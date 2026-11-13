import test from 'node:test';
import assert from 'node:assert/strict';
import {youtubeChannelUrl, googleAccountLabel, withGoogleAccountLabel, validAccountEmail} from '../libraries/helpers/src/utils/channel-account.ts';

test('channel links use only exact YouTube channel IDs', () => {
  assert.equal(youtubeChannelUrl('youtube','UCO6fS45rObf6onEIFbUs2Tw'), 'https://www.youtube.com/channel/UCO6fS45rObf6onEIFbUs2Tw');
  for (const id of ['javascript:alert(1)','UC../../../../','@numberflipworld711','']) assert.equal(youtubeChannelUrl('youtube',id),null);
  assert.equal(youtubeChannelUrl('instagram','UCO6fS45rObf6onEIFbUs2Tw'),null);
});
test('account labels preserve other settings and can be removed', () => {
  const original = '[{"title":"other","type":"checkbox","value":true}]';
  const next = withGoogleAccountLabel(original,' imseobgyu711@gmail.com ');
  assert.equal(googleAccountLabel(next),'imseobgyu711@gmail.com');
  assert.deepEqual(JSON.parse(next)[0],JSON.parse(original)[0]);
  assert.equal(withGoogleAccountLabel(next,''),original);
  assert.equal(googleAccountLabel(withGoogleAccountLabel(next,'second@example.com')),'second@example.com');
});
test('bad metadata cannot silently overwrite provider settings', () => {
  for (const raw of ['oops','{}','[null]','[4]']) { assert.equal(googleAccountLabel(raw),null); assert.throws(()=>withGoogleAccountLabel(raw,'owner@example.com')); }
  for (const email of ['a\nb@example.com','<img>@example.com','bad','a@example.com\r\nX: y']) { assert.equal(validAccountEmail(email),false); assert.throws(()=>withGoogleAccountLabel('[]',email)); }
});
