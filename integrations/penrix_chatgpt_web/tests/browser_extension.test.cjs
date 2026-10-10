// Unit-level simulated browser APIs/DOM. This is not live Chrome acceptance.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = name => fs.readFileSync(path.join(__dirname,'../browser_extension',name),'utf8');

function worker(store={}, requests=[]) {
  let listener;
  const chrome = {runtime:{id:'own-extension',onMessage:{addListener:f=>listener=f}}, storage:{session:{
    get:async()=>store,set:async value=>Object.assign(store,value)
  }}};
  vm.runInNewContext(source('background.js'),{chrome,URL,AbortSignal,fetch:async(url,options)=>{
    requests.push({url,options});
    return {ok:true,json:async()=>url.endsWith('/pair')?{token:'fixture-credential',project:'one'}:{state:'idle',project:'one'}};
  }});
  return {requests,send:(message,sender)=>new Promise(resolve=>listener({source:'penrix-webcodex',...message},sender,resolve))};
}
const sender = {id:'own-extension',tab:{id:12},frameId:0,url:'https://chatgpt.com/c/chat-one'};
test('background credential is isolated; only the bound top-level tab can use it after worker eviction', async()=>{
  const store = {}, requests = [];
  const first = worker(store,requests);
  const connected = await first.send({operation:'connect'},sender);
  assert.equal(connected.ok,true);
  assert.equal(JSON.stringify(connected).includes('fixture-credential'),false);
  const restored = worker(store,requests);
  assert.equal((await restored.send({operation:'status'},sender)).ok,true);
  const before=requests.length;
  for (const foreign of [{...sender,tab:{id:13}},{...sender,frameId:1},{...sender,id:'foreign'},{...sender,url:'https://attacker.invalid/c/chat-one'},{...sender,url:'https://chatgpt.com/c/other'}]) {
    assert.equal((await restored.send({operation:'start',task:'do not execute'},foreign)).ok,false);
  }
  assert.equal(requests.length,before);
  assert.equal(requests.at(-1).options.headers.Authorization,'Bearer fixture-credential');
});
test('background cannot be used as an arbitrary URL or operation proxy',async()=>{
  const w = worker({connection:{token:'fixture',tabId:12,conversation:'chat-one'}});
  assert.equal((await w.send({operation:'../../other',url:'https://attacker.invalid'},sender)).ok,false);
  assert.equal(w.requests.length,0);
  await w.send({operation:'status',url:'https://attacker.invalid',token:'attacker'},sender);
  assert.equal(w.requests[0].url,'http://127.0.0.1:17842/status');
  assert.equal(w.requests[0].options.body,JSON.stringify({conversation:'chat-one'}));
  assert.equal(w.requests[0].options.redirect,'error');
});

function panel({blockedAtSend=false,ownerAtSend=false,missingTurns=false,claimed=false,paragraphComposer=false,alteredComposer=false}={}) {
  const elements=[], calls=[];
  let tick, blocked=false, statusCalls=0, sends=0;
  class Element {
    constructor(tag){this.tag=tag;this.textContent='';this.value='';this.style={};this.listeners={};elements.push(this);}
    setAttribute(){} append(){} attachShadow(){return new Element('shadow');}
    addEventListener(name,f){this.listeners[name]=f;}
    getClientRects(){return [{}];} focus(){}
    get innerText(){return this.renderedText ?? this.textContent;}
  }
  const human = id=>({getAttribute:()=>id,textContent:'owner task'});
  const humans=[human('human-one')];
  const turn={getAttribute:()=> 'complete',querySelectorAll:()=>[]};
  const send={getAttribute:()=> 'Send',disabled:false,click:()=>sends++};
  const input=new Element('input'); input.closest=()=>({querySelectorAll:()=>[send]});
  const document={body:new Element('body'),getElementById:()=>null,createElement:tag=>new Element(tag),
    execCommand:(_cmd,_show,text)=>{
      input.textContent=text;
      if (paragraphComposer) {
        input.children=text.split('\n').map(line=>({tagName:'P',textContent:line,innerText:line || '\n'}));
        input.renderedText=input.children.map(p=>p.innerText).join('\n\n');
        if (alteredComposer) input.children.at(-1).textContent += ' changed';
      }
      return true;
    },
    querySelector:()=>null,querySelectorAll:selector=>{
      if(selector==='[data-talvt-turn-state]') return missingTurns?[]:[turn];
      if(selector==='[data-chatgpt-search-unit-key$=":user"]') return humans;
      if(selector==='[data-composer-markdown][contenteditable="true"]') return [input];
      if(selector==='button[aria-label]') return [];
      if(selector==='[role="alert"],[role="dialog"]') return blocked?[{textContent:'unusual activity'}]:[];
      throw new Error('Unexpected DOM query: '+selector);
    }};
  const request={id:'r',prompt:'[WebCodex controller request:r]\nfixture\n\n  indentation stays',delivery:claimed?'claimed':'ready'};
  let state='idle';
  const snapshot=()=>({state,detail:state,project:'one',request:state==='running'?request:null});
  const chrome={runtime:{sendMessage:(message,callback)=>{
    calls.push(message);
    if(message.operation==='start') state='running';
    if(message.operation==='status' && ++statusCalls===2) {
      blocked=blockedAtSend;
      if(ownerAtSend) humans.push(human('human-correction'));
    }
    if(message.operation==='claim') request.delivery='claimed';
    if(message.operation==='pause') state='paused';
    callback({ok:true,result:snapshot()});
  }}};
  const window={};window.top=window;window.confirm=()=>true;
  vm.runInNewContext(source('content.js'),{window,document,chrome,location:{pathname:'/c/chat-one'},Date,Set,Promise,Error,
    WebCodexProtocol:require('../browser_extension/protocol.js'),setInterval:f=>tick=f,setTimeout});
  return {calls,get sends(){return sends;},tick:()=>tick(),status:()=>elements.find(e=>e.tag==='p').textContent,
    click:async label=>elements.find(e=>e.tag==='button'&&e.textContent===label).listeners.click({isTrusted:true})};
}
test('blocking page appearing during delivery prevents Send and pauses without retry',async()=>{
  const p=panel({blockedAtSend:true});
  await p.click('连接项目');await p.click('开始 / 恢复');await p.tick();await p.tick();
  assert.equal(p.sends,0);
  assert.equal(p.calls.filter(m=>m.operation==='claim').length,1);
  assert.equal(p.calls.filter(m=>m.operation==='pause').length,1);
  assert.match(p.status(),/页面或输入内容已改变/);
});
test('owner correction during delivery prevents the stale Send',async()=>{
  const p=panel({ownerAtSend:true});
  await p.click('连接项目');await p.click('开始 / 恢复');await p.tick();
  assert.equal(p.sends,0);assert.match(p.status(),/收到你的新消息/);
});
test('ChatGPT paragraph composer preserves exact logical lines despite doubled rendered separators',async()=>{
  const p=panel({paragraphComposer:true});
  await p.click('连接项目');await p.click('开始 / 恢复');await p.tick();
  assert.equal(p.sends,1);
  assert.equal(p.calls.filter(m=>m.operation==='pause').length,0);
  const changed=panel({paragraphComposer:true,alteredComposer:true});
  await changed.click('连接项目');await changed.click('开始 / 恢复');await changed.tick();
  assert.equal(changed.sends,0);
  assert.match(changed.status(),/页面或输入内容已改变/);
});
test('unknown DOM prevents connection; a claimed request after reload is never sent twice',async()=>{
  const unknown=panel({missingTurns:true});await unknown.click('连接项目');
  assert.equal(unknown.calls.length,0);assert.match(unknown.status(),/未识别/);
  const reloaded=panel({claimed:true});await reloaded.click('连接项目');await reloaded.click('开始 / 恢复');await reloaded.tick();
  assert.equal(reloaded.sends,0);assert.match(reloaded.status(),/不能重发/);
});
