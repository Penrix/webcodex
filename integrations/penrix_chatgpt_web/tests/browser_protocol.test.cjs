const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const file = path.join(__dirname, '../browser_extension/protocol.js');
test('browser protocol is present', () => assert.equal(fs.existsSync(file), true));
test('only matching completed new assistant envelope is admitted', () => {
  const p = require(file);
  const text = JSON.stringify({request_id: 'current', action: {kind: 'final',tool:null,params:null,text:'ok'}});
  assert.equal(p.completedEnvelope({id:'new',role:'assistant',complete:false,codes:[text]}, new Set(['old']), 'current'), null);
  assert.equal(p.completedEnvelope({id:'old',role:'assistant',complete:true,codes:[text]}, new Set(['old']), 'current'), null);
  assert.equal(p.completedEnvelope({id:'new',role:'user',complete:true,codes:[text]}, new Set(), 'current'), null);
  assert.equal(p.completedEnvelope({id:'new',role:'assistant',complete:true,codes:[text.replace('current','stale')]}, new Set(), 'current'), null);
  assert.deepEqual(p.completedEnvelope({id:'new',role:'assistant',complete:true,codes:[text]}, new Set(), 'current'), JSON.parse(text));
});
test('multiple code proposals and extra envelope fields cannot execute', () => {
  const p = require(file);
  const text=JSON.stringify({request_id:'r',action:{kind:'final',tool:null,params:null,text:'ok'}});
  assert.equal(p.completedEnvelope({id:'new',role:'assistant',complete:true,codes:[text,text]},new Set(),'r'),null);
  assert.equal(p.completedEnvelope({id:'new',role:'assistant',complete:true,codes:[JSON.stringify({...JSON.parse(text), extra:true})]},new Set(),'r'),null);
});
test('native message identity must have one unique ID, never select an arbitrary member', () => {
  const p = require(file);
  assert.equal(p.messageIdentity('id-one id-one'), 'id-one');
  assert.throws(()=>p.messageIdentity('id-one id-two'), /identity/i);
  assert.throws(()=>p.messageIdentity(null), /identity/i);
});
