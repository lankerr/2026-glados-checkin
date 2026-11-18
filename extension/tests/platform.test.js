import test from 'node:test';
import assert from 'node:assert/strict';
import {selectExtensionAPI,restrictPersistentStorage} from '../platform.js';
test('uses standard browser namespace and falls back to Chrome',()=>{
 const browser={runtime:{id:'browser'}},chrome={runtime:{id:'chrome'}};
 assert.equal(selectExtensionAPI({browser,chrome}),browser);
 assert.equal(selectExtensionAPI({chrome}),chrome);
 assert.throws(()=>selectExtensionAPI({}));
});
test('missing Firefox storage access restriction fails closed',async()=>{
 await assert.rejects(restrictPersistentStorage({storage:{local:{}}}),/unsupported/);
});
test('persistent storage requests exact trusted-context restriction',async()=>{
 let arg;await restrictPersistentStorage({storage:{local:{setAccessLevel:async a=>{arg=a}}}});
 assert.deepEqual(arg,{accessLevel:'TRUSTED_CONTEXTS'});
});
test('browser protection rejection is never silently bypassed',async()=>{
 await assert.rejects(restrictPersistentStorage({storage:{local:{setAccessLevel:async()=>{throw Error('denied')}}}}),/denied/);
});
