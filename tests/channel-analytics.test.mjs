import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';
const require = createRequire(import.meta.url);
const ts = require('typescript');
const source = readFileSync(new URL('../apps/backend/src/api/routes/channel-analytics.ts', import.meta.url), 'utf8');
class HttpException extends Error { constructor(body, status) { super(body.message); this.body=body; this.status=status; } }
class NotFoundException extends Error {}
class BadRequestException extends Error {}
function setup({failure, rows=[['2026-11-12',12,5,25,45,1,3,0]], integration, redisFailure=false}={}) {
  const calls={query:[],credentials:[],cache:new Map(),lookups:[]};
  const channel={id:'channel-1',organizationId:'org-1',providerIdentifier:'youtube',internalId:'UC1234567890123456789012',token:'private-access',refreshToken:'private-refresh',tokenExpiration:new Date(Date.now()+3600000),deletedAt:null,...integration};
  const service={getIntegrationById:async(org,id)=>{calls.lookups.push([org,id]);return org===channel.organizationId&&id===channel.id?channel:null;},checkAnalytics:async()=>['other-provider']};
  const exports={};
  const imports={
    '@nestjs/common':{HttpException,NotFoundException,BadRequestException},
    googleapis:{google:{auth:{OAuth2:class {setCredentials(c){calls.credentials.push(c);}}},youtubeAnalytics:()=>({reports:{query:async q=>{calls.query.push(q);if(failure)throw failure;return {data:{columnHeaders:['day','views','estimatedMinutesWatched','averageViewDuration','averageViewPercentage','subscribersGained','likes','subscribersLost'].map(name=>({name})),rows}};}}})}},
    '@gitroom/nestjs-libraries/redis/redis.service':{ioRedis:{get:async k=>{if(redisFailure)throw Error('redis offline');return calls.cache.get(k)||null;},set:async(k,v)=>{if(redisFailure)throw Error('redis offline');calls.cache.set(k,v);}}},
  };
  const output=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText;
  vm.runInNewContext(output,{exports,require:id=>{if(!(id in imports))throw Error('Unexpected import '+id);return imports[id];},process:{env:{YOUTUBE_CLIENT_ID:'client',YOUTUBE_CLIENT_SECRET:'secret'}},Date,JSON,Number,Math});
  return {calls,read:(date='7',org='org-1',id='channel-1')=>exports.readChannelAnalytics(service,{id:org},id,date)};
}
test('uses exact channel ID and stored refresh grant; returns views with correct units',async()=>{
  const {calls,read}=setup();const data=await read();
  assert.equal(calls.query[0].ids,'channel==UC1234567890123456789012');
  assert.equal(calls.credentials[0].refresh_token,'private-refresh');
  assert.equal(data.find(m=>m.label==='Views').data[0].total,12);
  assert.equal(data.find(m=>m.label==='Average View Duration').unit,'seconds');
  assert.equal(data.find(m=>m.label==='Average View Percentage').unit,'percent');
  assert.ok(!JSON.stringify(data).includes('private-'));
});
test('validates ownership and deleted channels before cache/provider access',async()=>{
  for(const options of [{},{integration:{deletedAt:new Date()}}]){
    const {calls,read}=setup(options);await assert.rejects(read('7',options.integration?'org-1':'foreign-org'),NotFoundException);assert.equal(calls.query.length,0);assert.equal(calls.cache.size,0);
  }
});
test('cache separates organization/channel/period and uses a new namespace',async()=>{
  const {calls,read}=setup();await read('7');await read('7');assert.equal(calls.query.length,1);await read('30');assert.equal(calls.query.length,2);assert.equal(calls.cache.size,2);assert.ok([...calls.cache.keys()].every(k=>k.startsWith('channel-analytics:v1:org-1:channel-1:')));
});
test('empty report is no data, not zero metrics or authorization failure',async()=>{
  const {read}=setup({rows:[]});assert.equal((await read()).length,0);
});
test('service configuration, authorization, quota and network failures stay distinguishable and sanitized',async()=>{
  for(const [status,reason,code] of [[403,'accessNotConfigured','ANALYTICS_API_DISABLED'],[403,'insufficientPermissions','ANALYTICS_PERMISSION_REQUIRED'],[401,'authError','CHANNEL_AUTHORIZATION_REQUIRED'],[403,'quotaExceeded','ANALYTICS_RATE_LIMITED'],[503,'backendError','ANALYTICS_UNAVAILABLE']]){
    const {calls,read}=setup({failure:{message:'private-access',response:{status,data:{error:{errors:[{reason}],message:'private-refresh'}}}}});
    await assert.rejects(read(),e=>{assert.equal(e.body.code,code);assert.ok(!JSON.stringify(e.body).includes('private-'));assert.notEqual(e.status,401);return true;});assert.equal(calls.cache.size,0);
  }
});
test('temporary cache failure still permits provider reads',async()=>{
  const {read}=setup({redisFailure:true});assert.equal((await read()).length,7);
});
test('rejects invalid periods and channel identifiers without provider call',async()=>{
  for(const date of ['0','-1','NaN','366','7.5']){const {read,calls}=setup();await assert.rejects(read(date),BadRequestException);assert.equal(calls.query.length,0);}
  const {read,calls}=setup({integration:{internalId:'channel==MINE'}});await assert.rejects(read(),BadRequestException);assert.equal(calls.query.length,0);
});
test('other providers retain their existing analytics implementation',async()=>{
  const {read,calls}=setup({integration:{providerIdentifier:'instagram'}});assert.deepEqual(await read(),['other-provider']);assert.equal(calls.query.length,0);
});
test('analytics page retry revalidates API without constructing a social login URL',()=>{
  const ui=readFileSync(new URL('../apps/frontend/src/components/platform-analytics/render.analytics.tsx',import.meta.url),'utf8');
  assert.ok(!ui.includes('/integrations/social/'));assert.ok(!ui.includes('window.location.href'));assert.match(ui,/mutate\(/);assert.match(ui,/response\.ok/);
});
