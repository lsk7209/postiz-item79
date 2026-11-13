// Display metadata only: never an OAuth identity or publishing authority.
export const GOOGLE_ACCOUNT_LABEL = 'item79_google_account_email';
export function youtubeChannelUrl(identifier: string, channelId: string): string | null {
  return identifier === 'youtube' && /^UC[A-Za-z0-9_-]{22}$/.test(channelId)
    ? `https://www.youtube.com/channel/${channelId}` : null;
}
export function validAccountEmail(value: unknown): value is string {
  return typeof value === 'string' && value.length <= 254 &&
    /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}$/.test(value);
}
export function accountSettings(raw: string | null | undefined): Record<string, unknown>[] {
  try {
    const parsed: unknown = JSON.parse(raw || '[]');
    if (!Array.isArray(parsed) || parsed.some(p => !p || typeof p !== 'object' || Array.isArray(p))) throw new Error();
    return parsed;
  } catch { throw new Error('기존 채널 설정을 읽을 수 없습니다. 새로고침 후 다시 시도하세요.'); }
}
export function googleAccountLabel(raw: string | null | undefined): string | null {
  try {
    const values = accountSettings(raw).filter(p => p.title === GOOGLE_ACCOUNT_LABEL);
    return values.length === 1 && validAccountEmail(values[0].value) ? values[0].value : null;
  } catch { return null; }
}
export function withGoogleAccountLabel(raw: string | null | undefined, email: string): string {
  const value = email.trim();
  if (value && !validAccountEmail(value)) throw new Error('올바른 Google 계정 이메일을 입력하세요.');
  const settings = accountSettings(raw).filter(p => p.title !== GOOGLE_ACCOUNT_LABEL);
  if (value) settings.push({title: GOOGLE_ACCOUNT_LABEL, description: '연결 Google 계정 (관리자 직접 기록; OAuth 소유권 증명 아님)', type: 'text', value});
  return JSON.stringify(settings);
}
