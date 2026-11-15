import { BadRequestException, HttpException, NotFoundException } from '@nestjs/common';
import type { Organization } from '@prisma/client';
import type { IntegrationService } from '@gitroom/nestjs-libraries/database/prisma/integrations/integration.service';
import { ioRedis } from '@gitroom/nestjs-libraries/redis/redis.service';
import { google } from 'googleapis';

// Web/API-only reader: never changes the publishing worker, channel state or grants.
export async function readChannelAnalytics(
  service: IntegrationService,
  org: Organization,
  integrationId: string,
  date: string
) {
  const days = date === undefined || date === '' ? 7 : Number(date);
  if (!Number.isSafeInteger(days) || days < 1 || days > 365) {
    throw new BadRequestException('Analytics period must be between 1 and 365 days');
  }
  const integration = await service.getIntegrationById(org.id, integrationId);
  if (!integration || integration.deletedAt) throw new NotFoundException();
  if (integration.providerIdentifier !== 'youtube') {
    return service.checkAnalytics(org, integrationId, String(days));
  }
  if (!/^UC[A-Za-z0-9_-]{22}$/.test(integration.internalId)) {
    throw new BadRequestException('Invalid YouTube channel identifier');
  }
  // Deliberately separate from the legacy MINE cache, which may contain another channel.
  const key = `channel-analytics:v1:${org.id}:${integrationId}:${days}`;
  const cached = await ioRedis.get(key).catch(() => null);
  if (cached) {
    try { return JSON.parse(cached); } catch { /* Read again from the provider. */ }
  }
  const client = new google.auth.OAuth2({
    clientId: process.env.YOUTUBE_CLIENT_ID,
    clientSecret: process.env.YOUTUBE_CLIENT_SECRET,
    forceRefreshOnFailure: true,
  });
  client.setCredentials({
    access_token: integration.token,
    refresh_token: integration.refreshToken || undefined,
    expiry_date: integration.tokenExpiration?.getTime(),
  });
  const end = new Date();
  const start = new Date(end.getTime() - days * 86400000);
  try {
    // google-auth-library automatically refreshes expired tokens and retries 401s
    // using the saved grant. Refreshed tokens stay in server memory only.
    const { data } = await google.youtubeAnalytics({version: 'v2', auth: client}).reports.query({
      ids: `channel==${integration.internalId}`,
      startDate: start.toISOString().slice(0, 10),
      endDate: end.toISOString().slice(0, 10),
      metrics: 'views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,likes,subscribersLost',
      dimensions: 'day',
      sort: 'day',
    }, { timeout: 20000 });
    const columns = data.columnHeaders?.map(column => column.name) || [];
    const rows = data.rows || [];
    const metrics = [
      ['views', 'Views', false, 'count'],
      ['estimatedMinutesWatched', 'Estimated Minutes Watched', false, 'minutes'],
      ['averageViewDuration', 'Average View Duration', true, 'seconds'],
      ['averageViewPercentage', 'Average View Percentage', true, 'percent'],
      ['subscribersGained', 'Subscribers Gained', false, 'count'],
      ['subscribersLost', 'Subscribers Lost', false, 'count'],
      ['likes', 'Likes', false, 'count'],
    ] as const;
    const result = rows.length ? metrics.map(([metric, label, average, unit]) => ({
      label, average, unit,
      data: rows.map(row => ({date: String(row[columns.indexOf('day')]), total: Number(row[columns.indexOf(metric)])})),
    })) : [];
    if (result.some(metric => metric.data.some(point => !Number.isFinite(point.total)))) {
      throw new Error('Invalid provider report');
    }
    await ioRedis.set(key, JSON.stringify(result), 'EX', 300).catch(() => undefined);
    return result;
  } catch (error: unknown) {
    const failure = error as { response?: {status?: number; data?: {error?: {errors?: {reason?: string}[]} | string}}; code?: number };
    const status = failure.response?.status || failure.code;
    const body = failure.response?.data?.error;
    const reason = typeof body === 'string' ? body : body?.errors?.[0]?.reason;
    let code = 'ANALYTICS_UNAVAILABLE';
    let message = '분석 API에 일시적으로 연결할 수 없습니다. 잠시 후 다시 조회해 주세요.';
    let httpStatus = 503;
    if (reason === 'accessNotConfigured' || reason === 'serviceDisabled') {
      code = 'ANALYTICS_API_DISABLED';
      message = 'Google 프로젝트의 YouTube Analytics API 활성화가 필요합니다. 채널 재로그인은 필요하지 않습니다.';
      httpStatus = 424;
    } else if (status === 429 || reason === 'quotaExceeded' || reason === 'rateLimitExceeded' || reason === 'dailyLimitExceeded') {
      code = 'ANALYTICS_RATE_LIMITED';
      message = '분석 API 조회 한도에 도달했습니다. 잠시 후 다시 조회해 주세요.';
      httpStatus = 429;
    } else if (status === 401 || reason === 'invalid_grant') {
      code = 'CHANNEL_AUTHORIZATION_REQUIRED';
      message = '저장된 채널 연결 권한을 갱신할 수 없습니다. 채널 관리에서 연결 권한을 확인해 주세요.';
      // A provider authentication failure must not sign the user out of Postiz.
      httpStatus = 424;
    } else if (status === 403) {
      code = 'ANALYTICS_PERMISSION_REQUIRED';
      message = '이 채널의 분석 조회 권한이 없습니다. 연결된 채널과 Google 분석 권한을 확인해 주세요.';
      httpStatus = 424;
    }
    // Never return/log Google error bodies: they can contain request credentials.
    throw new HttpException({code, message}, httpStatus);
  }
}
