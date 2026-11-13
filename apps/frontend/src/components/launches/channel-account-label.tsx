'use client';
import { useState } from 'react';
import { useFetch } from '@gitroom/helpers/utils/custom.fetch';
import { googleAccountLabel, validAccountEmail } from '@gitroom/helpers/utils/channel-account';
import { useUser } from '../layout/user.context';

export function ChannelAccountLabel({ id, settings, onSaved }: {
  id: string; settings: string | null; onSaved: () => unknown;
}) {
  const fetch = useFetch();
  const user = useUser();
  const email = googleAccountLabel(settings);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  async function save() {
    setSaving(true); setError('');
    try {
      if (draft.trim() && !validAccountEmail(draft.trim())) throw new Error('올바른 Google 계정 이메일을 입력하세요.');
      const response = await fetch(`/integrations/${encodeURIComponent(id)}/google-account-label`, {
        method: 'POST', body: JSON.stringify({ email: draft.trim(), expectedEmail: email }),
      });
      if (response.status === 409) throw new Error('다른 변경이 있습니다. 새로고침 후 다시 저장하세요.');
      if (!response.ok) throw new Error('계정 표시 저장에 실패했습니다. 다시 시도하세요.');
      await onSaved(); setEditing(false);
    } catch (e) { setError(e instanceof Error ? e.message : '저장에 실패했습니다.'); }
    finally { setSaving(false); }
  }
  if (!['ADMIN', 'SUPERADMIN'].includes(user?.role || '')) {
    return <span className="block text-[12px] truncate" title={email || '계정 기록 없음'}>{email || '계정 기록 없음'}{email && ' · 직접 기록'}</span>;
  }
  return <div className="text-[12px] leading-5 min-w-0" onClick={e => e.stopPropagation()}>
    {!editing ? <button type="button" className="block text-start max-w-full truncate opacity-75 hover:opacity-100"
      title={email ? `연결 Google 계정 · 직접 기록: ${email}` : '연결한 Google 계정을 직접 기록하세요.'}
      onClick={() => { setDraft(email || ''); setError(''); setEditing(true); }}>
      {email || 'Google 계정 기록'}{email && <span className="ms-1 text-[10px]">· 직접 기록</span>}
    </button> : <div className="py-1 space-y-1">
      <label className="block">연결 Google 계정 (직접 기록)
        <input type="email" value={draft} maxLength={254} disabled={saving} aria-label="연결 Google 계정 이메일"
          className="block w-full min-w-0 bg-newBgColorInner border border-current rounded px-1"
          onChange={e => setDraft(e.target.value)} />
      </label>
      <div className="flex gap-3"><button type="button" disabled={saving} onClick={save}>{saving ? '저장 중…' : '저장'}</button>
        <button type="button" disabled={saving} onClick={() => setEditing(false)}>취소</button></div>
      {error && <p role="alert" className="text-red-400 whitespace-normal">{error}</p>}
    </div>}
  </div>;
}
