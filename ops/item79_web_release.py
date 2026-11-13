"""Warm web slots; retain the existing app as the sole worker and live fallback."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.request
import base64

ROOT = Path('/opt/postiz-center-20261112')
ROUTE = Path('/data/coolify/proxy/dynamic/postiz-item79.yml')
STATE = ROOT / 'web-release.json'
DOMAIN = 'https://postiz.item79.com'

WORKER_FINGERPRINT_JS = r'''
const fs=require('node:fs'),crypto=require('node:crypto'),h=crypto.createHash('sha256');
function walk(path){const s=fs.lstatSync(path);h.update(path+'\0');if(s.isSymbolicLink())h.update(fs.readlinkSync(path));else if(s.isDirectory()){for(const name of fs.readdirSync(path).sort())walk(path+'/'+name);}else if(s.isFile())h.update(fs.readFileSync(path));}
for(const path of ['/app/apps/orchestrator/dist','/app/libraries/nestjs-libraries/src','/app/libraries/helpers/src','/app/package.json','/app/pnpm-lock.yaml','/app/apps/orchestrator/package.json'])walk(path);
h.update(process.version);console.log(h.digest('hex'));
'''
POLLERS_JS = r'''
const{Connection}=require('@temporalio/client');
(async()=>{const c=await Connection.connect({address:process.env.TEMPORAL_ADDRESS||'temporal:7233'});const queues={};for(const[name,type]of[['main',1],['main',2],['youtube',2]]){const r=await c.workflowService.describeTaskQueue({namespace:'default',taskQueue:{name},taskQueueType:type,includeTaskQueueStatus:true});queues[name+':'+type]=(r.pollers||[]).map(p=>p.identity).sort();}const attrs=await c.operatorService.listSearchAttributes({namespace:'default'});await c.close();console.log(JSON.stringify({queues,attributes:Object.keys(attrs.customAttributes||{}).sort()}));})().catch(e=>{console.error(e.name);process.exit(1)});
'''
# These are sentinel queues, not a census of all provider/email pollers.
# Container identity, orchestrator PID and restart count establish that this
# release did not replace the existing worker process.


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def atomic(path, content, mode=0o600):
    require(not path.is_symlink(), 'Unexpected symlink target')
    pending = path.with_name(path.name + '.pending')
    with pending.open('wb') as out:
        out.write(content)
        out.flush(); os.fsync(out.fileno())
    pending.chmod(mode)
    os.replace(pending, path)
    if os.name != 'nt':
        descriptor = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def worker_identity(args):
    container = subprocess.check_output(args + ['ps', '-q', 'app']).decode().strip()
    info = json.loads(subprocess.check_output(['docker', 'inspect', container]))[0]
    processes = json.loads(subprocess.check_output(['docker', 'exec', container, 'pm2', 'jlist']))
    worker = next(p for p in processes if p['name'] == 'orchestrator')
    require(worker['pm2_env']['status'] == 'online' and worker['pid'] > 0, 'Publishing worker is not online')
    pollers = json.loads(subprocess.check_output(['docker', 'exec', container, 'node', '-e', POLLERS_JS]))
    require(all(pollers['queues'].values()), 'Publishing task queues have no active poller')
    require({'organizationId', 'postId'} <= set(pollers['attributes']), 'Existing Temporal attributes missing')
    return {'container': container, 'image': info['Config']['Image'], 'pid': worker['pid'], 'restarts': worker['pm2_env']['restart_time'], 'sentinelPollerFingerprint': hashlib.sha256(json.dumps(pollers['queues'], sort_keys=True).encode()).hexdigest()}


def live_schema_unchanged(args):
    command = 'pnpm exec prisma migrate diff --from-schema-datasource libraries/nestjs-libraries/src/database/prisma/schema.prisma --to-schema-datamodel libraries/nestjs-libraries/src/database/prisma/schema.prisma --exit-code'
    result = subprocess.run(args + ['exec', '-T', 'app', 'sh', '-c', command], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(result.returncode == 0, 'Live database differs from retained application schema; no schema change allowed')


def verify_runtime_closure(image, container):
    old = subprocess.check_output(['docker', 'exec', container, 'node', '-e', WORKER_FINGERPRINT_JS]).decode().strip()
    new = subprocess.check_output(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'node', image, '-e', WORKER_FINGERPRINT_JS]).decode().strip()
    require(re.fullmatch('[a-f0-9]{64}', old) is not None and old == new, 'Retained worker runtime or shared contract differs')
    return old


def health(base, revision=None):
    with urllib.request.urlopen(base + '/auth/login', timeout=8) as response:
        require(response.status == 200, 'Web frontend unavailable')
        if revision is not None:
            require(response.headers.get('X-Item79-Revision') == revision, 'Traffic did not reach the intended revision')
    with urllib.request.urlopen(base + '/api/auth/can-register', timeout=8) as response:
        require(response.status == 200 and json.load(response) == {'register': False}, 'Backend unavailable or registration opened')
        if revision is not None:
            require(response.headers.get('X-Item79-Revision') == revision, 'Backend traffic revision mismatch')


def wait_health(base, revision=None, attempts=120):
    for _ in range(attempts):
        try:
            health(base, revision)
            return
        except Exception:
            time.sleep(5)
    raise RuntimeError('Web readiness deadline exceeded')


def validate_route(raw, state):
    config = json.loads(raw)
    routers = config['http']['routers']
    require(set(routers) == {'postiz-item79-https', 'postiz-item79-http'}, 'Unexpected router scope')
    require(all('Host(`postiz.item79.com`)' in r['rule'] and r['service'] == 'postiz-item79' for r in routers.values()), 'Unexpected domain/service binding')
    targets = config['http']['services']['postiz-item79']['loadBalancer']['servers']
    expected = 'http://postiz-item79-web-' + state['activeSlot'] + ':5000' if state else 'http://postiz-center-app:5000'
    require(targets == [{'url': expected}], 'Existing route differs from the scoped release state')
    return config


def slot_config(image, slot, nginx):
    require(slot in {'blue', 'green'}, 'Unknown web slot')
    return {'name': 'postiz-item79-web-' + slot, 'services': {'web': {
        'image': image, 'restart': 'unless-stopped', 'env_file': str(ROOT / 'app.env'),
        'environment': {'RUN_CRON': ''}, 'mem_limit': '2g', 'cpus': 1,
        'ports': ['127.0.0.1:' + ('34008' if slot == 'blue' else '34009') + ':5000'],
        'volumes': [str(ROOT / 'uploads') + ':/uploads', str(ROOT / 'app-config') + ':/config', str(nginx) + ':/etc/nginx/nginx.conf:ro'],
        'networks': {'app': {}, 'front': {'aliases': ['postiz-item79-web-' + slot]}},
        'command': ['sh', '-c', 'nginx && pnpm --filter ./apps/frontend run pm2 && pnpm --filter ./apps/backend run pm2 && pm2 logs'],
    }}, 'networks': {'app': {'external': True, 'name': 'postiz-center_default'}, 'front': {'external': True, 'name': 'imcloud-postiz-front'}}}


def recover_pending(args):
    journal = ROOT / 'web-release.pending.json'
    if not journal.exists():
        return
    pending = json.loads(journal.read_text())
    require(pending['slot'] in {'blue', 'green'}, 'Invalid pending slot')
    old = pending['oldState']
    committed = json.loads(STATE.read_text()) if STATE.exists() else None
    current_route = ROUTE.read_bytes()
    try:
        validate_route(current_route, old)
    except RuntimeError:
        validate_route(current_route, {'activeSlot': pending['slot']})
    require(worker_identity(args)['image'] == pending['workerImage'], 'Retained worker image changed during interrupted release')
    if committed and committed['revision'] == pending['revision']:
        try:
            wait_health(DOMAIN, committed['revision'], attempts=12)
        except Exception:
            atomic(ROUTE, base64.b64decode(pending['routeBefore'], validate=True), 0o644)
            if old:
                atomic(STATE, json.dumps(old).encode())
            else:
                STATE.unlink()
            wait_health(DOMAIN, old['revision'] if old else None, attempts=12)
    else:
        require(committed == old, 'Unexpected concurrent release state')
        atomic(ROUTE, base64.b64decode(pending['routeBefore'], validate=True), 0o644)
        wait_health(DOMAIN, old['revision'] if old else None, attempts=12)
    journal.unlink()


def wait_inactive_connections(commands):
    container = subprocess.check_output(commands + ['ps', '-q', 'web']).decode().strip()
    if not container:
        return
    script = r'''require('node:http').get('http://127.0.0.1:5000/_item79/connections',r=>{let s='';r.on('data',d=>s+=d);r.on('end',()=>{const m=s.match(/Active connections:\s*(\d+)/);if(r.statusCode!==200||!m)process.exit(1);console.log(m[1]);});}).on('error',()=>process.exit(1));'''
    quiet = 0
    for _ in range(30):
        count = int(subprocess.check_output(['docker', 'exec', container, 'node', '-e', script]))
        quiet = quiet + 1 if count <= 1 else 0  # The status request itself counts as one.
        if quiet >= 3:
            return
        time.sleep(2)
    raise RuntimeError('Inactive slot still handles requests; leave active uploads untouched')


def release(image, revision, args, validate_preview, backup_release):
    import yaml
    require(ROOT.resolve() == ROOT and ROUTE.resolve() == ROUTE, 'Unexpected release paths')
    recover_pending(args)
    before = worker_identity(args)
    fingerprint = verify_runtime_closure(image, before['container'])
    live_schema_unchanged(args)
    old_state = json.loads(STATE.read_text()) if STATE.exists() else None
    if old_state and old_state['image'] == image and old_state['revision'] == revision:
        validate_route(ROUTE.read_bytes(), old_state)
        health(DOMAIN, revision)
        require(worker_identity(args) == before, 'Worker changed during idempotent verification')
        print(json.dumps({'revision': revision, 'alreadyReleased': True, 'workerUnchanged': True}))
        return old_state
    validate_preview()
    require(worker_identity(args) == before, 'Worker changed during preview')
    backup = backup_release()
    route_before = ROUTE.read_bytes()
    route = validate_route(route_before, old_state)
    (backup / 'public-route.json').write_bytes(route_before)
    (backup / 'public-route.json').chmod(0o600)
    require(int(Path('/proc/meminfo').read_text().split('MemAvailable:')[1].split()[0]) * 1024 > 4 * 1024**3, 'Insufficient warm-slot memory headroom')
    slot = 'green' if old_state and old_state['activeSlot'] == 'blue' else 'blue'
    parent = ROOT / 'web-slots'
    parent.mkdir(mode=0o700, exist_ok=True)
    require(parent.resolve().parent == ROOT, 'Invalid web slot directory')
    directory = parent / slot
    directory.mkdir(mode=0o700, exist_ok=True)
    require(directory.resolve().parent == parent, 'Invalid web slot path')
    nginx = subprocess.check_output(['docker', 'exec', before['container'], 'cat', '/etc/nginx/nginx.conf']).decode()
    require(nginx.count('server {') == 1, 'Unexpected app nginx layout')
    nginx = nginx.replace('server {', 'server {\n        add_header X-Item79-Revision "' + revision + '" always;\n        location = /_item79/connections { stub_status; allow 127.0.0.1; deny all; }', 1)
    atomic(directory / 'nginx.conf', nginx.encode())
    atomic(directory / 'compose.yaml', yaml.safe_dump(slot_config(image, slot, directory / 'nginx.conf'), sort_keys=False).encode())
    commands = ['docker', 'compose', '--project-directory', str(directory)]
    port = 34008 if slot == 'blue' else 34009
    switched = False
    candidate_mutated = False
    journal = ROOT / 'web-release.pending.json'
    atomic(journal, json.dumps({'oldState': old_state, 'slot': slot, 'revision': revision, 'workerImage': before['image'], 'routeBefore': base64.b64encode(route_before).decode()}).encode())
    try:
        # This Compose project contains only web. Never recreate the existing app.
        wait_inactive_connections(commands)
        candidate_mutated = True
        subprocess.run(commands + ['up', '-d', '--no-deps', '--force-recreate', 'web'], check=True)
        wait_health('http://127.0.0.1:' + str(port), revision)
        processes = json.loads(subprocess.check_output(commands + ['exec', '-T', 'web', 'pm2', 'jlist']))
        require({p['name'] for p in processes} == {'frontend', 'backend'}, 'Web slot unexpectedly starts publishing workers')
        require(worker_identity(args) == before, 'Publishing worker changed during web warmup')
        route['http']['services']['postiz-item79']['loadBalancer']['servers'] = [{'url': 'http://postiz-item79-web-' + slot + ':5000'}]
        switched = True
        atomic(ROUTE, json.dumps(route, indent=2).encode(), 0o644)
        wait_health(DOMAIN, revision, attempts=12)
        for _ in range(3):
            health(DOMAIN, revision)
            time.sleep(2)
        require(worker_identity(args) == before, 'Publishing worker identity/pollers changed')
        live_schema_unchanged(args)
        state = {'version': 1, 'activeSlot': slot, 'revision': revision, 'image': image, 'previousSlot': old_state['activeSlot'] if old_state else None, 'worker': before, 'workerRuntimeFingerprint': fingerprint, 'updatedAt': time.time(), 'backup': str(backup)}
        atomic(STATE, json.dumps(state, indent=2).encode())
        try:
            journal.unlink()
        except OSError:
            pass  # Committed state/route are healthy; next invocation reconciles it.
        print(json.dumps({'releasedImage': image, 'revision': revision, 'activeWebSlot': slot, 'workerUnchanged': True, 'liveSchemaUnchanged': True, 'previousWebKeptWarm': bool(old_state)}))
        return state
    except BaseException:
        if switched:
            atomic(ROUTE, route_before, 0o644)
            wait_health(DOMAIN, old_state['revision'] if old_state else None, attempts=12)
        if STATE.exists() and json.loads(STATE.read_text()).get('revision') == revision:
            if old_state:
                atomic(STATE, json.dumps(old_state, indent=2).encode())
            else:
                STATE.unlink()
        can_stop = candidate_mutated
        if can_stop and switched:
            try:
                wait_inactive_connections(commands)
            except Exception:
                can_stop = False
                print(json.dumps({'failedCandidateKeptWarm': slot, 'reason': 'Connections have not drained; public route was restored'}))
        if can_stop:
            subprocess.run(commands + ['stop', 'web'], check=False)
        require(worker_identity(args) == before, 'Retained worker changed during rollback')
        if journal.exists():
            journal.unlink()
        raise
