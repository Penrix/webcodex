(() => {
  'use strict';
  if (window.top !== window || document.getElementById('penrix-webcodex-panel')) return;
  const chat = () => location.pathname.match(/^\/c\/([A-Za-z0-9_-]+)$/)?.[1];
  let connectedChat = null, inFlight = null, ticking = false, lastState = null;
  let humanBaseline = new Set();
  let displayedChat = chat();
  const host = document.createElement('div');
  host.id = 'penrix-webcodex-panel';
  host.setAttribute('data-webcodex-build','20261012-collapsed-dock');
  const root = host.attachShadow({mode:'open'});
  const style = document.createElement('style');
  style.textContent = `
    :host{position:fixed;top:8px;left:8px;bottom:8px;width:min(var(--panel-width,520px),calc(100vw - 656px));max-width:calc(100vw - 16px);z-index:30;font:14px/1.6 system-ui;color:#19322d;pointer-events:none}
    :host([data-collapsed]){top:40%;left:0;bottom:auto;width:auto}
    .launcher{writing-mode:vertical-rl;padding:14px 7px;border-radius:0 9px 9px 0;box-shadow:0 2px 8px #183b291a}
    *{box-sizing:border-box}[hidden]{display:none!important}
    .panel{height:100%;display:flex;flex-direction:column;gap:14px;background:#fff;border:1px solid #c9d7d2;border-radius:16px;box-shadow:0 12px 48px #183b2926;padding:20px;pointer-events:auto;position:relative;overflow-y:auto;overscroll-behavior:contain}
    .header{display:flex;align-items:center;justify-content:space-between;padding-bottom:10px;border-bottom:1px solid #e7eeea}
    h2{font-size:20px;letter-spacing:-.4px;margin:0}p{margin:0;white-space:pre-wrap;overflow-wrap:anywhere}
    .status{padding:10px 12px;background:#f2f7f4;border-left:3px solid #82a797;border-radius:4px;font-size:13px}
    .help,.retention{font-size:12px;line-height:1.6;color:#64766e}.help{margin-top:5px}
    .history{flex:1;min-height:100px;overflow:auto;overscroll-behavior:contain;padding-right:6px}
    .empty{padding:22px 4px;color:#64766e}.entry{padding:0 0 20px;margin-bottom:18px;border-bottom:1px solid #e4ece7}
    .meta{font-size:11px;color:#76857d;margin-bottom:8px}.speaker{font-size:12px;font-weight:650;margin:10px 0 5px}
    .message{white-space:pre-wrap;overflow-wrap:anywhere;font-size:14px;line-height:1.75}.answer{border-left:2px solid #c9dbd2;padding-left:12px}
    .pending{color:#738178;font-size:13px;white-space:pre-wrap}.compose{display:flex;flex-direction:column;gap:8px}
    label{font-weight:600;font-size:13px}textarea{width:100%;height:clamp(170px,27vh,300px);min-height:140px;max-height:45vh;resize:vertical;padding:14px;font:15px/1.75 system-ui;color:#19322d;background:#fff;border:1px solid #b5c9bf;border-radius:10px}
    textarea:focus{outline:2px solid #cce6d8;outline-offset:1px;border-color:#527e68}
    .actions{display:flex;gap:8px;flex-wrap:wrap}button{font:13px/1.5 system-ui;border:1px solid #c3d4cb;border-radius:8px;padding:8px 12px;background:#fff;color:#284a3b;cursor:pointer;pointer-events:auto}
    button:hover{background:#f0f6f2}button.primary{background:#245c43;border-color:#245c43;color:white;flex:1}button.primary:hover{background:#184b34}button:disabled{opacity:.5;cursor:default}
    summary{font-size:12px;color:#607669;cursor:pointer}details p{font-size:12px;padding:8px 0}details button{margin:8px 6px 0 0}
    .project{font:11px/1.5 system-ui;white-space:pre-wrap;overflow-wrap:anywhere;color:#64766e;max-height:80px;overflow:auto}
    .result{font:14px/1.75 system-ui;white-space:pre-wrap;overflow:auto;max-height:25vh;overflow-wrap:anywhere}
    .resize{position:absolute;right:0;top:12px;bottom:12px;width:9px;cursor:ew-resize;touch-action:none;pointer-events:auto;border-radius:8px}.resize:hover,.resize:focus{background:#b6d5c5;outline:none}
    @media(max-width:1100px){:host{width:min(var(--panel-width,520px),calc(100vw - 16px))}.resize{display:none}}
    @media(max-width:700px){.panel{padding:16px;gap:10px}textarea{height:180px;min-height:120px}}
    @media(max-height:650px){.panel{gap:8px;padding:14px}textarea{height:140px;min-height:90px}.history{min-height:60px}.retention{display:none}}
  `;
  const panel = document.createElement('section');
  panel.setAttribute('aria-label','WebCodex 项目执行'); panel.className = 'panel';
  const heading = document.createElement('h2'); heading.textContent = 'WebCodex';
  const status = document.createElement('p'); status.className = 'status'; status.textContent = '先启动本地服务，再连接项目';
  const help = document.createElement('div'); help.className = 'help'; help.textContent = '在这里写任务；也可留空，使用网页里你最后一条消息。回复仍由网页 ChatGPT 生成。';
  const historyView = document.createElement('div'); historyView.className = 'history'; historyView.setAttribute('aria-label','任务与回复记录');
  const retention = document.createElement('div'); retention.className = 'retention'; retention.textContent = '本机保存最近 30 条任务与最终回复；完整逐轮对话在 ChatGPT 对话区查看。';
  let historySignature = '';
  const projectDetails = document.createElement('details');
  const projectSummary = document.createElement('summary'); projectSummary.textContent = '项目与会话信息';
  const projectInfo = document.createElement('div'); projectInfo.className = 'project';
  projectDetails.append(projectSummary,projectInfo);
  const label = document.createElement('label'); label.textContent = '新任务 / 纠正'; label.htmlFor = 'webcodex-task';
  const task = document.createElement('textarea'); task.id = 'webcodex-task'; task.setAttribute('aria-label','WebCodex 任务或纠正'); task.placeholder = '描述你要完成的工作，可以粘贴多段需求……';
  const result = document.createElement('pre'); result.className = 'result'; result.hidden = true;
  const connect = button('连接工作区', async () => {
    turns(); humans(); // Connection grants no Send; composer readiness belongs to execution.
    const s = await rpc('connect'); connectedChat = chat(); humanBaseline = new Set(humans().map(m=>m.id)); render(s);
  });
  const transfer = button('转移到本聊天', async () => {
    turns(); humans();
    const s = await rpc('transfer');
    connectedChat = chat(); inFlight = null;
    humanBaseline = new Set(humans().map(m=>m.id)); render(s);
  });
  const start = button('开始 / 恢复', async () => {
    const targetChat = chat();
    await waitFor(composer,10000);
    if(chat()!==targetChat) throw new Error('已切换聊天；请在当前聊天重新点击开始');
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
  function collapse(closed) {
    panel.hidden = closed; toggle.hidden = !closed;
    if (closed) host.setAttribute('data-collapsed',''); else host.removeAttribute('data-collapsed');
  }
  const toggle = button('WebCodex', async () => collapse(false)); toggle.className = 'launcher';
  toggle.title = '打开 WebCodex 任务面板；不会开始任务或发送消息';
  const shrink = button('收起', async () => collapse(true)); shrink.title = '收起侧栏；正在编辑的任务和执行状态会保留';
  start.className = 'primary';
  connect.title = '把当前聊天连接到启动器选定的本地项目；不会开始任务或发送消息';
  start.title = '执行上方任务；恢复时沿用原 Session，先读取当前项目状态';
  pause.title = '停止下一轮自动发送；已经开始的本地工具调用会先结束';
  transfer.title = '把同一项目和 Session 转移到当前聊天；旧执行必须先暂停，转移后仍需点击开始';
  shutdown.title = '退出本地 WebCodex 服务；保留项目和 Session，下次启动可以恢复';
  const other = document.createElement('details');
  const summary = document.createElement('summary'); summary.textContent = '其他操作（换聊天 / 退出服务）';
  other.append(summary,transfer,shutdown);
  const header = document.createElement('div'); header.className = 'header'; header.append(heading,shrink);
  const compose = document.createElement('div'); compose.className = 'compose'; compose.append(label,task,help);
  const actions = document.createElement('div'); actions.className = 'actions'; actions.append(connect,start,pause);
  const resize = document.createElement('div'); resize.className = 'resize'; resize.tabIndex = 0;
  resize.setAttribute('role','separator'); resize.setAttribute('aria-label','调整任务面板宽度'); resize.setAttribute('aria-orientation','vertical');
  // Reserve space in the observed ChatGPT #root, never restyle another extension.
  // Narrow screens use an explicitly opened drawer; Prompt Shelf (z-index 40)
  // remains above it and its right-hand launcher is never covered while closed.
  const dockStyle = document.createElement('style');
  function setWidth(width) {
    const value = Math.max(360,Math.min(width,900))+'px';
    host.style.setProperty('--panel-width',value);
    dockStyle.textContent = `@media(min-width:1101px){body:has(> #penrix-webcodex-panel:not([data-collapsed])) > #root{margin-left:calc(min(${value},100vw - 656px) + 24px);width:calc(100% - min(${value},100vw - 656px) - 24px)}}`;
  }
  setWidth(520);
  let dragging = null;
  resize.addEventListener('pointerdown',event=>{dragging = {x:event.clientX,width:host.getBoundingClientRect().width};resize.setPointerCapture(event.pointerId);});
  resize.addEventListener('pointermove',event=>{if(dragging)setWidth(dragging.width+event.clientX-dragging.x);});
  resize.addEventListener('pointerup',()=>{dragging=null;});
  resize.addEventListener('pointercancel',()=>{dragging=null;});
  resize.addEventListener('keydown',event=>{if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();setWidth(host.getBoundingClientRect().width+(event.key==='ArrowRight'?20:-20));}});
  panel.append(resize,header,status,projectDetails,historyView,retention,compose,actions,other,result);
  collapse(true); // Before insertion: no flash of a full panel on every chat load.
  root.append(style,panel,toggle); document.body.append(dockStyle,host);

  function button(text, action) {
    const b = document.createElement('button'); b.textContent = text;
    b.addEventListener('click', async event => {
      if (!event.isTrusted) return;
      const targetChat = chat();
      b.disabled = true;
      try {await action();} catch(error) {if(chat()===targetChat)status.textContent = error.message;} finally {b.disabled = false;}
    });
    return b;
  }
  function rpc(operation, values={}) {
    const targetChat = chat();
    return new Promise((resolve,reject)=>chrome.runtime.sendMessage({source:'penrix-webcodex',operation,...values}, response=>{
      if(chat()!==targetChat) {reject(new Error('已切换聊天；忽略原聊天的延迟响应'));return;}
      const error = chrome.runtime.lastError;
      if (error || !response?.ok) reject(new Error(error?.message || response?.error || '浏览器连接已中断'));
      else resolve(response.result);
    }));
  }
  function render(s) {
    lastState = s;
    status.textContent = s.detail + (s.real_test ? '\n测试模式：回复完成后至少等待 30 秒' : '') + (s.history_error ? '\n'+s.history_error : '');
    projectInfo.textContent = (s.workspace_root ? '操作范围：' + s.workspace_root + '\n' : '') + '项目：' + s.project + (s.session_id ? '\nSession：'+s.session_id : '');
    result.textContent = s.final || ''; result.hidden = !s.final || !!s.history?.length;
    const history = s.history || [];
    const signature = JSON.stringify(history);
    if (signature === historySignature) return;
    historySignature = signature;
    const nearBottom = historyView.scrollHeight-historyView.scrollTop-historyView.clientHeight < 40;
    historyView.replaceChildren();
    if (!history.length) {
      const empty = document.createElement('div'); empty.className = 'empty';
      empty.textContent = '任务与完成回复会保存在这里。\n先连接项目，再输入任务并开始。'; historyView.append(empty);
    }
    for (const item of history) {
      const entry = document.createElement('article'); entry.className = 'entry';
      const meta = document.createElement('div'); meta.className = 'meta';
      const names = {running:'执行中',completed:'已完成',paused:'已暂停',pausing:'正在暂停',idle:'待开始'};
      meta.textContent = new Date(item.at).toLocaleString()+' · '+(names[item.state] || item.state);
      const user = document.createElement('div'); user.className = 'speaker'; user.textContent = '你的任务';
      const instruction = document.createElement('div'); instruction.className = 'message'; instruction.textContent = item.task;
      const assistant = document.createElement('div'); assistant.className = 'speaker'; assistant.textContent = 'ChatGPT / WebCodex';
      const answer = document.createElement('div'); answer.className = item.result ? 'message answer' : 'pending';
      answer.textContent = item.result ? item.result+(item.result_truncated?'\n[此回复的本机记录已截断；完整回复请查看网页对话]':'') : (item.detail || '等待执行结果');
      entry.append(meta,user,instruction,assistant,answer); historyView.append(entry);
    }
    if (nearBottom || history.length === 1) historyView.scrollTop = historyView.scrollHeight;
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
    if (inputs.length > 1) throw new Error('检测到 ' + inputs.length + ' 个聊天输入框；为避免发错位置，已停止');
    return inputs[0] || null; // Native ChatGPT can temporarily unmount its composer.
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
    const input = await waitFor(composer,10000);
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
    if (chat() !== displayedChat) {
      displayedChat = chat(); connectedChat = null; inFlight = null;
      historySignature = ''; render({detail:'已切换聊天；请重新连接工作区',project:'尚未连接',history:[]});
      loadHistory(displayedChat);
    }
    if (ticking || !connectedChat) return;
    const targetChat = chat();
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
      if(chat()!==targetChat) return;
      status.textContent = error.message;
      try {await rpc('pause',{reason:error.message});} catch { /* Connection failure stays visible. */ }
      connectedChat = null; inFlight = null;
    } finally {ticking = false;}
  }
  render({detail:'先启动本地服务，再连接项目',project:'尚未连接',history:[]});
  function loadHistory(targetChat) {
    rpc('history').then(s=>{if(!connectedChat && chat()===targetChat)render(s);}).catch(()=>{
      if(!connectedChat && chat()===targetChat)status.textContent='本机记录暂未读取成功；可先连接项目';
    });
  }
  loadHistory(displayedChat);
  setInterval(tick,1000);
})();
