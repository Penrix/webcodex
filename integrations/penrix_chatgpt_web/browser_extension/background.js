'use strict';
const BASE = 'http://127.0.0.1:17842';
const paths = new Set(['/status','/start','/claim','/reply','/pause','/shutdown']);
let bindingChange = Promise.resolve();
let historyChange = Promise.resolve();
async function withHistory(status, conversation, task) {
  // Storage mutations serialize independently of HTTP, without delaying pause requests.
  const operation = historyChange.then(async()=>{
    const stored = await chrome.storage.local.get('taskHistory');
    let history = Array.isArray(stored.taskHistory) ? stored.taskHistory : [];
    const previous = JSON.stringify(history);
    const matches = item => item.project === status.project && item.conversation === conversation;
    let item = history.find(item=>matches(item) && item.run_id === status.run_id);
    if (typeof task === 'string' && typeof status.run_id === 'string' && !item) {
      item = {project:status.project,conversation,run_id:status.run_id,task,at:Date.now(),state:status.state,result:''};
      history.push(item);
    }
    if (item && !(item.state === 'completed' && status.state !== 'completed') &&
        !(Number.isInteger(status.snapshot_seq) && Number.isInteger(item.snapshot_seq) && status.snapshot_seq < item.snapshot_seq)) {
      item.snapshot_seq = status.snapshot_seq;
      item.state = status.state;
      item.detail = status.detail || '';
      if (status.state === 'completed' && typeof status.final === 'string') {
        item.result = status.final.slice(0,32000);
        item.result_truncated = status.final.length > 32000;
      }
    } else if (!status.run_id) {
      for (const old of history.filter(matches)) {
        if (old.state === 'running' || old.state === 'pausing') {
          old.state = 'paused'; old.detail = '本地服务已重启；请核对项目状态后恢复';
        }
      }
    }
    history = history.slice(-30);
    while (history.length && new TextEncoder().encode(JSON.stringify(history)).length > 4*1024*1024) history.shift();
    if (JSON.stringify(history) !== previous) await chrome.storage.local.set({taskHistory:history});
    return {...status,history:history.filter(matches)};
  });
  historyChange = operation.catch(()=>{});
  try {return await operation;} catch {
    return {...status,history_error:'本机任务记录保存失败；当前执行仍有效，请勿重复开始任务'};
  }
}
function chatFor(sender) {
  if (sender.id !== chrome.runtime.id || !sender.tab || sender.frameId !== 0) throw new Error('Untrusted browser sender');
  const url = new URL(sender.url);
  const match = url.pathname.match(/^\/c\/([A-Za-z0-9_-]{1,128})$/);
  if (url.origin !== 'https://chatgpt.com' || !match) throw new Error('请打开一个已有的 ChatGPT 对话');
  return match[1];
}
async function request(path, body, token) {
  const response = await fetch(BASE + path, {
    method:'POST', redirect:'error', credentials:'omit',
    headers:{'Content-Type':'application/json', ...(token ? {Authorization:'Bearer '+token} : {})},
    body:JSON.stringify(body), signal:AbortSignal.timeout(12000)
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Local WebCodex request failed');
  return result;
}
async function handle(message, sender) {
  if (message.source !== 'penrix-webcodex') throw new Error('Unknown message');
  const conversation = chatFor(sender);
  if (message.operation === 'history') {
    await historyChange;
    const stored = await chrome.storage.local.get('taskHistory');
    const all = Array.isArray(stored.taskHistory) ? stored.taskHistory.filter(item=>item.conversation === conversation) : [];
    const project = all.at(-1)?.project;
    return {state:'idle',project:project || '尚未连接',history:all.filter(item=>item.project === project),
            detail:'尚未连接本地服务；可以先查看本机保存的记录'};
  }
  if (message.operation === 'connect' || message.operation === 'transfer') {
    const paired = await request('/pair', {});
    // Credential stays in the service worker/session storage, never returned to the page.
    const status = await request(message.operation === 'transfer' ? '/transfer' : '/status', {conversation}, paired.token);
    await chrome.storage.session.set({connection:{token:paired.token,tabId:sender.tab.id,conversation}});
    return withHistory(status,conversation);
  }
  const {connection} = await chrome.storage.session.get('connection');
  if (!connection || connection.tabId !== sender.tab.id || connection.conversation !== conversation) throw new Error('请先连接这个聊天和本地项目');
  const path = '/' + message.operation;
  if (!paths.has(path)) throw new Error('Unknown operation');
  const body = {conversation};
  for (const key of ['task','id','text','reason']) if (message[key] !== undefined) body[key] = message[key];
  const status = await request(path, body, connection.token);
  if (message.operation === 'start' && status.previous_run?.run_id) {
    const previous = await withHistory(status.previous_run,conversation);
    if (previous.history_error) status.history_error = previous.history_error;
  }
  return withHistory(status,conversation,message.operation === 'start' ? message.task : undefined);
}
chrome.runtime.onMessage.addListener((message,sender,reply) => {
  if (message?.source !== 'penrix-webcodex') return false;
  let result;
  if (message.operation === 'connect' || message.operation === 'transfer') {
    // Keep the server binding and storage update in the same handshake order.
    result = bindingChange.then(()=>handle(message,sender));
    bindingChange = result.catch(()=>{});
  } else result = handle(message,sender);
  result.then(value=>reply({ok:true,result:value})).catch(error=>reply({ok:false,error:error.message}));
  return true;
});
