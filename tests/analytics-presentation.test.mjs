import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import vm from 'node:vm';
const require=createRequire(import.meta.url);
const ts=require('typescript');
const source=readFileSync(new URL('../apps/frontend/src/components/platform-analytics/render.analytics.tsx',import.meta.url),'utf8');
const output=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}});
const api={};
let lastChart;
const imports={react:{useRef:()=>({current:{}}),useEffect:fn=>fn(),useMemo:fn=>fn()},'swr':()=>{},'chart.js/auto':class {constructor(canvas,config){lastChart=config;}destroy(){}},'react-use-cookie':()=>['dark'],'react/jsx-runtime':{jsx:(type,props)=>({type,props}),jsxs:(type,props)=>({type,props})},'@gitroom/helpers/utils/custom.fetch':{}};
vm.runInNewContext(output.outputText,{exports:api,require:id=>{if(!(id in imports))throw Error('Unexpected import '+id);return imports[id];}});
const metric=(label,points)=>({label,data:points.map(([date,total])=>({date,total}))});

test('all seven YouTube headings have Korean labels',()=>{
  for(const label of ['Views','Estimated Minutes Watched','Average View Duration','Average View Percentage','Subscribers Gained','Subscribers Lost','Likes']){
    assert.notEqual(api.koreanMetricLabel(label),label);assert.match(api.koreanMetricLabel(label),/[가-힣]/);
  }
});
test('weighted means join dates, not array positions or simple daily averages',()=>{
  const views=metric('Views',[['2026-11-01',1],['2026-11-02',99]]);
  const average=metric('Average View Duration',[['2026-11-02',10],['2026-11-01T00:00:00Z',100]]);
  assert.equal(api.weightedAverage(average,views),10.9);
});
test('undefined and invalid values never silently become zero',()=>{
  assert.equal(api.metricSum(),null);assert.equal(api.metricSum(metric('Views',[])),null);
  for(const value of [null,undefined,NaN,Infinity,' ',false,[],{}])assert.equal(api.metricSum(metric('Views',[['2026-11-01',value]])),null);
  assert.equal(api.metricSum(metric('Views',[['2026-11-01',0]])),0);
  assert.equal(api.formatCount(null,'회'),'—');assert.equal(api.formatCount(0,'회'),'0회');
});
test('no views has no defined average, positive views need a matching average',()=>{
  assert.equal(api.weightedAverage(metric('Average View Duration',[['a',0]]),metric('Views',[['a',0]])),null);
  assert.equal(api.weightedAverage(metric('Average View Duration',[['a',10]]),metric('Views',[['a',1],['b',3]])),null);
  assert.equal(api.weightedAverage(metric('Average View Duration',[['a',0]]),metric('Views',[['a',10]])),0);
});
test('subscriber net requires matching complete series and keeps its sign',()=>{
  const report=api.buildAnalyticsReport([metric('Subscribers Gained',[['a',2]]),metric('Subscribers Lost',[['a',5]])]);
  assert.equal(report.net,-3);assert.equal(report.rows[0].net,-3);
  const partial=api.buildAnalyticsReport([metric('Subscribers Gained',[['a',2],['b',3]]),metric('Subscribers Lost',[['a',1]])]);
  assert.equal(partial.net,null);assert.equal(partial.rows[1].net,null);
});
test('Korean duration formatting handles seconds, minutes, hours and missing data',()=>{
  for(const [seconds,text] of [[null,'—'],[-1,'—'],[0,'0초'],[9,'9초'],[60,'1분'],[75,'1분 15초'],[20160,'5시간 36분']])assert.equal(api.formatDuration(seconds),text);
  assert.equal(api.formatCount(1234,'회'),'1,234회');
});
test('daily table preserves gaps and source input bytes',()=>{
  const input=[metric('Views',[['2026-11-03',20],['2026-11-01',5]]),metric('Likes',[['2026-11-02',1]])];const before=JSON.stringify(input);
  const report=api.buildAnalyticsReport(input);
  assert.equal(report.rows[1].date,'2026-11-02');assert.equal(report.rows[1].views,null);assert.equal(report.rows[1].likes,1);
  assert.equal(JSON.stringify(input),before);
});
test('other-provider and unknown metrics are retained without YouTube assumptions',()=>{
  const items=[metric('Views',[['a',12]]),metric('Custom metric',[['a',7]])];
  const other=api.buildAnalyticsReport(items,false);assert.equal(other.hasStandardMetrics,false);assert.equal(JSON.stringify(other.extras),JSON.stringify(items));
  const youtube=api.buildAnalyticsReport(items);assert.equal(youtube.extras[0].label,'Custom metric');
});
test('actual chart configuration keeps zero-valued points and explicit null gaps',()=>{
  lastChart=null;
  api.ViewsChart({rows:[{date:'2026-11-01',views:0},{date:'2026-11-02',views:null},{date:'2026-11-03',views:20}]});
  assert.equal(JSON.stringify(lastChart.data.datasets[0].data),'[0,null,20]');assert.equal(lastChart.data.datasets[0].spanGaps,false);
  assert.equal(lastChart.data.datasets[0].label,'조회수');assert.equal(lastChart.options.scales.x.grid.display,false);
});
test('an all-zero valid series draws a zero chart rather than a missing-data state',()=>{
  lastChart=null;api.ViewsChart({rows:[{date:'2026-11-01',views:0}]});assert.ok(lastChart);assert.equal(lastChart.data.datasets[0].data[0],0);
  lastChart=null;api.ViewsChart({rows:[{date:'2026-11-01',views:null}]});assert.equal(lastChart,null);
});
test('tooltip does not turn a missing numeric value into zero',()=>{
  api.ViewsChart({rows:[{date:'2026-11-01',views:1}]});
  const label=lastChart.options.plugins.tooltip.callbacks.label;
  assert.equal(label({parsed:{y:null}}),'조회수 —');assert.equal(label({parsed:{y:0}}),'조회수 0회');
});
test('both frontend sources parse without JSX syntax diagnostics',()=>{
  for(const name of ['render.analytics.tsx','platform.analytics.tsx']){
    const result=ts.transpileModule(readFileSync(new URL('../apps/frontend/src/components/platform-analytics/'+name,import.meta.url),'utf8'),{reportDiagnostics:true,compilerOptions:{jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2022}});
    assert.deepEqual((result.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).map(d=>d.code),[]);
  }
});
