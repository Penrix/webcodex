'use strict';
const BASE = 'http://127.0.0.1:17842';
const paths = new Set(['/status','/start','/claim','/reply','/pause','/shutdown']);
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
  if (message.operation === 'connect') {
    const paired = await request('/pair', {});
    // Credential stays in the service worker/session storage, never returned to the page.
    const status = await request('/status', {conversation}, paired.token);
    await chrome.storage.session.set({connection:{token:paired.token,tabId:sender.tab.id,conversation}});
    return status;
  }
  const {connection} = await chrome.storage.session.get('connection');
  if (!connection || connection.tabId !== sender.tab.id || connection.conversation !== conversation) throw new Error('请先连接这个聊天和本地项目');
  const path = '/' + message.operation;
  if (!paths.has(path)) throw new Error('Unknown operation');
  const body = {conversation};
  for (const key of ['task','id','text','reason']) if (message[key] !== undefined) body[key] = message[key];
  return request(path, body, connection.token);
}
chrome.runtime.onMessage.addListener((message,sender,reply) => {
  if (message?.source !== 'penrix-webcodex') return false;
  handle(message,sender).then(result=>reply({ok:true,result})).catch(error=>reply({ok:false,error:error.message}));
  return true;
});
