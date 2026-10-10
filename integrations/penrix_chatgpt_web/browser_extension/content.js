(() => {
  'use strict';
  if (window.top !== window || document.getElementById('penrix-webcodex-panel')) return;
  const chat = () => location.pathname.match(/^\/c\/([A-Za-z0-9_-]+)$/)?.[1];
  let connectedChat = null, inFlight = null, ticking = false, lastState = null;
  let humanBaseline = new Set();
  const host = document.createElement('div');
  host.id = 'penrix-webcodex-panel';
  host.setAttribute('data-webcodex-build','20261010-paragraph-lines');
  host.style.cssText = 'position:fixed;right:16px;bottom:155px;z-index:2147483645';
  const root = host.attachShadow({mode:'open'});
  const style = document.createElement('style');
  style.textContent = ':host{font:13px/1.5 system-ui;color:#19322d}section{width:320px;max-width:calc(100vw - 48px);background:#fff;border:1px solid #9ab8af;border-radius:14px;box-shadow:0 6px 24px #0002;padding:14px}h2{margin:0 0 8px;font-size:16px}p,pre{white-space:pre-wrap;overflow-wrap:anywhere}pre{max-height:25vh;overflow:auto;font:12px/1.5 system-ui;background:#f5f8f7;padding:8px}textarea{width:100%;box-sizing:border-box;min-height:72px;font:inherit;border:1px solid #aabfb7;border-radius:8px;padding:8px}button{font:inherit;border:1px solid #aabfb7;border-radius:8px;padding:6px 10px;background:#edf6f2;color:inherit;cursor:pointer;margin:4px 4px 0 0}button:disabled{opacity:.5;cursor:default}[hidden]{display:none}';
  const panel = document.createElement('section');
  panel.setAttribute('aria-label','WebCodex 项目执行');
  const heading = document.createElement('h2'); heading.textContent = 'WebCodex';
  const status = document.createElement('p'); status.textContent = '本地服务就绪后，连接这个聊天';
  const task = document.createElement('textarea'); task.setAttribute('aria-label','WebCodex 任务或纠正'); task.placeholder = '输入任务或纠正；留空则使用聊天中最后一条你的消息';
  const result = document.createElement('pre'); result.hidden = true;
  const connect = button('连接项目', async () => {
    turns(); composer(); humans(); // Validate the current DOM before granting this tab work.
    const s = await rpc('connect'); connectedChat = chat(); humanBaseline = new Set(humans().map(m=>m.id)); render(s);
  });
  const start = button('开始 / 恢复', async () => {
    if (busy()) throw new Error('请等待当前 ChatGPT 回复完成');
    const instruction = task.value.trim() || latestHuman();
    if (!instruction) throw new Error('请输入任务');
    inFlight = null;
    humanBaseline = new Set(humans().map(m=>m.id));
    render(await rpc('start',{task:instruction}));
    task.value = '';
  });
  const pause = button('暂停', async () => {render(await rpc('pause')); inFlight = null;});
  const shutdown = button('关闭本地服务', async () => {
    if (!window.confirm('请先暂停并等待当前调用结束。关闭本地服务会停止 Server/Runner；工作状态保留，运行中的 Job 可能中断。现在关闭？')) return;
    await rpc('shutdown'); connectedChat = null; status.textContent = '本地服务已关闭；下次启动后恢复原 Session';
  });
  const toggle = button('WebCodex', async () => {panel.hidden = !panel.hidden;});
  panel.append(heading,status,task,connect,start,pause,shutdown,result);
  root.append(style,panel,toggle); document.body.append(host);

  function button(text, action) {
    const b = document.createElement('button'); b.textContent = text;
    b.addEventListener('click', async event => {
      if (!event.isTrusted) return;
      b.disabled = true;
      try {await action();} catch(error) {status.textContent = error.message;} finally {b.disabled = false;}
    });
    return b;
  }
  function rpc(operation, values={}) {
    return new Promise((resolve,reject)=>chrome.runtime.sendMessage({source:'penrix-webcodex',operation,...values}, response=>{
      const error = chrome.runtime.lastError;
      if (error || !response?.ok) reject(new Error(error?.message || response?.error || '浏览器连接已中断'));
      else resolve(response.result);
    }));
  }
  function render(s) {
    lastState = s;
    status.textContent = s.detail + '\n项目：' + s.project + (s.session_id ? '\nSession：' + s.session_id : '') + (s.real_test ? '\n真实测试模式：回复完成后至少冷却 30 秒' : '');
    result.textContent = s.final || ''; result.hidden = !s.final;
  }
  function turns() {
    // Observed on the owner's 2026-10-09 DOM; independently corroborated rollout hooks.
    const found = [...document.querySelectorAll('[data-talvt-turn-state]')];
    if (!found.length) throw new Error('未识别到当前聊天消息结构；已停止自动发送');
    return found;
  }
  function assistants() {
    return turns().flatMap(turn => [...turn.querySelectorAll('[data-chatgpt-search-unit-key$=":assistant"]')].map(unit=>({
      id:WebCodexProtocol.messageIdentity(unit.getAttribute('data-chatgpt-search-message-ids')),
      role:'assistant', complete:turn.getAttribute('data-talvt-turn-state') === 'complete',
      codes:[...unit.querySelectorAll('pre')].map(pre=>(pre.querySelector('code') || pre).textContent)
    })));
  }
  function latestHuman() {
    return humans().filter(m=>!m.text.startsWith('[WebCodex controller request:')).at(-1)?.text || '';
  }
  function humans() {
    return [...document.querySelectorAll('[data-chatgpt-search-unit-key$=":user"]')].map(e=>({
      id:WebCodexProtocol.messageIdentity(e.getAttribute('data-chatgpt-search-message-ids')),text:e.textContent.trim()
    }));
  }
  function checkHumanMessages() {
    for (const message of humans()) {
      if (humanBaseline.has(message.id)) continue;
      humanBaseline.add(message.id);
      if (!message.text.startsWith('[WebCodex controller request:')) throw new Error('收到你的新消息，已暂停执行；回复完成后点击恢复以吸收纠正');
    }
  }
  function composer() {
    const inputs = [...document.querySelectorAll('[data-composer-markdown][contenteditable="true"]')].filter(e=>e.getClientRects().length);
    if (inputs.length !== 1) throw new Error('无法确定唯一聊天输入框；已停止自动发送');
    return inputs[0];
  }
  function composerText(input) {
    // ChatGPT's ProseMirror creates one P per inserted logical line. innerText
    // adds paragraph-spacing newlines; textContent on the whole editor joins lines.
    const paragraphs = [...(input.children || [])];
    return paragraphs.length && paragraphs.every(e=>e.tagName === 'P')
      ? paragraphs.map(e=>e.textContent).join('\n') : input.innerText;
  }
  function busy() {
    return turns().some(t=>t.getAttribute('data-talvt-turn-state') !== 'complete') ||
      [...document.querySelectorAll('button[aria-label]')].some(b=>/^(停止|Stop)( generating| streaming|生成)?$/.test(b.getAttribute('aria-label')));
  }
  function pageBlocked() {
    if (document.querySelector('iframe[src*="challenges.cloudflare.com"],iframe[src*="recaptcha"]')) return true;
    return [...document.querySelectorAll('[role="alert"],[role="dialog"]')].some(e=>/too many requests|rate limit|unusual activity|verify you are human|异常活动|请求过多|达到.*限制|验证码/i.test(e.textContent));
  }
  async function waitFor(predicate, timeout) {
    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {
      const value = predicate(); if (value) return value;
      await new Promise(resolve=>setTimeout(resolve,200));
    }
    throw new Error('页面未在等待期限内就绪；不会重试发送');
  }
  async function deliver(request) {
    if (busy()) return; // No claim or send while an earlier reply is incomplete.
    const input = composer();
    if (input.textContent.trim()) throw new Error('输入框有未发送文字；请先处理，WebCodex 不会覆盖');
    const baseline = new Set(assistants().map(m=>m.id));
    await rpc('claim',{id:request.id}); // Crossing this fence forbids another Send.
    inFlight = {id:request.id,baseline,at:Date.now()};
    input.focus();
    if (!document.execCommand('insertText',false,request.prompt)) throw new Error('聊天输入框未接受内容；请求已领取，不会重发');
    const send = await waitFor(()=>[...input.closest('form').querySelectorAll('button[aria-label]')].find(b=>/^(发送|Send)( message)?$/.test(b.getAttribute('aria-label')) && !b.disabled && b.getAttribute('aria-disabled') !== 'true'),10000);
    // Pause/navigation can happen during composer readiness.
    const current = await rpc('status');
    if (current.state !== 'running' || current.request?.id !== request.id || chat() !== connectedChat) throw new Error('发送前工作已暂停或切换');
    checkHumanMessages();
    if (busy() || pageBlocked() || composerText(input).trim() !== request.prompt.trim()) throw new Error('发送前页面或输入内容已改变；已停止，不会重发');
    send.click();
  }
  async function tick() {
    if (ticking || !connectedChat) return;
    ticking = true;
    try {
      if (chat() !== connectedChat) {connectedChat = null; status.textContent = '已切换聊天，请重新连接'; return;}
      if (pageBlocked()) throw new Error('检测到限流或验证，已停止；不会自动重试');
      const s = await rpc('status'); render(s);
      if (s.state !== 'running') {inFlight = null; return;}
      checkHumanMessages();
      if (inFlight) {
        if (!s.request || s.request.id !== inFlight.id) throw new Error('当前请求已失效，停止发送');
        if (Date.now() - inFlight.at > 600000) throw new Error('回复结果不明；请核对当前聊天');
        for (const message of assistants()) {
          const envelope = WebCodexProtocol.completedEnvelope(message,inFlight.baseline,inFlight.id);
          if (envelope) {
            const id = inFlight.id; inFlight = null; // Never repeat a reply POST after an uncertain result.
            render(await rpc('reply',{id,text:JSON.stringify(envelope)}));
            break;
          }
        }
      } else if (s.request?.delivery === 'ready') await deliver(s.request);
      else if (s.request?.delivery === 'claimed') throw new Error('上次请求已领取；刷新后不能重发，请核对聊天并恢复');
    } catch(error) {
      status.textContent = error.message;
      try {await rpc('pause',{reason:error.message});} catch { /* Connection failure stays visible. */ }
      connectedChat = null; inFlight = null;
    } finally {ticking = false;}
  }
  setInterval(tick,1000);
})();
