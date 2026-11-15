import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import vm from 'node:vm';
const require=createRequire(import.meta.url);const ts=require('typescript');
const source=readFileSync(new URL('../apps/frontend/src/components/platform-analytics/platform.analytics.tsx',import.meta.url),'utf8');
const exports={};
vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,{exports,require:()=>({})});
test('temporary HTTP failure is an error, never a successful empty channel list',async()=>{
  await assert.rejects(exports.loadAnalyticsChannels(async()=>({ok:false,json:async()=>({integrations:[]})}),false),/채널 목록을 불러오지 못했습니다/);
});
test('malformed channel response is an error, valid empty list remains empty',async()=>{
  await assert.rejects(exports.loadAnalyticsChannels(async()=>({ok:true,json:async()=>({})}),false),/응답/);
  assert.equal((await exports.loadAnalyticsChannels(async()=>({ok:true,json:async()=>({integrations:[]})}),false)).length,0);
});
test('valid response preserves channels and existing provider restrictions',async()=>{
  const channels=[{id:'a',identifier:'youtube'},{id:'b',identifier:'x'},{id:'c',identifier:'unknown'}];
  const fetcher=async path=>{assert.equal(path,'/integrations/list');return {ok:true,json:async()=>({integrations:channels})};};
  assert.equal(JSON.stringify(await exports.loadAnalyticsChannels(fetcher,true)),JSON.stringify([channels[0]]));
  assert.equal(JSON.stringify(await exports.loadAnalyticsChannels(fetcher,false)),JSON.stringify(channels.slice(0,2)));
});
