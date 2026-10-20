const $ = (selector, root = document) => root.querySelector(selector);
const e = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const paths = {
  dashboard:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  plans:'M8 4H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-3 M8 2h8v5H8z M7 12h10 M7 17h7',
  focus:'M12 3a9 9 0 1 0 9 9 M12 7v5l3 2 M17 2v6h6',
  knowledge:'M12 5C9 2 4 3 2 4v15c3-1 7-1 10 1 3-2 7-2 10-1V4c-2-1-7-2-10 1z M12 5v15',
  agent:'M12 3l2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z M20 2v4 M18 4h4',
  stats:'M4 20V11 M10 20V5 M16 20v-7 M22 20H2',
  community:'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M22 21v-2a4 4 0 0 0-3-3.9 M16 3.1a4 4 0 0 1 0 7.8',
  settings:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M9 2h6l1 4 4 1 2 5-3 3v4l-5 3-3-2-4 1-4-5 2-3-1-4 5-2z',
  arrow:'M5 12h14 M13 6l6 6-6 6',plus:'M12 5v14 M5 12h14',check:'M5 12l4 4L19 6',
  leaf:'M20 3C8 1 2 6 5 14c2 5 8 6 12 1 3-4 3-9 3-12z M4 21L15 9',
  trash:'M3 6h18 M9 6V3h6v3 M6 6l1 15h10l1-15 M10 10v7 M14 10v7',
  file:'M14 2H5v20h14V7z M14 2v6h5 M8 12h8 M8 16h6',close:'M6 6l12 12 M6 18L18 6',
  play:'M7 3l14 9-14 9z',send:'M22 2L9 15 M22 2l-7 20-6-7-7-6z',fire:'M12 2c1 5-5 6-5 11a5 5 0 0 0 10 0c0-3-2-5-2-5s0 4-3 4c-3-1 3-4 0-10z'
};
const icon = name => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name] || paths.leaf}"/></svg>`;
const art = `<svg class="hero-art" viewBox="0 0 400 280" aria-hidden="true"><ellipse cx="215" cy="239" rx="151" ry="17" fill="#d8e1c8"/><path d="M112 220l37-25 48 6 32-27 88 36-35 29-108 3z" fill="#b5c799"/><path d="M112 220v12l62 22 108-3 35-29v-12l-35 29-108 3z" fill="#9db685"/><path d="M208 218V92" stroke="#728f57" stroke-width="4"/><path d="M209 174c-77 9-83-49-86-63 55-2 84 18 86 63" fill="#99b579"/><path d="M209 146c69 6 83-49 83-69-61-3-84 25-83 69" fill="#809e62"/><path d="M209 117c-42-2-52-38-47-62 40 3 48 30 47 62" fill="#b5ca93"/><path d="M209 96c42-11 48-49 39-72-34 10-47 35-39 72" fill="#658b50"/><path d="M209 175l-61-43 M209 147l58-49 M209 117l-32-45 M209 95l28-51" stroke="#6b8d50" stroke-width="1.3" fill="none" opacity=".5"/><path d="M135 226v-37 M135 205c-21 1-26-16-26-24 19 0 26 10 26 24 M135 200c21 0 25-17 23-26-19 2-24 12-23 26" fill="#7d9b63" stroke="#7d9b63" stroke-width="2"/><path d="M262 226v-28 M262 213c-15-1-20-13-19-20 15 1 20 9 19 20 M262 207c15 0 20-14 17-20-13 2-19 11-17 20" fill="#a3bb85" stroke="#a3bb85" stroke-width="2"/><circle cx="108" cy="78" r="23" fill="#d9e4c7"/><circle cx="315" cy="162" r="6" fill="#bdcda6"/><path d="M316 52v14 M309 59h14" stroke="#a4bb86" stroke-width="2"/><path d="M92 156v10 M87 161h10" stroke="#9bb47c" stroke-width="2"/></svg>`;
const nav = [ ['dashboard','学习概览'],['plans','计划与任务'],['focus','专注空间'],['knowledge','知识库'],['agent','AI 学习教练'],['stats','成长记录'],['community','学习广场'] ];
const state = {user:null,stats:null,plans:[],docs:[],runs:[],cap:null,focus:null,page:'dashboard',authMode:'login',socket:null,messages:[],online:0,asking:false,selectedTask:null};
let toastTimer, renderToken = 0, reconnectTimer;

function toast(message) { $('#toast').textContent = message; $('#toast').classList.add('show'); clearTimeout(toastTimer); toastTimer = setTimeout(() => $('#toast').classList.remove('show'), 4000); }
async function api(path, options = {}) {
  const response = await fetch('/api' + path, {credentials:'same-origin', ...options, headers:{...(options.body && !(options.body instanceof FormData) ? {'Content-Type':'application/json'} : {}), ...options.headers}});
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    if (response.status === 401 && !path.startsWith('/auth/')) showAuth();
    throw new Error(typeof data.detail === 'string' ? data.detail : response.status === 422 ? '请检查输入长度、格式与必填项' : `请求失败 (${response.status})`);
  }
  return response.status === 204 ? null : response.json();
}
const post = (path, body = {}) => api(path, {method:'POST',body:JSON.stringify(body)});
function heading(eyebrow, title, subtitle, action = '') { return `<div class="page-heading"><div><p class="eyebrow">${eyebrow}</p><h1>${title}</h1><p class="subtitle">${subtitle}</p></div>${action}</div>`; }
function button(label, action, type='primary', symbol='plus', extra='') { return `<button class="button ${type}" data-action="${action}" ${extra}>${icon(symbol)}${label}</button>`; }
function empty(text, symbol='leaf') { return `<div class="empty">${icon(symbol)}<br>${text}</div>`; }
function allTasks() { return state.plans.flatMap(p => p.tasks.map(t => ({...t,planTitle:p.title,planId:p.id}))); }
function taskRows(tasks, compact = false) {
  if (!tasks.length) return empty('还没有任务，从一个小目标开始吧。','plans');
  return `<div class="task-list">${tasks.map(t => `<div class="task-row"><button class="task-check ${t.done?'done':''}" data-action="toggle-task" data-id="${e(t.id)}" data-done="${t.done}" aria-label="${t.done?'取消完成':'完成任务'}">${t.done?'✓':''}</button><div class="task-text ${t.done?'done':''}"><strong>${e(t.title)}</strong>${compact?`<small>${e(t.planTitle)}</small>`:''}</div><span class="task-time">${t.minutes} 分钟</span><button class="tiny-button" data-action="task-focus" data-id="${e(t.id)}" aria-label="专注此任务">${icon('play')}</button>${!compact?`<button class="tiny-button" data-action="delete-task" data-id="${e(t.id)}" aria-label="删除任务">${icon('trash')}</button>`:''}</div>`).join('')}</div>`;
}
function metrics() {
  const s = state.stats;
  return `<div class="metric-grid">${[
    ['focus','今日专注',s.today_minutes,'分钟','每一段专注都算数'],
    ['fire','连续打卡',s.streak,'天',`累计打卡 <b>${s.checkin_count}</b> 天`],
    ['plans','完成任务',s.completed_tasks,'项',`共 ${s.task_count} 项任务，稳步前进`],
    ['leaf','累计学习',Math.round(s.total_minutes/60*10)/10,'小时',`已完成 <b>${s.focus_count}</b> 次专注`]
  ].map(([i,l,n,u,note]) => `<div class="metric"><div class="metric-label">${icon(i)}${l}</div><div class="metric-number">${n}<small>${u}</small></div><div class="metric-note">${note}</div></div>`).join('')}</div>`;
}
function chart() {
  const max = Math.max(...state.stats.week.map(d => d.minutes), 60);
  return `<div class="chart">${state.stats.week.map(d => `<div class="bar-column"><span>${d.minutes||''}</span><div class="bar" style="height:${Math.max(d.minutes/max*108,3)}px" title="${d.day}: ${d.minutes} 分钟"></div><small>${['日','一','二','三','四','五','六'][new Date(d.day+'T00:00:00').getDay()]}</small></div>`).join('')}</div><div class="chart-foot"><span>过去 7 天 · 专注分钟</span><span>本周累计 ${state.stats.week.reduce((v,d)=>v+d.minutes,0)} 分钟</span></div>`;
}
function heatmap() { return `<div class="heatmap">${state.stats.heatmap.map(d => `<div class="heat-cell ${d.minutes?'focused':d.checked?'checked':''}" title="${d.day} · ${d.checked?'已打卡':'未打卡'} · ${d.minutes} 分钟"></div>`).join('')}</div><div class="heat-legend"><span>少</span><i></i><i></i><i></i><span>多</span></div>`; }
function dashboard() {
  const tasks = allTasks().filter(t=>!t.done).slice(0,4);
  return heading('YOUR LEARNING JOURNEY',`你好，${e(state.user.name)} <span style="font-size:21px">☀</span>`,'从今天的小小行动，走向更远的自己。',button(state.stats.checked_in?'今日已打卡':'记录今日成长','checkin',state.stats.checked_in?'ghost':'primary','check'))+
  `<section class="hero"><div class="hero-copy"><p class="eyebrow">A LITTLE PROGRESS, EVERY DAY</p><h2>让每一次专注，<br>都有<em>生长的力量。</em></h2><p>把大目标变成小行动，给好奇心一点时间。</p>${button('开始一段专注','focus','primary','play')}</div>${art}</section>`+metrics()+
  `<div class="dashboard-grid"><section class="panel"><div class="panel-heading"><h2>接下来的小目标 <small>${allTasks().filter(t=>!t.done).length} 待完成</small></h2><a class="text-button" href="#plans">全部计划 ↗</a></div>${taskRows(tasks,true)}${!state.plans.length?`<div style="padding:0 23px 23px">${button('创建第一个计划','new-plan','ghost')}</div>`:''}</section><div><section class="panel"><div class="panel-heading"><h2>专注的足迹</h2><span class="badge">近 7 天</span></div>${chart()}</section><section class="coach-card"><div class="coach-title">${icon('agent')}你的 AI 学习教练 <span class="badge">${state.cap.ai_mode==='llm'?'AI 已连接':'规则模式'}</span></div><p>结合你的学习数据与目标，拆解出真正可以开始的下一步。</p><a class="text-button" href="#agent">一起制定计划 ${icon('arrow')}</a></section></div></div><section class="panel padded section-gap"><div class="panel-heading" style="padding:0 0 22px"><h2>持续生长 <small>最近 52 周</small></h2><span class="small-label">${state.stats.checkin_count} 天的坚持</span></div>${heatmap()}</section>`;
}
function plansView() {
  return heading('SMALL STEPS, BIG GOALS','计划与任务','把想做的事写下来，把每一步踏实完成。',button('新建计划','new-plan'))+
  (!state.plans.length?`<section class="panel">${empty('你的下一段学习旅程，从一个计划开始。','plans')}<div style="text-align:center;padding-bottom:30px">${button('创建计划','new-plan','primary')} ${button('载入示例资料','seed','ghost','knowledge')}</div></section>`:
  `<div class="plans-grid">${state.plans.map((p,i) => `<section class="panel plan-card"><div class="plan-head"><span class="badge">PLAN ${String(i+1).padStart(2,'0')}</span><button class="tiny-button" data-action="delete-plan" data-id="${p.id}" aria-label="删除计划">${icon('trash')}</button></div><h2>${e(p.title)}</h2><p class="plan-description">${e(p.description||'每一步积累，都离目标更近一点。')}</p><div class="progress-label"><span>${p.tasks.filter(t=>t.done).length} / ${p.tasks.length} 个任务</span><span>${p.progress}%</span></div><div class="progress-track"><span style="width:${p.progress}%"></span></div>${taskRows(p.tasks)}<div class="plan-actions"><button class="text-button" data-action="new-task" data-id="${p.id}">＋ 添加任务</button><a class="text-button" href="#focus">去专注 ↗</a></div></section>`).join('')}</div>`);
}
function focusView() {
  return heading('ONE THING AT A TIME','专注空间','暂时放下其他事，给眼前的目标一段完整的时间。')+`<div class="two-column"><section class="panel focus-panel"><span class="eyebrow">TIME TO GROW</span><h2>此刻，只做一件事。</h2><div class="timer-ring"><div class="timer-inner"><span id="timer" class="timer">25:00</span><span id="timer-caption" class="timer-caption">准备好就开始</span></div></div><div class="focus-controls"><select id="focus-minutes" aria-label="专注时长" ${state.focus?'disabled':''}>${[25,45,60,1].map(m=>`<option value="${m}" ${state.focus?.minutes===m?'selected':''}>${m===1?'1 分钟体验':m+' 分钟'}</option>`).join('')}</select>${state.focus?button('结束本次','cancel-focus','ghost','close'):button('开始专注','start-focus','primary','play')}</div><select id="focus-task" class="focus-select" aria-label="关联任务" ${state.focus?'disabled':''}><option value="">自由专注 · 不关联任务</option>${allTasks().filter(t=>!t.done).map(t=>`<option value="${t.id}" ${state.focus?.task_id===t.id?'selected':''}>${e(t.title)}</option>`).join('')}</select><p class="focus-note">完成后自动记录专注时长，刷新页面也能继续。<br>提前结束不会计入统计。</p></section><div><section class="panel padded"><p class="eyebrow">A MOMENT FOR YOURSELF</p><h2>给专注一点仪式感</h2><div class="reading-note"><ol><li>选一个现在就能开始的小任务。</li><li>把手机放远，暂时关闭通知。</li><li>专注到倒计时结束，再稍作休息。</li></ol></div><div class="coach-card" style="margin-top:5px"><div class="coach-title">${icon('leaf')}不必一次做完所有事。</div><p>只需要给下一步，留出一点安静的时间。</p></div></section><section class="panel padded section-gap"><div class="metric-label">今天已经认真学习</div><div class="metric-number">${state.stats.today_minutes}<small>分钟</small></div><p class="subtitle">累计 ${state.stats.focus_count} 次专注，每次努力都被记录。</p></section></div></div>`;
}
function knowledgeView() {
  const documents = state.docs.map(d => `
    <div class="doc-row">${icon('file')}
      <button class="doc-info" data-action="read-doc" data-id="${d.id}" style="text-align:left">
        <strong>${e(d.title)}</strong><small>${d.chunks} 个片段 · ${d.index_status==='ready'?'向量就绪':'待建向量索引'}</small>
      </button>
      <button class="tiny-button" data-action="reindex-doc" data-id="${d.id}" aria-label="重建索引：${e(d.title)}" title="重建向量索引" ${state.cap.retrieval_mode!=='hybrid'?'disabled':''}>${icon('focus')}</button>
      <button class="tiny-button" data-action="delete-doc" data-id="${d.id}" aria-label="删除文档">${icon('trash')}</button>
    </div>`).join('');
  return heading('BUILD YOUR SECOND BRAIN','知识库','把资料变成自己的知识，让每一个答案都有出处。',button('新建笔记','new-doc','primary','plus')) + `
    <div class="knowledge-layout">
      <section class="panel">
        <div class="panel-heading"><h2>我的资料 <small>${state.docs.length} 份</small></h2><span class="badge">${state.cap.retrieval_mode==='hybrid'?'混合检索':'BM25'}</span></div>
        <label class="upload-zone">${icon('file')}<br>点击上传学习资料<input id="file-upload" type="file" accept=".md,.txt,.pdf,.docx" hidden><small>MD / TXT / PDF / DOCX · 最大 5 MB</small></label>
        <div class="doc-list">${documents || empty('上传第一份资料，<br>或者载入内置示例。','knowledge')}</div>
        ${!state.docs.length?`<div style="padding:0 20px 20px">${button('载入示例资料','seed','ghost','knowledge')}</div>`:''}
      </section>
      <section class="panel answer-panel">
        <div class="run-top"><h2>${icon('agent')} 与你的知识对话</h2><span class="badge">引用可追溯</span></div>
        <p class="subtitle" style="margin-top:11px">${state.cap.ai_mode==='llm'?'基于检索资料生成回答，支持流式输出。':'本地模式展示检索原文；配置模型后可生成引用回答。'}</p>
        <form id="ask-form">
          <label class="knowledge-scope">回答依据<select name="document_id" aria-label="回答依据"><option value="">全部资料</option>${state.docs.map(d=>`<option value="${d.id}">${e(d.title)}</option>`).join('')}</select></label>
          <div class="question-input"><input name="question" required maxlength="2000" placeholder="例如：FastAPI 中如何隔离不同用户的数据？" aria-label="知识库问题"><button class="button primary" type="submit">${icon('send')} 提问</button></div>
        </form>
        <div id="answer"><div class="answer-hint">${icon('knowledge')}<br>读过的资料，都能成为下一次灵感的起点。<br><small>选择回答依据，提出问题，查看引用片段。</small></div></div>
      </section>
    </div>`;
}
const toolNames = {observe_learning:'读取学习数据',generate_structured_plan:'生成结构化计划',validate_plan:'校验任务结构',request_approval:'确认计划草稿',create_plan:'写入计划与任务'};
function runCard(r) {
  const result=r.result;
  return `<section class="panel agent-run"><div class="run-top"><h2>${e(r.goal)}</h2><span class="badge ${r.status==='awaiting_approval'?'orange':''}">${({awaiting_approval:'待确认',completed:'已创建',cancelled:'已取消',running:'处理中'})[r.status]||e(r.status)}</span></div><p class="subtitle" style="margin-top:8px">${r.mode==='llm'?'语言模型规划':'本地规则规划'} · ${new Date(r.created_at+'Z'.repeat(!/[Z+]\d*/.test(r.created_at))).toLocaleString('zh-CN')}</p>${result?`<p class="run-summary">${e(result.summary)}</p>${result.warning?`<div class="notice">${e(result.warning)}</div>`:''}<div class="run-tasks">${result.tasks.map((t,i)=>`<div>${i+1}. ${e(t.title)}<span>${t.minutes} 分钟</span></div>`).join('')}</div>`:''}<div class="trace">${r.steps.map(s=>`<details><summary>${e(toolNames[s.tool]||s.tool)} · ${s.status==='completed'?'完成':s.status==='fallback'?'已降级':'待确认'} ${s.duration_ms!=null?`<small>(${s.duration_ms} ms)</small>`:''}</summary><pre>${e(typeof s.detail==='object'?JSON.stringify(s.detail,null,2):s.detail)}</pre></details>`).join('')}</div>${r.status==='awaiting_approval'?`<div class="run-actions">${button('确认并创建计划','approve-run','primary','check',`data-id="${r.id}"`)}${button('暂不采用','reject-run','ghost','close',`data-id="${r.id}"`)}</div>`:r.plan_id?'<a class="text-button" href="#plans">查看已创建的计划 ↗</a>':''}</section>`;
}
function agentView() {
  return heading('YOUR PERSONAL LEARNING COACH','AI 学习教练','从你的真实学习数据出发，一起找到下一步。',`<span class="badge">${state.cap.ai_mode==='llm'?e(state.cap.model):'本地规则模式'}</span>`)+
  `<section class="agent-prompt"><h2>${icon('agent')} 你接下来想学什么？</h2><p class="subtitle" style="margin-top:12px">教练会读取学习统计和你的偏好，生成草稿；确认后自动加入计划。</p><form id="agent-form"><input name="goal" minlength="2" maxlength="2000" required placeholder="例如：两周内掌握 FastAPI，做一个带 RAG 的学习助手" aria-label="学习目标"><button type="submit" class="button primary">生成学习计划 ${icon('arrow')}</button></form></section><div class="panel-heading" style="padding:0 0 18px"><h2>规划与执行记录</h2><span class="subtitle">今日请求 ${state.cap.requests_today} / ${state.cap.daily_limit}</span></div><div id="runs">${state.runs.length?state.runs.map(runCard).join(''):`<section class="panel">${empty('从一个具体目标开始，第一步会慢慢清晰。','agent')}</section>`}</div>`;
}
function statsView() { return heading('EVERY EFFORT COUNTS','成长记录','走过的每一步，都在这里留下了痕迹。')+metrics()+`<div class="two-column"><section class="panel"><div class="panel-heading"><h2>最近一周的专注</h2><span class="badge">分钟</span></div>${chart()}</section><section class="panel padded"><p class="eyebrow">LEARNING INSIGHT</p><h2>找到自己的节奏</h2><p class="reading-note">${state.stats.focus_count?`已完成 ${state.stats.focus_count} 次专注，平均每次 ${Math.round(state.stats.total_minutes/state.stats.focus_count)} 分钟。`:'第一段专注结束后，这里会记录你的学习节奏。'}<br>目前有 ${state.plans.length} 个计划，完成了 ${state.stats.completed_tasks} / ${state.stats.task_count} 项任务。</p><a class="text-button" href="#agent">让学习教练制定下一步 ↗</a></section></div><section class="panel padded section-gap"><div class="panel-heading" style="padding:0 0 24px"><h2>学习日历 <small>最近 52 周</small></h2><span class="small-label">连续 ${state.stats.streak} 天</span></div>${heatmap()}</section>`; }
function communityView() { return heading('GROW BETTER, TOGETHER','学习广场','分享今天的收获，和认真学习的人一起前进。',`<span id="online-label" class="badge">连接中…</span>`)+`<section class="panel chat-panel"><div class="panel-heading"><h2>${icon('community')} 一起学习吧</h2><span class="subtitle">所有登录用户可见</span></div><div id="chat-messages" class="chat-messages" aria-live="polite">${state.messages.map(chatMessage).join('')||empty('这里还很安静，分享你的第一个学习收获吧。','community')}</div><form id="chat-form" class="chat-form"><input name="content" required maxlength="2000" placeholder="今天有什么新的收获？" aria-label="聊天消息"><button class="button primary" type="submit">${icon('send')}发送</button></form></section>`; }
function chatMessage(m) { return `<div class="chat-message ${m.user_id===state.user.id?'own':''}"><div class="avatar">${e(m.name.slice(0,1).toUpperCase())}</div><div><div class="chat-meta">${e(m.name)}</div><div class="chat-bubble">${e(m.content)}</div></div></div>`; }
function settingsView() { return heading('MAKE IT YOUR OWN','我的学习空间','让教练更了解你，给自己更合适的学习节奏。')+`<section class="panel padded"><form id="settings-form" class="settings-form"><label>昵称<input value="${e(state.user.name)}" disabled></label><label>邮箱<input value="${e(state.user.email)}" disabled></label><label>学习偏好与长期目标<textarea name="preference" rows="5" maxlength="1000" placeholder="例如：每晚可学习一小时，偏好项目实践，目标是 AI 应用开发岗位。">${e(state.user.preference)}</textarea></label><p class="subtitle">你主动填写的偏好会保存在账户中，并在生成计划时作为上下文使用。</p><button class="button primary" type="submit">保存学习偏好</button></form><div class="mode-info"><span>规划模式：${state.cap.ai_mode==='llm'?'语言模型 · '+e(state.cap.model):'本地规则'}</span><span>知识检索：${state.cap.retrieval_mode==='hybrid'?'BM25 + 向量混合检索':'本地 BM25 关键词检索'}</span><span>今日请求：${state.cap.requests_today} / ${state.cap.daily_limit}</span></div>${button('退出登录','logout','ghost','arrow')}</section>`; }

async function refresh() { const [s,p,c,f] = await Promise.all([api('/stats'),api('/plans'),api('/capabilities'),api('/focus/active')]); Object.assign(state,{stats:s,plans:p,cap:c,focus:f}); }
async function render() {
  if (!state.user) return;
  const token = ++renderToken;
  state.page = location.hash.slice(1) || 'dashboard';
  if (![...nav.map(n=>n[0]),'settings'].includes(state.page)) state.page='dashboard';
  if (state.page!=='community' && state.socket) { state.socket.close(); state.socket=null; }
  clearTimeout(reconnectTimer);
  $('#page-label').textContent = nav.find(n=>n[0]===state.page)?.[1] || '我的学习空间';
  $('#navigation').innerHTML=nav.map(([id,label])=>`<a href="#${id}" aria-label="${label}" class="nav-link ${state.page===id?'active':''}" ${state.page===id?'aria-current="page"':''}>${icon(id)}<span>${label}</span>${id==='agent'?'<span class="nav-tag">AI</span>':''}</a>`).join('');
  $('#main').innerHTML='<div class="loading"><span class="spinner"></span> 正在整理你的学习空间…</div>';
  try {
    await refresh();
    const page=state.page;
    if(page==='knowledge') state.docs=await api('/documents');
    if(page==='agent') state.runs=await api('/agent/runs');
    if(page==='community') state.messages=await api('/chat/messages');
    if(token!==renderToken) return;
    $('#mode-label').textContent=state.cap.ai_mode==='llm'?'AI 已连接':'本地规则模式';
    const views={dashboard,plans:plansView,focus:focusView,knowledge:knowledgeView,agent:agentView,stats:statsView,community:communityView,settings:settingsView};
    $('#main').innerHTML=views[page]();
    if(page==='focus') {if(state.selectedTask&&!state.focus)$('#focus-task').value=state.selectedTask;tick();}
    if(page==='community') connectChat();
  } catch(error) { if(token===renderToken) $('#main').innerHTML=`<section class="panel">${empty(e(error.message))}<div style="text-align:center;padding-bottom:24px">${button('重新加载','reload','ghost','arrow')}</div></section>`; }
}
function go(page) { if(location.hash==='#'+page) render(); else location.hash=page; }
function showAuth() {
  state.user=null; state.focus=null; renderToken++; clearTimeout(reconnectTimer);
  if(state.socket) {state.socket.close();state.socket=null;}
  $('#shell').hidden=true; $('#auth').hidden=false;
  const register=state.authMode==='register';
  $('#auth').innerHTML=`<section class="auth-story"><a class="brand" href="/"><span class="brand-mark">S</span>StudyFlow<span class="brand-dot">●</span></a><h1>学习，是一场<br>慢慢生长的旅程。</h1><p>计划 · 专注 · 知识 · AI 教练<br>给每一次认真，留下生长的痕迹。</p>${art}</section><section class="auth-form-wrap"><form id="auth-form" class="auth-form"><p class="eyebrow">YOUR NEXT CHAPTER STARTS HERE</p><h2>${register?'开启你的学习空间':'欢迎回来。'}</h2><p class="subtitle">${register?'从一个小小的目标开始。':'今天，也向目标靠近一点。'}</p>${register?'<label>怎么称呼你<input name="name" required maxlength="60" autocomplete="nickname" placeholder="你的昵称"></label>':''}<label>邮箱<input name="email" type="email" required autocomplete="email" maxlength="254" placeholder="you@example.com"></label><label>密码<input name="password" type="password" required minlength="8" maxlength="128" autocomplete="${register?'new-password':'current-password'}" placeholder="至少 8 位字符"></label><div id="auth-error" class="form-error" role="alert"></div><button class="button primary" type="submit">${register?'创建账户':'进入学习空间'} ${icon('arrow')}</button><div class="auth-switch">${register?'已有账户？':'还没有账户？'} <button type="button" data-action="auth-switch">${register?'去登录':'创建一个'}</button></div><p class="auth-note">无需配置 AI 密钥，即可体验完整学习流程。</p></form></section>`;
}
async function loggedIn(user) {
  state.user=user;$('#auth').hidden=true;$('#shell').hidden=false;
  $('#profile-name').textContent=user.name;$('#avatar').textContent=user.name.slice(0,1).toUpperCase();
  $('#today-label').textContent=new Intl.DateTimeFormat('zh-CN',{month:'long',day:'numeric',weekday:'long',timeZone:'Asia/Shanghai'}).format(new Date());
  await render();
}
function modal(title, content) { $('#modal-content').innerHTML=`<div class="modal-heading"><h2>${e(title)}</h2><button data-action="close-modal" class="tiny-button" aria-label="关闭">${icon('close')}</button></div>${content}`;$('#modal').showModal(); }
function newPlan() { modal('开始一个新计划',`<form id="plan-form" class="form-grid"><label>计划名称<input name="title" required maxlength="120" placeholder="例如：FastAPI 实战入门"></label><label>目标与说明<textarea name="description" rows="3" maxlength="10000" placeholder="你希望完成后能做到什么？"></textarea></label><label>初始任务<textarea name="tasks" rows="5" placeholder="每行一个小任务，最多 30 个\n学习请求与响应\n实现第一个 REST API\n为接口编写测试"></textarea></label><div class="help">任务默认预计 25 分钟。也可以先创建空计划，再逐步添加。</div><div class="form-actions"><button type="button" class="button ghost" data-action="close-modal">取消</button><button type="submit" class="button primary">创建计划</button></div></form>`); }
async function seed() {
  await post('/documents',{title:'FastAPI 学习手册 · 示例',content:'# FastAPI 实战学习手册\n\n## 用户数据隔离\n每条业务记录必须关联 user_id。服务端从经过验证的会话中获取当前用户，所有读取、修改和删除操作都需要同时验证记录所有者；不要信任客户端传入的 user_id。其他用户的记录返回 404。\n\n## RAG 检索增强生成\nRAG 包含文档解析、带重叠的文本分块、索引构建、查询检索和基于证据生成回答。BM25 适合关键词匹配；向量检索适合语义匹配；混合检索可以通过 RRF 合并排名。回答需保留来源引用，找不到依据时应明确说明。\n\n## FastAPI 依赖注入\n通过 Depends 注入数据库 Session 和当前用户。数据库 Session 每个请求独立创建，结束后关闭。使用 Pydantic 校验请求与模型的结构化输出。\n\n## 工作流与幂等\n学习规划工作流先读取学习统计和偏好，再生成计划草稿，通过用户确认后写入计划与任务。用状态条件更新和事务防止重复确认创建多份计划。专注完成接口需校验服务端时间，重复提交不重复计时。'});
  if(!state.plans.some(p=>p.title==='构建我的第一个 AI 学习助手')) await post('/plans',{title:'构建我的第一个 AI 学习助手',description:'示例计划：从 API 到知识库，完成一个可演示的学习项目。',tasks:[{title:'熟悉 FastAPI 路由、依赖注入与数据校验',minutes:25},{title:'实现登录会话与用户数据隔离',minutes:45},{title:'上传学习资料，体验带引用的知识库问答',minutes:25},{title:'运行 AI 规划工作流，查看步骤记录',minutes:25}]});
  toast('示例计划和资料已载入，可以开始体验了');await render();
}
let completing=false;
async function tick() {
  if(!state.user) return;
  if(!state.focus) { if($('#timer')) $('#timer').textContent=String(Number($('#focus-minutes')?.value||25)).padStart(2,'0')+':00';return; }
  const remain=Math.max(0,Math.ceil((new Date(state.focus.ends_at)-Date.now())/1000));
  if($('#timer')) $('#timer').textContent=String(Math.floor(remain/60)).padStart(2,'0')+':'+String(remain%60).padStart(2,'0');
  if($('#timer-caption')) $('#timer-caption').textContent=remain?'正在慢慢靠近目标':'正在记录本次专注';
  if(remain===0&&!completing) {completing=true;try {await post(`/focus/${state.focus.id}/complete`);state.focus=null;toast('这段专注已记录，休息一下吧。');await render();}catch(error){toast(error.message);}finally{completing=false;}}
}
setInterval(tick,1000);
function connectChat() {
  if(state.socket&&state.socket.readyState<2) return;
  const socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws/chat`);state.socket=socket;
  socket.onmessage=event=>{const data=JSON.parse(event.data);if(data.type==='presence'){state.online=data.online;if($('#online-label'))$('#online-label').textContent=`${data.online} 人在线`;}if(data.type==='error')toast(data.message);if(data.type==='message'){if(state.messages.some(m=>m.id===data.id))return;state.messages.push(data);state.messages=state.messages.slice(-100);const box=$('#chat-messages');if(box){const nearBottom=box.scrollHeight-box.scrollTop-box.clientHeight<80;box.innerHTML=state.messages.map(chatMessage).join('');if(nearBottom)box.scrollTop=box.scrollHeight;}}};
  socket.onclose=()=>{if(state.socket===socket)state.socket=null;if($('#online-label'))$('#online-label').textContent='连接已断开';if(state.page==='community'&&state.user)reconnectTimer=setTimeout(connectChat,4000);};
  const box=$('#chat-messages');if(box)box.scrollTop=box.scrollHeight;
}
async function askQuestion(form) {
  if(state.asking)return;state.asking=true;
  const submit=$('button[type="submit"]',form);submit.disabled=true;
  $('#answer').innerHTML='<div class="answer-content" id="answer-text">正在检索资料…</div><div id="sources" class="sources"></div>';
  let output='';
  try{
    const values=new FormData(form);
    const response=await fetch('/api/knowledge/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:values.get('question'),document_id:values.get('document_id')||null})});
    if(!response.ok){const data=await response.json();throw new Error(data.detail||'提问失败');}
    const reader=response.body.getReader(),decoder=new TextDecoder();let pending='',doneEvent=false;
    function frame(value){const event=value.match(/^event: (.+)$/m)?.[1],line=value.match(/^data: (.+)$/m)?.[1];if(!line)return;const data=JSON.parse(line);
      if(event==='sources'&&$('#sources'))$('#sources').innerHTML=data.sources.map(s=>`<details class="source"><summary>[${s.index}] ${e(s.title)} · 片段 ${s.chunk+1}</summary><p>${e(s.content)}</p><button class="text-button" data-action="read-doc" data-id="${e(s.document_id)}">阅读原文 ↗</button></details>`).join('');
      if(event==='delta'){output+=data.text;if($('#answer-text'))$('#answer-text').textContent=output;}
      if(event==='error')throw new Error(data.message);
      if(event==='done')doneEvent=true;
    }
    try{while(true){const {done,value}=await reader.read();pending+=decoder.decode(value||new Uint8Array(),{stream:!done});let index;while((index=pending.indexOf('\n\n'))>=0){frame(pending.slice(0,index));pending=pending.slice(index+2);}if(done)break;}if(!doneEvent)throw new Error('响应中断，请重试');}finally{await reader.cancel().catch(()=>{});}
  }catch(error){toast(error.message);if($('#answer-text'))$('#answer-text').textContent=(output?output+'\n\n':'')+error.message;}finally{state.asking=false;submit.disabled=false;}
}

document.addEventListener('click',async event=>{
  const target=event.target.closest('[data-action]');if(!target)return;const action=target.dataset.action,id=target.dataset.id;
  if(target.disabled)return;
  try{
    if(nav.some(n=>n[0]===action)||action==='settings'){go(action);return;}
    if(action==='auth-switch'){state.authMode=state.authMode==='login'?'register':'login';showAuth();return;}
    if(action==='close-modal'){$('#modal').close();return;}
    if(action==='new-plan'){newPlan();return;}
    if(action==='new-task'){modal('添加一个小任务',`<form id="task-form" data-plan="${e(id)}" class="form-grid"><label>任务名称<input name="title" required maxlength="200" placeholder="一个具体、可完成的行动"></label><label>预计分钟<input name="minutes" type="number" min="5" max="180" value="25" required></label><div class="form-actions"><button class="button primary" type="submit">添加任务</button></div></form>`);return;}
    if(action==='new-doc'){modal('写一份学习笔记',`<form id="doc-form" class="form-grid"><label>标题<input name="title" required maxlength="120" placeholder="给这份知识一个名字"></label><label>内容<textarea name="content" rows="10" required maxlength="200000" placeholder="支持 Markdown 或纯文本，保存后自动分块并建立索引。"></textarea></label><div class="form-actions"><button class="button primary" type="submit">保存并索引</button></div></form>`);return;}
    if(action==='read-doc'){const doc=await api('/documents/'+id);modal(doc.title,`<div class="document-text">${e(doc.content)}</div>`);return;}
    if(action.startsWith('delete-')||action==='cancel-focus'){
      const item=action==='delete-plan'?'这个计划及其所有任务':action==='delete-task'?'这个任务':action==='delete-doc'?'这份文档及其检索索引':'本次专注（不会计入学习时长）';
      modal('确认操作',`<p class="reading-note">确定删除或结束${item}？</p><div class="form-actions"><button class="button ghost" data-action="close-modal">保留</button><button class="button danger" data-action="confirm-${action}" data-id="${e(id||state.focus?.id)}">确认</button></div>`);return;
    }
    target.disabled=true;
    if(action==='reindex-doc'){toast('正在重建向量索引，请稍候…');await post('/documents/'+id+'/reindex');toast('向量索引已更新，原文档已保留');}
    if(action==='checkin'){await post('/checkins');toast('今天的努力，已留下痕迹。');}
    if(action==='toggle-task')await api('/tasks/'+id,{method:'PATCH',body:JSON.stringify({done:target.dataset.done!=='true'})});
    if(action==='confirm-delete-plan')await api('/plans/'+id,{method:'DELETE'});
    if(action==='confirm-delete-task')await api('/tasks/'+id,{method:'DELETE'});
    if(action==='confirm-delete-doc')await api('/documents/'+id,{method:'DELETE'});
    if(action==='confirm-cancel-focus'){await api('/focus/'+id,{method:'DELETE'});state.focus=null;}
    if(action.startsWith('confirm-'))$('#modal').close();
    if(action==='start-focus'){state.focus=await post('/focus/start',{minutes:Number($('#focus-minutes').value),task_id:$('#focus-task').value||null,request_id:crypto.randomUUID()});}
    if(action==='task-focus'){state.selectedTask=id;go('focus');return;}
    if(action==='approve-run'){await post('/agent/runs/'+id+'/approve');toast('计划与任务已创建，开始行动吧。');}
    if(action==='reject-run')await post('/agent/runs/'+id+'/reject');
    if(action==='seed'){await seed();return;}
    if(action==='logout'){await post('/auth/logout');showAuth();return;}
    await render();
  }catch(error){toast(error.message);}finally{target.disabled=false;}
});
document.addEventListener('submit',async event=>{
  const form=event.target;if(!form.id)return;event.preventDefault();
  if(form.id==='ask-form'){await askQuestion(form);return;}
  const values=Object.fromEntries(new FormData(form)),submit=$('button[type="submit"]',form);if(submit?.disabled)return;if(submit)submit.disabled=true;
  try{
    if(form.id==='auth-form'){const user=await post('/auth/'+state.authMode,values);await loggedIn(user);return;}
    if(form.id==='plan-form'){const tasks=values.tasks.split('\n').map(v=>v.trim()).filter(Boolean);if(tasks.length>30)throw new Error('初始任务最多 30 项');await post('/plans',{title:values.title,description:values.description,tasks:tasks.map(title=>({title,minutes:25}))});$('#modal').close();toast('新计划已创建');}
    if(form.id==='task-form'){await post('/plans/'+form.dataset.plan+'/tasks',{title:values.title,minutes:Number(values.minutes)});$('#modal').close();}
    if(form.id==='doc-form'){await post('/documents',values);$('#modal').close();toast('笔记已保存并建立索引');}
    if(form.id==='agent-form'){submit.innerHTML='<span class="spinner"></span> 正在分析与规划…';const run=await post('/agent/runs',values);toast(run.mode==='llm'?'计划草稿已生成，确认后即可执行':'规则计划草稿已生成，请查看并确认');}
    if(form.id==='settings-form'){state.user=await api('/auth/me',{method:'PATCH',body:JSON.stringify(values)});toast('学习偏好已保存');}
    if(form.id==='chat-form'){if(state.socket?.readyState!==WebSocket.OPEN)throw new Error('聊天连接尚未就绪，请稍后重试');state.socket.send(JSON.stringify(values));form.reset();return;}
    await render();
  }catch(error){if(form.id==='auth-form')$('#auth-error').textContent=error.message;else toast(error.message);if(form.id==='agent-form')submit.textContent='生成学习计划';}finally{if(submit)submit.disabled=false;}
});
document.addEventListener('change',async event=>{
  if(event.target.id==='focus-minutes')tick();
  if(event.target.id==='file-upload'&&event.target.files[0]){const file=event.target.files[0];if(file.size>5*1024*1024){toast('文件最多 5 MB');return;}const body=new FormData();body.append('file',file);toast('正在解析并索引资料…');event.target.disabled=true;try{const result=await api('/documents/upload',{method:'POST',body});toast(result.duplicate?'相同内容已经在知识库中':'资料已加入知识库');await render();}catch(error){toast(error.message);event.target.disabled=false;event.target.value='';}}
});
window.addEventListener('hashchange',render);
$('#modal').addEventListener('click',event=>{if(event.target===$('#modal')){const r=$('#modal').getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)$('#modal').close();}});
api('/auth/me').then(loggedIn).catch(showAuth);
