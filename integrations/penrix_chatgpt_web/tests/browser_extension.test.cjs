// Unit-level simulated browser APIs/DOM. This is not live Chrome acceptance.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = name => fs.readFileSync(path.join(__dirname,'../browser_extension',name),'utf8');

function worker(store={}, requests=[], {rejectTransfer=false,beforeResponse=async()=>{},local={},serverStatus={state:'idle',project:'one'},storageFails=false}={}) {
  let listener;
  const chrome = {runtime:{id:'own-extension',onMessage:{addListener:f=>listener=f}}, storage:{session:{
    get:async()=>store,set:async value=>Object.assign(store,value)
  },local:{get:async()=>local,set:async value=>{if(storageFails)throw new Error('fixture quota failure');Object.assign(local,value);}}}};
  vm.runInNewContext(source('background.js'),{chrome,URL,AbortSignal,TextEncoder,fetch:async(url,options)=>{
    requests.push({url,options});
    await beforeResponse(url);
    if (rejectTransfer && url.endsWith('/transfer')) return {ok:false,json:async()=>({error:'old execution still active'})};
    return {ok:true,json:async()=>url.endsWith('/pair')?{token:'fixture-credential',project:'one'}:{...serverStatus}};
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

test('task and final reply persist across worker restart, isolate projects/chats and match exact runs',async()=>{
  const store={connection:{token:'fixture',tabId:12,conversation:'chat-one'}},local={};
  const serverStatus={state:'running',project:'one',run_id:'run-one',final:''};
  const w=worker(store,[],{local,serverStatus});
  await w.send({operation:'start',task:'Read the first file'},sender);
  serverStatus.state='completed';serverStatus.final='First file read';
  const finished=await w.send({operation:'status'},sender);
  assert.equal(finished.result.history[0].task,'Read the first file');
  assert.equal(finished.result.history[0].result,'First file read');
  const restored=worker(store,[],{local,serverStatus});
  assert.equal((await restored.send({operation:'status'},sender)).result.history.length,1);
  serverStatus.run_id='run-two';serverStatus.state='running';serverStatus.final='';
  await restored.send({operation:'start',task:'Read the second file'},sender);
  serverStatus.run_id='run-one';serverStatus.state='completed';serverStatus.final='Late first result';
  const late=(await restored.send({operation:'status'},sender)).result.history;
  assert.equal(late[0].result,'Late first result');assert.equal(late[1].result,'');
  serverStatus.project='another-project';
  assert.equal((await restored.send({operation:'status'},sender)).result.history.length,0);
  const another={...sender,tab:{id:13},url:'https://chatgpt.com/c/chat-two'};
  serverStatus.project='one';
  assert.equal((await restored.send({operation:'connect'},another)).result.history.length,0);
});

test('history has a global retention bound; storage failure reports loss without replaying start',async()=>{
  const store={connection:{token:'fixture',tabId:12,conversation:'chat-one'}},local={};
  const serverStatus={state:'running',project:'one',final:''};
  const w=worker(store,[],{local,serverStatus});
  for(let i=0;i<31;i++){serverStatus.run_id='run-'+i;await w.send({operation:'start',task:'task '+i},sender);}
  assert.equal(local.taskHistory.length,30);assert.equal(local.taskHistory[0].task,'task 1');
  const broken=worker(store,[],{local:{},serverStatus,storageFails:true});
  const response=await broken.send({operation:'start',task:'Do not retry'},sender);
  assert.equal(response.ok,true);assert.match(response.result.history_error,/保存失败/);
  assert.equal(broken.requests.filter(r=>r.url.endsWith('/start')).length,1);
});

test('saved history can be opened offline without connecting or contacting the service',async()=>{
  const local={taskHistory:[{project:'one',conversation:'chat-one',task:'Saved task',result:'Saved answer'},
                           {project:'two',conversation:'chat-two',task:'Other chat'}]};
  const w=worker({},[],{local});
  const viewed=await w.send({operation:'history'},sender);
  assert.equal(viewed.ok,true);assert.equal(viewed.result.history.length,1);
  assert.equal(viewed.result.history[0].result,'Saved answer');assert.equal(w.requests.length,0);
  assert.equal((await w.send({operation:'start',task:'No binding'},sender)).ok,false);
});

test('next start preserves an unpolled final and late status cannot downgrade it',async()=>{
  const store={connection:{token:'fixture',tabId:12,conversation:'chat-one'}};
  const local={taskHistory:[{project:'one',conversation:'chat-one',run_id:'old',task:'Old task',state:'running',result:''}]};
  const serverStatus={project:'one',run_id:'new',state:'running',snapshot_seq:4,
    previous_run:{project:'one',run_id:'old',state:'completed',final:'Unpolled final',snapshot_seq:3}};
  const w=worker(store,[],{local,serverStatus});
  const next=await w.send({operation:'start',task:'Next task'},sender);
  assert.equal(next.result.history[0].result,'Unpolled final');
  Object.assign(serverStatus,{run_id:'old',state:'running',snapshot_seq:2,previous_run:undefined});
  await w.send({operation:'status'},sender);
  assert.equal(local.taskHistory[0].state,'completed');
  Object.assign(serverStatus,{run_id:'new',state:'paused',snapshot_seq:6});
  await w.send({operation:'status'},sender);
  Object.assign(serverStatus,{state:'running',snapshot_seq:5});
  await w.send({operation:'status'},sender);
  assert.equal(local.taskHistory[1].state,'paused');
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
test('explicit transfer switches the bound tab only after the server accepts; old tab loses authority',async()=>{
  const store={connection:{token:'old',tabId:12,conversation:'chat-one'}};
  const next={...sender,tab:{id:13},url:'https://chatgpt.com/c/chat-two'};
  const rejected=worker(store,[],{rejectTransfer:true});
  assert.equal((await rejected.send({operation:'transfer'},next)).ok,false);
  assert.equal(store.connection.tabId,12);
  const admitted=worker(store);
  assert.equal((await admitted.send({operation:'transfer'},next)).ok,true);
  assert.equal(store.connection.tabId,13);
  assert.equal(store.connection.conversation,'chat-two');
  const before=admitted.requests.length;
  assert.equal((await admitted.send({operation:'start',task:'stale'},sender)).ok,false);
  assert.equal(admitted.requests.length,before);
  assert.equal(admitted.requests[1].url,'http://127.0.0.1:17842/transfer');
});

test('a delayed old connection response cannot overwrite a newer transfer binding',async()=>{
  let release, reached;
  const delayed = new Promise(resolve=>release=resolve);
  const ready = new Promise(resolve=>reached=resolve);
  const store={}, requests=[];
  const w=worker(store,requests,{beforeResponse:async url=>{
    if(url.endsWith('/status')) {reached();await delayed;}
  }});
  const old=w.send({operation:'connect'},sender);
  await ready;
  const next={...sender,tab:{id:13},url:'https://chatgpt.com/c/chat-two'};
  const moved=w.send({operation:'transfer'},next);
  await new Promise(setImmediate);
  release();
  assert.equal((await old).ok,true);
  assert.equal((await moved).ok,true);
  assert.equal(store.connection.conversation,'chat-two');
  assert.equal(store.connection.tabId,13);
  assert.equal((await w.send({operation:'start',task:'new task'},next)).ok,true);
});

function panel({blockedAtSend=false,ownerAtSend=false,missingTurns=false,claimed=false,paragraphComposer=false,alteredComposer=false,composerCount=1,deferStatus=false}={}) {
  let delayedStatus;
  const elements=[], calls=[];
  let tick, blocked=false, statusCalls=0, sends=0;
  class Element {
    constructor(tag){this.tag=tag;this.textContent='';this.value='';this.style={setProperty(){}};this.listeners={};this.attributes={};elements.push(this);}
    setAttribute(name,value){this.attributes[name]=value;} removeAttribute(name){delete this.attributes[name];} append(){} replaceChildren(){} attachShadow(){return new Element('shadow');}
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
      if(selector==='[data-composer-markdown][contenteditable="true"]') return Array(composerCount).fill(input);
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
    if(message.operation==='status' && deferStatus) {const old={...snapshot(),detail:'OLD CHAT A STATUS'};delayedStatus=()=>callback({ok:true,result:old});return;}
    callback({ok:true,result:snapshot()});
  }}};
  const window={};window.top=window;window.confirm=()=>true;
  const location={pathname:'/c/chat-one'};
  vm.runInNewContext(source('content.js'),{window,document,chrome,location,Date,Set,Promise,Error,
    WebCodexProtocol:require('../browser_extension/protocol.js'),setInterval:f=>tick=f,setTimeout});
  return {calls,elements,flushStatus:()=>delayedStatus(),setChat:value=>location.pathname='/c/'+value,setComposerCount:value=>composerCount=value,get sends(){return sends;},tick:()=>tick(),status:()=>elements.find(e=>e.tag==='p').textContent,
    click:async label=>elements.find(e=>e.tag==='button'&&e.textContent===label).listeners.click({isTrusted:true})};
}

test('panel starts collapsed; opening and closing preserve the draft without sending or starting work',async()=>{
  const p=panel();
  const host=p.elements.find(e=>e.id==='penrix-webcodex-panel');
  const view=p.elements.find(e=>e.tag==='section');
  const launcher=p.elements.find(e=>e.tag==='button'&&e.textContent==='WebCodex');
  const task=p.elements.find(e=>e.tag==='textarea');
  assert.equal(view.hidden,true);
  assert.equal(launcher.hidden,false);
  assert.equal(host.attributes['data-collapsed'],'');
  await p.click('WebCodex');
  assert.equal(view.hidden,false);
  task.value='Keep this unsent draft';
  await p.click('收起');await p.click('WebCodex');
  assert.equal(task.value,'Keep this unsent draft');
  assert.equal(p.calls.filter(c=>c.operation!=='history').length,0);
  assert.equal(p.sends,0);
});

test('SPA route changes load only the destination history even when offline and disconnect execution',async()=>{
  const p=panel();
  assert.equal(p.calls.filter(c=>c.operation==='history').length,1);
  p.setChat('chat-two');await p.tick();
  assert.equal(p.calls.filter(c=>c.operation==='history').length,2);
  assert.equal(p.sends,0);
  await p.click('连接工作区');p.setChat('chat-three');await p.tick();
  assert.equal(p.calls.filter(c=>c.operation==='history').length,3);
  assert.equal(p.calls.filter(c=>c.operation==='status').length,0);
});

test('delayed status from previous SPA route cannot render or pause the destination',async()=>{
  const p=panel({deferStatus:true});await p.click('连接工作区');
  const oldTick=p.tick();
  p.setChat('chat-two');await p.tick();await Promise.resolve();
  const before=p.status();p.flushStatus();await oldTick;
  assert.equal(p.status(),before);
  assert.equal(p.calls.filter(c=>c.operation==='pause').length,0);
});

test('pending composer wait cannot start work in a transferred destination chat',async()=>{
  const p=panel({composerCount:0});await p.click('连接工作区');
  const pending=p.click('开始 / 恢复');await Promise.resolve();
  p.setChat('chat-two');await p.tick();await p.click('转移到本聊天');
  p.setComposerCount(1);await pending;
  assert.equal(p.calls.filter(c=>c.operation==='start').length,0);
  assert.equal(p.sends,0);
});

test('connection does not require a mounted composer; execution waits for a unique input',async()=>{
  const p=panel({composerCount:0});
  await p.click('连接工作区');
  assert.equal(p.calls.filter(m=>m.operation==='connect').length,1);
  assert.equal(p.sends,0);
  const starting=p.click('开始 / 恢复');
  await Promise.resolve();
  assert.equal(p.calls.filter(m=>m.operation==='start').length,0);
  p.setComposerCount(1);
  await starting;await p.tick();
  assert.equal(p.sends,1);
});

test('two composers refuse execution before starting or claiming; buttons explain their effects',async()=>{
  const p=panel({composerCount:2});
  await p.click('连接工作区');
  await p.click('开始 / 恢复');
  assert.equal(p.calls.filter(m=>m.operation==='start'||m.operation==='claim').length,0);
  assert.equal(p.sends,0);
  assert.match(p.status(),/2.*输入框/);
  for(const label of ['连接工作区','开始 / 恢复','暂停','转移到本聊天','关闭本地服务']) {
    assert.ok(p.elements.find(e=>e.tag==='button'&&e.textContent===label).title);
  }
});
test('blocking page appearing during delivery prevents Send and pauses without retry',async()=>{
  const p=panel({blockedAtSend:true});
  await p.click('连接工作区');await p.click('开始 / 恢复');await p.tick();await p.tick();
  assert.equal(p.sends,0);
  assert.equal(p.calls.filter(m=>m.operation==='claim').length,1);
  assert.equal(p.calls.filter(m=>m.operation==='pause').length,1);
  assert.match(p.status(),/页面或输入内容已改变/);
});
test('owner correction during delivery prevents the stale Send',async()=>{
  const p=panel({ownerAtSend:true});
  await p.click('连接工作区');await p.click('开始 / 恢复');await p.tick();
  assert.equal(p.sends,0);assert.match(p.status(),/收到你的新消息/);
});
test('ChatGPT paragraph composer preserves exact logical lines despite doubled rendered separators',async()=>{
  const p=panel({paragraphComposer:true});
  await p.click('连接工作区');await p.click('开始 / 恢复');await p.tick();
  assert.equal(p.sends,1);
  assert.equal(p.calls.filter(m=>m.operation==='pause').length,0);
  const changed=panel({paragraphComposer:true,alteredComposer:true});
  await changed.click('连接工作区');await changed.click('开始 / 恢复');await changed.tick();
  assert.equal(changed.sends,0);
  assert.match(changed.status(),/页面或输入内容已改变/);
});
test('unknown DOM prevents connection; a claimed request after reload is never sent twice',async()=>{
  const unknown=panel({missingTurns:true});await unknown.click('连接工作区');
  assert.equal(unknown.calls.filter(m=>m.operation!=='history').length,0);assert.match(unknown.status(),/未识别/);
  const reloaded=panel({claimed:true});await reloaded.click('连接工作区');await reloaded.click('开始 / 恢复');await reloaded.tick();
  assert.equal(reloaded.sends,0);assert.match(reloaded.status(),/不能重发/);
});
test('transfer requires an explicit panel click and never starts or sends work automatically',async()=>{
  const p=panel();
  await p.click('转移到本聊天');await p.tick();
  assert.equal(p.calls.filter(m=>m.operation==='transfer').length,1);
  assert.equal(p.calls.filter(m=>m.operation==='start').length,0);
  assert.equal(p.sends,0);
});
