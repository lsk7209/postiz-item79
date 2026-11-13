#!/usr/bin/env python3
"""Independent public health/deployment observer with private deduplicated alerts."""
import datetime
import json
import os
from pathlib import Path
import shutil
import smtplib
import ssl
import subprocess
import time
import urllib.request
import urllib.parse
from email.message import EmailMessage

ROOT = Path('/var/lib/item79-offsite')
CONFIG = Path('/etc/item79-ops')
SITE = 'https://postiz.item79.com'


def atomic_json(path, data):
    pending = path.with_name(path.name + '.pending')
    with pending.open('w', encoding='utf-8') as out:
        json.dump(data, out); out.flush(); os.fsync(out.fileno())
    pending.chmod(0o600); os.replace(pending, path)


def read_json(url, timeout=12):
    request = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'item79-private-ops/1'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def public_health():
    try:
        with urllib.request.urlopen(SITE + '/auth/login', timeout=12) as response:
            if response.status != 200:
                return False
        return read_json(SITE + '/api/auth/can-register') == {'register': False}
    except Exception:
        return False


def health_transition(state, healthy, now):
    events = []
    state['bad'] = 0 if healthy else state.get('bad', 0) + 1
    state['good'] = state.get('good', 0) + 1 if healthy else 0
    if not healthy and state['bad'] >= 3 and not state.get('down'):
        state['down'] = True
        events.append({'id': 'site-down-' + str(now), 'kind': 'site_down', 'message': 'Item79 장애 감지: postiz.item79.com이 3회 연속 정상 응답하지 않았습니다.'})
    if healthy and state['good'] >= 2 and state.get('down'):
        state['down'] = False
        events.append({'id': 'site-recovered-' + str(now), 'kind': 'site_recovered', 'message': 'Item79 복구 확인: postiz.item79.com이 다시 정상 응답합니다.'})
    return events


def failed_deploys(data, installed_at, seen):
    events = []
    for run in data.get('workflow_runs', []):
        identifier = str(run['id'])
        if run.get('head_branch') != 'main' or run.get('event') not in {'push', 'workflow_dispatch'} or run.get('conclusion') not in {'failure', 'timed_out', 'action_required'}:
            continue
        if run.get('created_at', '') < installed_at or identifier in seen:
            continue
        events.append({'id': 'deploy-' + identifier, 'kind': 'deploy_failed', 'runId': identifier, 'message': 'Item79 자동 배포 실패: ' + run['html_url']})
    return events


def workflow_runs(since):
    runs = []
    for page in range(1, 11):
        query = urllib.parse.urlencode({'branch': 'main', 'per_page': 100, 'page': page, 'created': '>=' + since})
        data = read_json('https://api.github.com/repos/lsk7209/postiz-item79/actions/workflows/item79.yml/runs?' + query)
        # GitHub limits filtered searches to 1,000. Report a coverage failure
        # instead of silently accepting an incomplete observation window.
        if data.get('total_count', 0) >= 1000:
            raise RuntimeError('Deployment observation window exceeds API coverage')
        batch = data['workflow_runs']
        runs.extend(batch)
        if len(batch) < 100:
            return runs
    raise RuntimeError('Deployment observation pagination incomplete')


def observe_deployments(state, installed_at, now):
    try:
        runs = workflow_runs(state.get('githubScanSince', installed_at))
        events = failed_deploys({'workflow_runs': runs}, installed_at, state['seenRuns'])
        state['seenRuns'] = list(dict.fromkeys(state['seenRuns'] + [event['runId'] for event in events]))[-1000:]
        # Revisit unfinished older runs until they finish, plus five minutes of
        # overlap. A failed scan never advances this durable cursor.
        overlap = datetime.datetime.fromtimestamp(now - 300, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        unfinished = [run['created_at'] for run in runs if run.get('status') != 'completed']
        state['githubScanSince'] = max(installed_at, min([overlap] + unfinished))
        if state.get('githubFailures', 0) >= 2:
            events.append({'id': 'github-recovered-' + str(now), 'kind': 'github_recovered', 'message': 'Item79 배포 감시 연결이 복구됐습니다.'})
        state['githubFailures'] = 0
        state['githubObservable'] = True
    except Exception:
        state['githubObservable'] = False
        state['githubFailures'] = state.get('githubFailures', 0) + 1
        events = []
        if state['githubFailures'] == 2:
            events.append({'id': 'github-unavailable-' + str(now), 'kind': 'github_unavailable', 'message': 'Item79 경고: GitHub 배포 감시를 연속 확인하지 못했습니다. 배포 실패 감지에 공백이 있을 수 있습니다.'})
    state['lastGithubAt'] = now
    return events


def source_status():
    config = json.loads((CONFIG / 'offsite.json').read_text())
    command = ['ssh', '-i', config['sourceKey'], '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=' + config['sourceKnownHosts'], '-o', 'ConnectTimeout=10', config['sourceUser'] + '@' + config['sourceHost'], 'status']
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
    if result.returncode:
        raise RuntimeError('Encrypted backup export unavailable')
    return json.loads(result.stdout)


def deliver(config, message):
    provider = config['provider']
    if provider == 'telegram':
        url = 'https://api.telegram.org/bot' + config['botToken'] + '/sendMessage'
        payload = {'chat_id': config['chatId'], 'text': message, 'disable_web_page_preview': True}
    elif provider == 'discord':
        url = config['webhookUrl']
        if not url.startswith(('https://discord.com/api/webhooks/', 'https://discordapp.com/api/webhooks/')):
            raise ValueError('Only the configured Discord webhook provider is supported')
        url += ('&' if '?' in url else '?') + 'wait=true'
        payload = {'content': message, 'allowed_mentions': {'parse': []}}
    elif provider == 'smtp':
        mail = EmailMessage()
        mail['Subject'] = 'Item79 운영 알림'
        mail['From'] = config['from']
        mail['To'] = config['to']
        mail.set_content(message)
        context = ssl.create_default_context()
        if config.get('starttls'):
            client = smtplib.SMTP(config['host'], config.get('port', 587), timeout=20)
            client.starttls(context=context)
        else:
            client = smtplib.SMTP_SSL(config['host'], config.get('port', 465), timeout=20, context=context)
        with client:
            client.login(config['username'], config['password'])
            refused = client.send_message(mail)
            if refused:
                raise RuntimeError('Notification recipient refused')
        return {'provider': provider, 'accepted': True}
    else:
        raise ValueError('Notification provider is not configured')
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.load(response)
    if provider == 'telegram':
        if not data.get('ok'):
            raise RuntimeError('Notification provider rejected message')
        return {'provider': provider, 'accepted': True, 'deliveryId': data['result']['message_id']}
    return {'provider': provider, 'accepted': True, 'deliveryId': data['id']}


def main():
    os.umask(0o077)
    import fcntl
    with (ROOT / '.monitor.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        settings = json.loads((CONFIG / 'monitor.json').read_text())
        state_file = ROOT / 'monitor-state.json'
        state = json.loads(state_file.read_text()) if state_file.exists() else {'seenRuns': [], 'pending': [], 'delivered': []}
        now = int(time.time())
        state['lastCheckedAt'] = now
        healthy = public_health()
        state['siteHealthy'] = healthy
        state['pending'].extend(health_transition(state, healthy, now))
        if now - state.get('lastGithubAt', 0) >= 300:
            state['pending'].extend(observe_deployments(state, settings['installedAt'], now))
        if now - state.get('lastSourceAt', 0) >= 300:
            try:
                receipt = source_status()
                state['sourceDiskFree'] = receipt['sourceFreeBytes']
                state['sourceExportBytes'] = receipt['exportBytes']
                state['sourceExportFailures'] = 0
            except Exception:
                state['sourceExportFailures'] = state.get('sourceExportFailures', 0) + 1
            state['lastSourceAt'] = now
        backup = ROOT / 'latest.json'
        latest = json.loads(backup.read_text()) if backup.exists() else None
        state['offsiteBackupFresh'] = bool(latest and datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(latest['verifiedAt']) < datetime.timedelta(hours=30))
        state['storageHeadroomBytes'] = shutil.disk_usage(ROOT).free
        for condition, key, text in [
            (not state['offsiteBackupFresh'], 'backup_stale', 'Item79 백업 경고: OVH에서 최근 30시간 이내 검증된 백업을 확인하지 못했습니다.'),
            (state['storageHeadroomBytes'] < 6 * 1024**3, 'storage_low', 'Item79 백업 경고: 독립 백업 서버의 여유 공간이 6GiB 아래입니다. 기존 백업은 자동 삭제하지 않습니다.'),
            (state.get('sourceDiskFree', 20 * 1024**3) < 16 * 1024**3 or state.get('sourceExportBytes', 0) > 8 * 1024**3, 'source_storage_low', 'Item79 백업 경고: 원본 서버 여유 공간 또는 암호화 전송 보관 용량을 확인해야 합니다. 기존 복구 백업은 자동 삭제하지 않습니다.'),
            (state.get('sourceExportFailures', 0) >= 2, 'source_export_failed', 'Item79 백업 경고: 원본 암호화 백업 내보내기에 연속 접속하지 못했습니다.'),
        ]:
            if condition and not state.get(key):
                state['pending'].append({'id': key + '-' + str(now), 'kind': key, 'message': text})
            state[key] = condition
        # Persist event identity before sending. Pending delivery stays explicit.
        atomic_json(state_file, state)
        notify = CONFIG / 'notify.json'
        state['notificationConfigured'] = notify.exists()
        if notify.exists():
            recipient = json.loads(notify.read_text())
            for event in list(state['pending']):
                try:
                    proof = deliver(recipient, event['message'])
                except Exception as error:
                    state['deliveryErrorType'] = type(error).__name__
                    break
                state['pending'].remove(event)
                state['delivered'].append({'eventId': event['id'], 'time': now, **proof})
                state['delivered'] = state['delivered'][-100:]
                atomic_json(state_file, state)
        atomic_json(state_file, state)
        print(json.dumps({'event': 'item79_monitor_checked', 'siteHealthy': healthy, 'notificationConfigured': notify.exists(), 'pendingDelivery': len(state['pending']), 'offsiteBackupFresh': state['offsiteBackupFresh']}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'event': 'monitor_failed', 'errorType': type(error).__name__}))
        raise SystemExit(1)
