import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';
import * as account from '../libraries/helpers/src/utils/channel-account.ts';
const require = createRequire(import.meta.url);
const ts = require('typescript');
const noopDecorator = () => () => {};
class BadRequestException extends Error {}
class ConflictException extends Error {}
class NotFoundException extends Error {}
class ForbiddenException extends Error {}
function load(file, name) {
  const output = ts.transpileModule(readFileSync(new URL('../' + file, import.meta.url), 'utf8'), {
    compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, experimentalDecorators: true, emitDecoratorMetadata: false},
  }).outputText;
  const exports = {};
  const imports = {
    '@nestjs/common': new Proxy({BadRequestException, ConflictException, NotFoundException, ForbiddenException}, {get: (obj,key) => obj[key] || noopDecorator}),
    '@gitroom/helpers/utils/channel-account': account,
    '@gitroom/nestjs-libraries/upload/upload.factory': {UploadFactory: {createStorage: () => ({})}},
    '@gitroom/backend/services/auth/permissions/permission.exception.class': {AuthorizationActions: {Create:'create'}, Sections: {CHANNEL:'channel'}},
  };
  vm.runInNewContext(output, { exports, require: id => imports[id] || new Proxy({}, {get: () => noopDecorator}), process: {env:{}}, console });
  return exports[name];
}
const Repository = load('libraries/nestjs-libraries/src/database/prisma/integrations/integration.repository.ts','IntegrationRepository');
const Controller = load('apps/backend/src/api/routes/integrations.controller.ts','IntegrationsController');
function fixture() {
  const initial = { id:'channel-a', organizationId:'org-a', providerIdentifier:'youtube', deletedAt:null, updatedAt:new Date(1000), additionalSettings: account.withGoogleAccountLabel('[{"title":"other","value":42}]','owner@example.com') };
  let row = {...initial}; let collision = false;
  const model = {integration: {
    findFirst: async ({where}) => row && Object.entries(where).every(([k,v])=>row[k]===v) ? {...row} : null,
    updateMany: async ({where,data}) => { if(collision || !Object.entries(where).every(([k,v])=>row[k]===v)) return {count:0}; row={...row,...data}; return {count:1}; },
  }};
  return {repo: new Repository({model}), row:()=>row, collide:()=>{collision=true;}};
}
test('only organization administrators can update account labels', async () => {
  let calls=0;
  const controller = new Controller({}, {updateGoogleAccountLabel: async()=>{calls++;return {saved:true};}});
  for(const role of ['USER','',undefined]) await assert.rejects(controller.updateGoogleAccountLabel({id:'org-a',users:[{role}]},'channel-a',{email:'new@example.com',expectedEmail:null}),ForbiddenException);
  assert.equal(calls,0);
  await controller.updateGoogleAccountLabel({id:'org-a',users:[{role:'ADMIN'}]},'channel-a',{email:'new@example.com',expectedEmail:null});
  assert.equal(calls,1);
});
test('cross-organization edits cannot reach another channel', async()=>{
  const f=fixture(); await assert.rejects(f.repo.updateGoogleAccountLabel('org-b','channel-a','other@example.com','owner@example.com'),NotFoundException);
  assert.equal(account.googleAccountLabel(f.row().additionalSettings),'owner@example.com');
});
test('label edit preserves existing provider values and rejects stale label', async()=>{
  const f=fixture();
  await f.repo.updateGoogleAccountLabel('org-a','channel-a','new@example.com','owner@example.com');
  assert.equal(account.googleAccountLabel(f.row().additionalSettings),'new@example.com');
  assert.equal(JSON.parse(f.row().additionalSettings)[0].value,42);
  await assert.rejects(f.repo.updateGoogleAccountLabel('org-a','channel-a','stale@example.com','owner@example.com'),ConflictException);
});
test('a simultaneous provider edit causes a conflict instead of overwriting it', async()=>{
  const f=fixture();f.collide();
  await assert.rejects(f.repo.updateGoogleAccountLabel('org-a','channel-a','new@example.com','owner@example.com'),ConflictException);
  assert.equal(account.googleAccountLabel(f.row().additionalSettings),'owner@example.com');
});
test('generic settings cannot replace or erase an admin account record', async()=>{
  const f=fixture();
  await f.repo.updateProviderSettings('org-a','channel-a',account.withGoogleAccountLabel('[{"title":"other","value":99}]','forged@example.com'));
  assert.equal(account.googleAccountLabel(f.row().additionalSettings),'owner@example.com');
  assert.equal(JSON.parse(f.row().additionalSettings)[0].value,99);
});
