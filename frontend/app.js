/* Herb-Hermes 研究驾驶舱 — front-end controller (vanilla JS + ECharts) */
'use strict';

const API = location.origin.includes('null') ? 'http://127.0.0.1:8000' : '';
const $ = (s, r = document) => r.querySelector(s);
const el = (h) => { const d = document.createElement('div'); d.innerHTML = h.trim(); return d.firstChild; };
const esc = (s) => (s ?? '').toString().replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
const charts = [];

const COL = {
  jade: '#6fcf97', jadeDeep: '#3fae78', celadon: '#a7d8bd', gold: '#d9b25f',
  goldSoft: '#e7cf95', rust: '#d98a6a', ink: '#e9f1ea', muted: '#93a89b',
  line: 'rgba(143,196,168,0.18)', panel: '#15201b'
};
const PALETTE = ['#6fcf97', '#d9b25f', '#7fb6d9', '#d98a6a', '#b08fd9', '#cf9f6f', '#79c7b0', '#c98aa6'];

async function api(path, opts) {
  const r = await fetch(API + path, opts);
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return r.json();
}
function toast(msg) {
  const t = $('#toast'); t.textContent = msg; t.classList.add('show');
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove('show'), 2200);
}
function disposeCharts() { while (charts.length) { try { charts.pop().dispose(); } catch (e) {} } }
function mkChart(node) { const c = echarts.init(node, null, { renderer: 'canvas' }); charts.push(c); return c; }
window.addEventListener('resize', () => charts.forEach(c => c.resize()));

const isFormulaName = (s) => /[湯散丸飲膏丹湯飲子煎]$/.test(s.trim()) || /[汤散丸饮膏]$/.test(s.trim());

/* ========================= Settings ========================= */
const Settings = {
  K: { MODEL: 'hh_model', KEY: 'hh_apikey', BASE: 'hh_apibase', PROV: 'hh_prov' },
  get() {
    return {
      model:    localStorage.getItem(this.K.MODEL) || '',
      apiKey:   localStorage.getItem(this.K.KEY)   || '',
      apiBase:  localStorage.getItem(this.K.BASE)  || '',
      provider: localStorage.getItem(this.K.PROV)  || '',
    };
  },
  set(d) {
    const set = (k, v) => v ? localStorage.setItem(k, v) : localStorage.removeItem(k);
    set(this.K.MODEL, d.model);
    set(this.K.KEY,   d.apiKey);
    set(this.K.BASE,  d.apiBase);
    set(this.K.PROV,  d.provider);
  },
  clear() { Object.values(this.K).forEach(k => localStorage.removeItem(k)); },
  /** Build the extra payload fields for /agent/ask and /agent/stream */
  agentPayload(base = {}) {
    const s = this.get();
    const p = Object.assign({}, base);
    if (s.model)  p.model   = s.model;
    if (s.apiKey) p.api_key = s.apiKey;
    if (s.apiBase) p.api_base = s.apiBase;
    return p;
  },
  hasLocal() { const s = this.get(); return !!(s.model || s.apiKey); },
};

/* ========================= Settings Panel ========================= */
let _modelsCache = null;
async function _fetchModels() {
  if (_modelsCache) return _modelsCache;
  try { _modelsCache = await api('/llm/models'); } catch (e) { _modelsCache = null; }
  return _modelsCache;
}

const FALLBACK_MODELS = {
  minimax:   ['MiniMax-M3','MiniMax-M2.7','MiniMax-M2.7-highspeed','MiniMax-M2.5','MiniMax-M2.5-highspeed','MiniMax-M2.1','MiniMax-M2.1-highspeed','MiniMax-M2'],
  openai:    ['gpt-4o-mini','gpt-4o','o3','o4-mini'],
  anthropic: ['claude-sonnet-4-6','claude-opus-4-8','claude-fable-5','claude-haiku-4-5-20251001'],
  ollama:    ['ollama/qwen2.5','ollama/llama3.2','ollama/deepseek-r1'],
  custom:    [],
};
const MINIMAX_REASONING = new Set(['MiniMax-M3','MiniMax-M2.7','MiniMax-M2.7-highspeed','MiniMax-M2.5','MiniMax-M2.5-highspeed','MiniMax-M2.1','MiniMax-M2.1-highspeed','MiniMax-M2']);

function _providerModels(prov, data) {
  if (!data) return (FALLBACK_MODELS[prov] || []).map(id => ({ id: prov === 'minimax' ? 'minimax/'+id : id, label: id, reasoning: MINIMAX_REASONING.has(id) }));
  const match = data.providers.find(p => p.name.toLowerCase().replace(/\s.*/, '') === prov) || data.providers[0];
  return match ? match.models : [];
}

async function openSettings() {
  $('#settings-panel').classList.add('open');
  const models = await _fetchModels();
  const s = Settings.get();
  const prov = s.provider || 'minimax';
  $('#set-provider').value = prov;
  if (s.apiKey)  $('#set-apikey').value  = s.apiKey;
  if (s.apiBase) $('#set-apibase').value = s.apiBase;
  _updateModelSelect(prov, s.model, models);
  _updateProviderHints(prov);
}
window.openSettings = openSettings;

function closeSettings() { $('#settings-panel').classList.remove('open'); }

function _updateModelSelect(prov, selected, data) {
  const sel = $('#set-model');
  sel.innerHTML = '';
  _providerModels(prov, data).forEach(m => {
    const o = document.createElement('option');
    o.value = m.id;
    o.textContent = m.label + (m.context ? ' ('+m.context+')' : '') + (m.reasoning ? ' ✦' : '');
    sel.appendChild(o);
  });
  if (selected) sel.value = selected;
  _updateReasoningBadge(sel.value);
}

function _updateReasoningBadge(modelId) {
  const bare = (modelId || '').split('/').pop();
  const hasReason = MINIMAX_REASONING.has(bare) ||
    ['o3','o4-mini','claude-fable-5','claude-opus-4-8','deepseek-r1'].some(m => bare.includes(m));
  const badge = $('#set-reasoning-badge');
  if (badge) badge.style.display = hasReason ? '' : 'none';
}

function _updateProviderHints(prov) {
  const tip = $('#set-tip');
  const baseGrp = $('#set-apibase-group');
  const baseIn = $('#set-apibase');
  const TIPS = {
    minimax: 'MiniMax 提示：官网申请 Key：<code>api.minimaxi.com</code> · 本系统自动启用 <code>reasoning_split=True</code>，在智能问答中实时显示「思考过程」。',
    openai: 'OpenAI Key 以 <code>sk-</code> 开头。',
    anthropic: 'Anthropic Key 以 <code>sk-ant-</code> 开头。',
    ollama: 'Ollama 无需 Key，确保本地服务已启动（默认 <code>http://localhost:11434</code>）。',
    custom: '填写兼容 OpenAI API 格式的自定义端点，如 vLLM、LM Studio 等。',
  };
  if (tip) tip.innerHTML = `<p>${TIPS[prov] || ''}</p>`;
  const showBase = ['minimax','ollama','custom'].includes(prov);
  if (baseGrp) baseGrp.style.display = showBase ? '' : 'none';
  if (baseIn && !baseIn.value) {
    if (prov === 'minimax') baseIn.value = 'https://api.minimaxi.com/v1';
    else if (prov === 'ollama') baseIn.value = 'http://localhost:11434';
  }
  // Clear base hint for OpenAI/Anthropic
  if (!showBase && baseIn) baseIn.value = '';
}

$('#set-provider').addEventListener('change', async function() {
  const models = await _fetchModels();
  _updateModelSelect(this.value, '', models);
  _updateProviderHints(this.value);
});
$('#set-model').addEventListener('change', function() { _updateReasoningBadge(this.value); });
$('#set-apply').addEventListener('click', () => {
  const s = {
    provider: $('#set-provider').value,
    model:    $('#set-model').value,
    apiKey:   $('#set-apikey').value.trim(),
    apiBase:  $('#set-apibase').value.trim(),
  };
  Settings.set(s);
  closeSettings();
  toast('已保存：' + (s.model || '(auto)'));
  _refreshAgentStatus();
});
$('#set-clear').addEventListener('click', () => {
  Settings.clear();
  ['#set-apikey','#set-apibase'].forEach(sel => { if ($(sel)) $(sel).value = ''; });
  toast('已清除模型配置');
  _refreshAgentStatus();
});
$('#closeSettings').addEventListener('click', closeSettings);
$('#settings-panel').addEventListener('click', function(e) { if (e.target === this) closeSettings(); });
$('#settingsBtn').addEventListener('click', openSettings);

/* ========================= Router ========================= */
const VIEWS = {};
let CURRENT = 'overview';
function go(view, arg) {
  CURRENT = view;
  document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.view === view));
  disposeCharts();
  $('#content').innerHTML = '';
  VIEWS[view](arg);
}
document.querySelectorAll('.nav-item').forEach(n => n.addEventListener('click', () => go(n.dataset.view)));

$('#globalSearch').addEventListener('keydown', (e) => {
  if (e.key !== 'Enter') return;
  const q = e.target.value.trim();
  if (!q) return;
  if (isFormulaName(q)) go('formula', q);
  else go('sourcing', q);
});

/* ========================= Overview ========================= */
VIEWS.overview = async function () {
  const c = $('#content');
  c.appendChild(el(`<div class="view">
    <div class="view-head"><h2>概览驾驶舱</h2><p>从经典本草到方剂演变 —— 离线证据闭环的全局视图</p></div>
    <div id="ov-stats" class="grid g3" style="margin-bottom:18px"></div>
    <div class="grid g-side">
      <div class="card"><h3><span class="dot"></span>高频药对 Top 12（配伍 + 共现 · PMI）</h3><div id="ov-pairs" class="chart"></div></div>
      <div class="card"><h3><span class="dot"></span>快速入口</h3>
        <p class="muted sm" style="margin-top:0">本草溯源</p>
        <div class="tags" id="ov-herbs"></div>
        <p class="muted sm" style="margin-top:16px">方剂谱系</p>
        <div class="tags" id="ov-formulas"></div>
        <div class="disclaimer">本平台面向中医药科研与知识发现。现代机制为待验证假设，<b style="color:var(--rust)">不生成临床处方、不替代执业医师判断</b>。</div>
      </div>
    </div>
  </div>`));

  ['黃芪', '杜仲', '當歸', '淫羊藿', '骨碎補', '續斷', '牛膝', '熟地黃'].forEach(h =>
    $('#ov-herbs').appendChild(chip(h, () => go('sourcing', h))));
  ['桂枝湯', '四君子湯', '六味地黃丸', '補中益氣湯', '獨活寄生湯', '補陽還五湯'].forEach(f =>
    $('#ov-formulas').appendChild(chip(f, () => go('formula', f), 'gold')));

  try {
    const s = await api('/stats');
    const cards = [
      ['本草 + 方書古籍', s.books, '部'],
      ['章节段落', s.passages, 'passages'],
      ['结构化单味药', s.herb_entries, '条'],
      ['方剂记录', s.formula_formulas, '首'],
      ['唯一方名', s.formula_unique_formula_names, '个'],
      ['谱系/类方边', (s.formula_with_parent || 0) + (s.formula_similarity_edges || 0), '条'],
    ];
    const g = $('#ov-stats');
    cards.forEach(([lab, num]) => g.appendChild(el(
      `<div class="card stat"><div class="num">${(num || 0).toLocaleString()}</div><div class="lab">${lab}</div></div>`)));
    const pairs = (await api('/pairs?limit=12')).pairs;
    renderPairsBar($('#ov-pairs'), pairs);
  } catch (e) { toast('加载失败：' + e.message); }
};

function chip(text, fn, cls = '') {
  const x = el(`<span class="chip ${cls}">${esc(text)}</span>`); x.addEventListener('click', fn); return x;
}

function renderPairsBar(node, pairs) {
  const ch = mkChart(node);
  const data = pairs.slice().reverse();
  ch.setOption({
    grid: { left: 110, right: 30, top: 10, bottom: 20 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, backgroundColor: COL.panel, borderColor: COL.line, textStyle: { color: COL.ink } },
    xAxis: { type: 'value', axisLabel: { color: COL.muted }, splitLine: { lineStyle: { color: COL.line } } },
    yAxis: { type: 'category', data: data.map(p => p.herb_a + '–' + p.herb_b), axisLabel: { color: COL.celadon, fontSize: 12 }, axisLine: { lineStyle: { color: COL.line } } },
    series: [{
      type: 'bar', data: data.map(p => p.count), barWidth: '62%',
      itemStyle: { borderRadius: [0, 6, 6, 0], color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [{ offset: 0, color: COL.jadeDeep }, { offset: 1, color: COL.jade }]) },
      label: { show: true, position: 'right', color: COL.muted, fontSize: 11, formatter: (p) => 'PMI ' + data[p.dataIndex].pmi }
    }]
  });
}

/* ========================= Sourcing ========================= */
VIEWS.sourcing = async function (herb) {
  herb = herb || '黃芪';
  const c = $('#content');
  c.appendChild(el(`<div class="view">
    <div class="view-head"><h2>本草溯源</h2><p>一味药在不同朝代、不同医家体系中的功效与配伍演变，逐条引文可溯</p></div>
    <div class="controls">
      <div class="ctrl"><label>药名</label><input id="sc-in" value="${esc(herb)}" /></div>
      <button class="btn" id="sc-go">溯源</button>
      <span class="muted sm">示例：</span>
      <span class="chip" onclick="go('sourcing','杜仲')">杜仲</span>
      <span class="chip" onclick="go('sourcing','朮')">朮（歧义）</span>
    </div>
    <div id="sc-body"></div>
  </div>`));
  $('#sc-go').addEventListener('click', () => go('sourcing', $('#sc-in').value.trim()));
  $('#sc-in').addEventListener('keydown', e => { if (e.key === 'Enter') go('sourcing', $('#sc-in').value.trim()); });
  $('#topTitle').textContent = '本草溯源 · ' + herb;

  const body = $('#sc-body');
  body.appendChild(el(`<div class="empty"><span class="loader"></span> 检索语料中…</div>`));
  try {
    const [trace, info] = await Promise.all([
      api('/trace/' + encodeURIComponent(herb) + '?limit=30'),
      api('/herb/' + encodeURIComponent(herb)),
    ]);
    body.innerHTML = '';
    if (trace.ambiguous) {
      body.appendChild(el(`<div class="card"><h3><span class="dot" style="background:var(--rust)"></span>名物歧义 · ${esc(trace.herb)}</h3>
        <p class="muted" style="line-height:1.9">${esc(trace.ambiguity_note)}</p>
        <p class="sm" style="color:var(--gold-soft)">⚖ Herb-Hermes 对歧义名物不强行归一，需依朝代 / 主治 / 性味 / 配伍判断。</p></div>`));
      return;
    }
    const ali = (trace.aliases || []).map(a => `<span class="chip muted">${esc(a)}</span>`).join('');
    body.appendChild(el(`<div class="card" style="margin-bottom:18px">
      <div class="flex between center"><h3 style="margin:0"><span class="dot"></span>${esc(trace.herb)}</h3>
      <span class="muted sm">${trace.evidence.length} 条引文 · ${trace.dynasty_timeline.length} 部著录</span></div>
      <div class="tags" style="margin-top:12px">${ali || '<span class="muted sm">（无登记异名）</span>'}</div></div>`));

    body.appendChild(el(`<div class="grid g-side">
      <div class="card"><h3><span class="dot"></span>历代著录时间线</h3><div id="sc-tl" class="chart"></div></div>
      <div class="card"><h3><span class="dot"></span>结构化条目</h3><div id="sc-entry"></div></div>
    </div>`));
    body.appendChild(el(`<div class="grid g-side" style="margin-top:18px">
      <div class="card"><h3><span class="dot"></span>引文证据</h3><div id="sc-evi" class="scroll-y"></div></div>
      <div class="card"><h3><span class="dot"></span>功效 / 配伍图谱</h3><div id="sc-graph" class="chart tall"></div></div>
    </div>`));

    renderTimeline($('#sc-tl'), trace.dynasty_timeline);
    renderEntry($('#sc-entry'), info, herb);
    const evi = $('#sc-evi');
    trace.evidence.forEach(e => evi.appendChild(el(
      `<div class="evi"><div class="cite">▪ ${esc(citation(e))}</div><div class="txt">${esc(e.snippet)}</div></div>`)));
    renderHerbGraph($('#sc-graph'), trace.herb, info.graph_neighbors || []);
  } catch (e) { body.innerHTML = `<div class="empty">未找到该药或加载失败：${esc(e.message)}</div>`; }
};

const citation = (e) => `《${e.book_title}${e.section && e.section !== e.book_title ? '·' + e.section : ''}》${e.dynasty || e.author ? '（' + [e.dynasty, e.author].filter(Boolean).join('·') + '）' : ''}`;

function renderEntry(node, info, herb) {
  const e = (info.entries || [])[0];
  if (!e) { node.innerHTML = `<p class="muted sm">语料中暂无《${esc(herb)}》的结构化條列條目，可参见左侧引文与图谱。</p>`; return; }
  const rows = [['性味', e.nature_flavor], ['归经', e.meridians], ['功用', e.functions], ['主治', e.indications], ['禁忌', e.contraindications], ['炮製', e.processing], ['配伍', e.compatibility]];
  node.innerHTML = `<p class="sm" style="color:var(--gold-soft);margin-top:-4px">据《${esc(e.book_title)}》${esc(e.dynasty)}</p>`;
  rows.forEach(([k, v]) => { if (v) node.appendChild(el(`<div class="field"><div class="k">${k}</div><div class="v">${esc(v.slice(0, 160))}</div></div>`)); });
}

function renderTimeline(node, tl) {
  if (!tl.length) { node.parentElement.innerHTML += '<p class="empty">无时间线数据</p>'; return; }
  const ch = mkChart(node);
  ch.setOption({
    grid: { left: 8, right: 24, top: 14, bottom: 60, containLabel: true },
    tooltip: { trigger: 'axis', backgroundColor: COL.panel, borderColor: COL.line, textStyle: { color: COL.ink }, formatter: p => `${tl[p[0].dataIndex].dynasty || '—'}《${tl[p[0].dataIndex].book}》<br/>提及 ${p[0].value} 次` },
    xAxis: { type: 'category', data: tl.map(t => (t.dynasty || '—') + '·' + t.book), axisLabel: { color: COL.muted, interval: 0, rotate: 42, fontSize: 10 }, axisLine: { lineStyle: { color: COL.line } } },
    yAxis: { type: 'value', name: '提及次数', nameTextStyle: { color: COL.muted }, axisLabel: { color: COL.muted }, splitLine: { lineStyle: { color: COL.line } } },
    series: [{ type: 'bar', data: tl.map(t => t.mentions), barWidth: '55%', itemStyle: { borderRadius: [5, 5, 0, 0], color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: COL.gold }, { offset: 1, color: 'rgba(217,178,95,0.15)' }]) } }]
  });
}

function renderHerbGraph(node, center, neighbors) {
  const ch = mkChart(node);
  const typeColor = { herb: COL.jade, function: COL.gold, meridian: COL.celadon, nature: COL.rust };
  const nodes = [{ name: center, symbolSize: 46, itemStyle: { color: COL.jadeDeep }, label: { color: COL.ink, fontSize: 14, fontWeight: 'bold' }, fixed: true, x: 300, y: 220 }];
  const links = [];
  const seen = new Set([center]);
  neighbors.slice(0, 26).forEach(n => {
    const label = n.label, t = n.type;
    if (seen.has(label)) return; seen.add(label);
    nodes.push({ name: label, symbolSize: t === 'herb' ? 30 : 22, itemStyle: { color: typeColor[t] || COL.muted }, label: { color: COL.muted, fontSize: 11 }, category: t });
    links.push({ source: center, target: label, lineStyle: { color: COL.line, width: 1.3, curveness: 0.12 }, label: { show: false } });
  });
  ch.setOption({
    tooltip: { backgroundColor: COL.panel, borderColor: COL.line, textStyle: { color: COL.ink } },
    legend: { data: ['herb', 'function', 'meridian', 'nature'], textStyle: { color: COL.muted }, top: 0, icon: 'circle' },
    series: [{ type: 'graph', layout: 'force', roam: true, draggable: true, categories: [{ name: 'herb' }, { name: 'function' }, { name: 'meridian' }, { name: 'nature' }],
      force: { repulsion: 220, edgeLength: 90, gravity: 0.08 }, data: nodes, links, lineStyle: { color: COL.line }, emphasis: { focus: 'adjacency' } }]
  });
  ch.on('click', p => { if (p.dataType === 'node' && p.data.category === 'herb' && p.name !== center) go('sourcing', p.name); });
}

/* ========================= Formula ========================= */
VIEWS.formula = async function (name) {
  name = name || '桂枝湯';
  const c = $('#content');
  c.appendChild(el(`<div class="view">
    <div class="view-head"><h2>方剂谱系</h2><p>从源方到衍生方 —— 重建方义结构、历代加减、类方网络与跨书演变</p></div>
    <div class="controls">
      <div class="ctrl"><label>方名</label><input id="fm-in" value="${esc(name)}" /></div>
      <button class="btn" id="fm-go">重建谱系</button>
      <span class="muted sm">示例：</span>
      <span class="chip gold" onclick="go('formula','四君子湯')">四君子湯</span>
      <span class="chip gold" onclick="go('formula','六味地黃丸')">六味地黃丸</span>
    </div>
    <div id="fm-body"></div></div>`));
  $('#fm-go').addEventListener('click', () => go('formula', $('#fm-in').value.trim()));
  $('#fm-in').addEventListener('keydown', e => { if (e.key === 'Enter') go('formula', $('#fm-in').value.trim()); });
  $('#topTitle').textContent = '方剂谱系 · ' + name;

  const body = $('#fm-body');
  body.appendChild(el(`<div class="empty"><span class="loader"></span> 重建谱系中…</div>`));
  try {
    const g = await api('/formula/' + encodeURIComponent(name));
    body.innerHTML = '';
    if (!g.found) { body.appendChild(el(`<div class="empty">语料中未找到方剂「${esc(name)}」。可试：桂枝湯、四君子湯、六味地黃丸、補中益氣湯。</div>`)); return; }
    const p = g.primary;
    const herbs = (p.composition_herbs || []).map(h => `<span class="chip" onclick="go('sourcing','${esc(h)}')">${esc(h)}</span>`).join('');
    body.appendChild(el(`<div class="card" style="margin-bottom:18px">
      <div class="flex between center"><h3 style="margin:0"><span class="dot"></span>${esc(g.name)}</h3>
        <span class="muted sm">代表出处《${esc(p.book)}》${esc(p.dynasty)} ${esc(p.author)} · 类目 ${esc(p.category || '—')}</span></div>
      <div class="tags" style="margin:13px 0">${herbs || '<span class="muted sm">组成未解析</span>'}</div>
      ${p.indications ? `<div class="field"><div class="k">主治</div><div class="v">${esc(p.indications)}</div></div>` : ''}
      ${p.preparation ? `<div class="field"><div class="k">煎服</div><div class="v">${esc(p.preparation)}</div></div>` : ''}
    </div>`));

    if (g.analysis && g.analysis.composition && g.analysis.composition.length) {
      body.appendChild(renderAnalysis(g.analysis));
    }

    body.appendChild(el(`<div class="grid g-side">
      <div class="card"><h3><span class="dot"></span>方剂谱系树（源流 → 本方 → 衍生）</h3><div id="fm-tree" class="chart tall"></div></div>
      <div class="card"><h3><span class="dot"></span>类方网络（组成相似度 Jaccard）</h3><div id="fm-sim" class="chart tall"></div></div>
    </div>`));
    body.appendChild(el(`<div class="grid g-side" style="margin-top:18px">
      <div class="card"><h3><span class="dot"></span>历代演变（同名方跨书著录）</h3><div id="fm-occ" class="scroll-y"></div></div>
      <div class="card"><h3><span class="dot"></span>历代加减记载</h3><div id="fm-deriv"></div></div>
    </div>`));

    renderGenealogyTree($('#fm-tree'), g);
    renderSimNetwork($('#fm-sim'), g);
    renderOccurrences($('#fm-occ'), g.occurrences);
    renderDerivations($('#fm-deriv'), g);
  } catch (e) { body.innerHTML = `<div class="empty">加载失败：${esc(e.message)}</div>`; }
};

const ROLE_COLOR = { '君': '#d9b25f', '臣': '#6fcf97', '佐': '#7fb6d9', '使': '#b08fd9' };
const ROLE_DESC  = { '君': '君药·主病主证', '臣': '臣药·辅助君药', '佐': '佐药·佐助佐制', '使': '使药·引经调和' };

function renderAnalysis(a) {
  const wrap = el(`<div class="card" style="margin-bottom:18px">
    <div class="flex between center"><h3 style="margin:0"><span class="dot" style="background:var(--gold)"></span>君臣佐使 · 剂量古今换算</h3>
    <span class="muted sm">据${esc(a.dynasty)}制 1兩≈${a.liang_grams}g · 全方≈${a.total_grams ?? '—'}g</span></div>
    <div id="an-bars" class="chart short" style="height:200px"></div>
    <table class="tbl" style="margin-top:8px"><thead><tr><th>角色</th><th>药味</th><th>原剂量</th><th>今约</th><th>依据</th></tr></thead><tbody></tbody></table>
    <div class="disclaimer">${esc(a.note)}</div></div>`);
  const tb = wrap.querySelector('tbody');
  a.composition.forEach(it => {
    const g = it.grams != null ? it.grams + ' g' : (it.count_unit ? it.value + it.count_unit : '—');
    tb.appendChild(el(`<tr>
      <td><span class="badge" style="background:${ROLE_COLOR[it.role]}22;color:${ROLE_COLOR[it.role]};border:1px solid ${ROLE_COLOR[it.role]}55">${it.role}</span></td>
      <td class="nm" onclick="go('sourcing','${esc(it.herb)}')">${esc(it.herb)}</td>
      <td class="sm muted">${esc(it.dose_raw || '—')}</td>
      <td class="pmi">${esc(g)}</td>
      <td class="sm muted">${esc(it.reason)}</td></tr>`));
  });
  setTimeout(() => {
    const dosed = a.composition.filter(it => it.grams != null);
    if (!dosed.length) return;
    const ch = mkChart(wrap.querySelector('#an-bars'));
    ch.setOption({
      grid: { left: 60, right: 24, top: 12, bottom: 24 },
      tooltip: { trigger: 'axis', backgroundColor: COL.panel, borderColor: COL.line, textStyle: { color: COL.ink }, formatter: p => `${p[0].name}（${ROLE_DESC[dosed[p[0].dataIndex].role]}）<br/>≈ ${p[0].value} g` },
      xAxis: { type: 'category', data: dosed.map(d => d.herb), axisLabel: { color: COL.celadon, interval: 0, fontSize: 11 }, axisLine: { lineStyle: { color: COL.line } } },
      yAxis: { type: 'value', name: 'g', axisLabel: { color: COL.muted }, splitLine: { lineStyle: { color: COL.line } } },
      series: [{ type: 'bar', data: dosed.map(d => ({ value: d.grams, itemStyle: { color: ROLE_COLOR[d.role], borderRadius: [5, 5, 0, 0] } })), barWidth: '50%',
        label: { show: true, position: 'top', color: COL.muted, fontSize: 10, formatter: p => dosed[p.dataIndex].role } }]
    });
  }, 0);
  return wrap;
}

function renderGenealogyTree(node, g) {
  const kids = (g.descendants || []).slice(0, 14).map(d => ({ name: d.name, value: (d.herbs || []).join('、'), itemStyle: { color: COL.celadon } }));
  let root = { name: g.name, value: (g.primary.composition_herbs || []).join('、'), itemStyle: { color: COL.jade }, label: { fontWeight: 'bold' }, children: kids };
  (g.ancestors || []).forEach(a => { root = { name: a.name, value: (a.herbs || []).join('、'), itemStyle: { color: COL.gold }, children: [root] }; });
  const ch = mkChart(node);
  ch.setOption({
    tooltip: { trigger: 'item', backgroundColor: COL.panel, borderColor: COL.line, textStyle: { color: COL.ink }, formatter: p => `<b>${p.name}</b>${p.value ? '<br/>' + p.value : ''}` },
    series: [{
      type: 'tree', data: [root], top: '4%', left: '12%', bottom: '4%', right: '22%',
      symbolSize: 11, orient: 'LR', expandAndCollapse: false, initialTreeDepth: 4,
      itemStyle: { borderColor: COL.jadeDeep }, lineStyle: { color: COL.line, width: 1.4, curveness: 0.35 },
      label: { color: COL.ink, fontSize: 12, position: 'left', verticalAlign: 'middle', align: 'right' },
      leaves: { label: { position: 'right', align: 'left', color: COL.muted } },
      emphasis: { focus: 'relative' }
    }]
  });
  ch.on('click', p => { if (p.data && p.name !== g.name) go('formula', p.name); });
}

function renderSimNetwork(node, g) {
  const sim = g.similar || [];
  if (!sim.length) { node.innerHTML = '<p class="empty">暂无组成相似的类方。</p>'; node.className = ''; return; }
  const ch = mkChart(node);
  const nodes = [{ name: g.name, symbolSize: 44, itemStyle: { color: COL.jadeDeep }, label: { color: COL.ink, fontWeight: 'bold' }, fixed: true, x: 250, y: 200 }];
  const links = [];
  sim.slice(0, 10).forEach(s => {
    nodes.push({ name: s.name, symbolSize: 18 + s.jaccard * 30, itemStyle: { color: COL.gold }, label: { color: COL.muted, fontSize: 11 } });
    links.push({ source: g.name, target: s.name, value: s.jaccard, lineStyle: { color: COL.line, width: 1 + s.jaccard * 4, curveness: 0.1 }, label: { show: true, formatter: s.jaccard.toFixed(2), color: COL.muted, fontSize: 10 } });
  });
  ch.setOption({
    tooltip: { backgroundColor: COL.panel, borderColor: COL.line, textStyle: { color: COL.ink }, formatter: p => p.dataType === 'edge' ? 'Jaccard ' + p.value.toFixed(3) : p.name },
    series: [{ type: 'graph', layout: 'force', roam: true, draggable: true, force: { repulsion: 260, edgeLength: 110, gravity: 0.1 }, data: nodes, links, emphasis: { focus: 'adjacency' }, edgeLabel: { show: true } }]
  });
  ch.on('click', p => { if (p.dataType === 'node' && p.name !== g.name) go('formula', p.name); });
}

function renderOccurrences(node, occ) {
  if (!occ || !occ.length) { node.innerHTML = '<p class="empty">无</p>'; return; }
  const tl = el('<div class="timeline"></div>');
  occ.forEach(o => tl.appendChild(el(
    `<div class="tl-item"><span class="dyn">${esc(o.dynasty || '—')}</span><span class="bk">《${esc(o.book)}》</span>
     <span class="ct">${esc((o.herbs || []).slice(0, 7).join('、'))}</span></div>`)));
  node.appendChild(tl);
}

function renderDerivations(node, g) {
  const d = g.derivations || [];
  if (!d.length) {
    const desc = (g.descendants || []).slice(0, 12);
    if (!desc.length) { node.innerHTML = '<p class="empty">语料中未见显式加减记载。</p>'; return; }
    node.innerHTML = '<p class="sm muted" style="margin-top:-2px">未见显式「加/去…名…」记载，下列为结构化谱系衍生方：</p>';
    const ul = el('<ul class="list"></ul>');
    desc.forEach(x => ul.appendChild(el(`<li><span style="color:var(--celadon);cursor:pointer" onclick="go('formula','${esc(x.name)}')">${esc(x.name)}</span> — ${esc((x.herbs || []).slice(0, 6).join('、'))}</li>`)));
    node.appendChild(ul); return;
  }
  const ul = el('<ul class="list"></ul>');
  d.forEach(x => ul.appendChild(el(`<li><span style="color:var(--jade)">${esc(x.relation)}</span> ${esc((x.herbs || []).join('、'))} → <span style="color:var(--gold-soft)">${esc(x.target)}</span> <span class="sm">《${esc(x.from_book)}》</span></li>`)));
  node.appendChild(ul);
}

/* ========================= Pairs ========================= */
VIEWS.pairs = async function (herb) {
  const c = $('#content');
  c.appendChild(el(`<div class="view">
    <div class="view-head"><h2>药对配伍</h2><p>基于配伍记载与方剂 / 段落共现的药对挖掘，PMI 量化关联强度</p></div>
    <div class="controls">
      <div class="ctrl"><label>聚焦药味</label><input id="pr-in" placeholder="留空=全局 Top" value="${esc(herb || '')}" /></div>
      <button class="btn" id="pr-go">挖掘</button>
    </div>
    <div class="grid g-side">
      <div class="card"><h3><span class="dot"></span>药对排行</h3><div id="pr-tbl" class="scroll-y"></div></div>
      <div class="card"><h3><span class="dot"></span>配伍网络</h3><div id="pr-net" class="chart tall"></div></div>
    </div></div>`));
  $('#pr-go').addEventListener('click', () => go('pairs', $('#pr-in').value.trim()));
  $('#pr-in').addEventListener('keydown', e => { if (e.key === 'Enter') go('pairs', $('#pr-in').value.trim()); });
  $('#topTitle').textContent = '药对配伍' + (herb ? ' · ' + herb : '');

  try {
    const data = await api('/pairs?limit=40' + (herb ? '&herb=' + encodeURIComponent(herb) : ''));
    const pairs = data.pairs;
    const tbl = $('#pr-tbl');
    if (!pairs.length) { tbl.innerHTML = '<p class="empty">无药对数据</p>'; return; }
    const t = el(`<table class="tbl"><thead><tr><th>药对</th><th>共现</th><th>PMI</th><th>例书</th></tr></thead><tbody></tbody></table>`);
    pairs.forEach(p => t.querySelector('tbody').appendChild(el(
      `<tr><td><span class="nm" onclick="go('sourcing','${esc(p.herb_a)}')">${esc(p.herb_a)}</span> – <span class="nm" onclick="go('sourcing','${esc(p.herb_b)}')">${esc(p.herb_b)}</span></td>
       <td>${p.count}</td><td class="pmi">${p.pmi}</td><td class="sm muted">${esc((p.example_books || []).slice(0, 2).join('、'))}</td></tr>`)));
    tbl.appendChild(t);
    renderPairNet($('#pr-net'), pairs.slice(0, 28), herb);
  } catch (e) { $('#pr-tbl').innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
};

function renderPairNet(node, pairs, focus) {
  const ch = mkChart(node);
  const deg = {}; pairs.forEach(p => { deg[p.herb_a] = (deg[p.herb_a] || 0) + p.count; deg[p.herb_b] = (deg[p.herb_b] || 0) + p.count; });
  const names = Object.keys(deg);
  const max = Math.max(...Object.values(deg));
  const nodes = names.map(n => ({ name: n, symbolSize: 14 + 34 * (deg[n] / max), itemStyle: { color: n === focus ? COL.gold : COL.jade }, label: { color: COL.muted, fontSize: 11 } }));
  const links = pairs.map(p => ({ source: p.herb_a, target: p.herb_b, lineStyle: { color: COL.line, width: 0.8 + Math.log(p.count) * 0.7, curveness: 0.1 } }));
  ch.setOption({
    tooltip: { backgroundColor: COL.panel, borderColor: COL.line, textStyle: { color: COL.ink } },
    series: [{ type: 'graph', layout: 'force', roam: true, draggable: true, force: { repulsion: 150, edgeLength: 80, gravity: 0.06 }, data: nodes, links, emphasis: { focus: 'adjacency', lineStyle: { color: COL.jade } } }]
  });
  ch.on('click', p => { if (p.dataType === 'node') go('sourcing', p.name); });
}

/* ========================= Search ========================= */
VIEWS.search = async function (q) {
  const c = $('#content');
  c.appendChild(el(`<div class="view">
    <div class="view-head"><h2>古籍检索</h2><p>古文友好的 BM25 全文检索，覆盖本草与方書，命中即带《书·篇（朝代·作者）》引文</p></div>
    <div class="controls">
      <div class="ctrl" style="flex:1;max-width:520px"><label>查询</label><input id="se-in" style="flex:1" placeholder="如：強筋骨 補肝腎 / 補氣固表 / 活血化瘀" value="${esc(q || '')}" /></div>
      <button class="btn" id="se-go">检索</button>
    </div>
    <div id="se-body"></div></div>`));
  $('#se-go').addEventListener('click', () => go('search', $('#se-in').value.trim()));
  $('#se-in').addEventListener('keydown', e => { if (e.key === 'Enter') go('search', $('#se-in').value.trim()); });
  if (!q) return;
  const body = $('#se-body');
  body.appendChild(el('<div class="empty"><span class="loader"></span> 检索中…</div>'));
  try {
    const data = await api('/search?limit=20&q=' + encodeURIComponent(q));
    body.innerHTML = '';
    if (!data.results.length) { body.appendChild(el('<div class="empty">无匹配结果</div>')); return; }
    const card = el('<div class="card"></div>');
    card.appendChild(el(`<h3><span class="dot"></span>命中 ${data.results.length} 条 · "${esc(q)}"</h3>`));
    data.results.forEach(r => card.appendChild(el(
      `<div class="evi"><div class="cite">▪ ${esc(r.citation)}<span class="score">score ${r.score}</span></div><div class="txt">${esc(r.snippet)}</div></div>`)));
    body.appendChild(card);
  } catch (e) { body.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
};

/* ========================= Hypothesis ========================= */
VIEWS.hypothesis = async function () {
  const c = $('#content');
  c.appendChild(el(`<div class="view">
    <div class="view-head"><h2>科研假设</h2><p>古籍依据 + 现代机制 + 可验证机制链 —— 自动生成引文落地的 Hypothesis Card</p></div>
    <div class="controls">
      <div class="ctrl"><label>主药</label><input id="hy-herb" value="黃芪" /></div>
      <div class="ctrl"><label>药对</label><input id="hy-partner" value="當歸" placeholder="可选" /></div>
      <div class="ctrl"><label>疾病</label>
        <select id="hy-disease"><option>骨质疏松</option><option>骨折</option></select></div>
      <button class="btn" id="hy-go">生成假设卡</button>
      <button class="btn ghost" id="hy-export">导出报告 ↧</button>
    </div>
    <div id="hy-body"></div></div>`));
  $('#hy-go').addEventListener('click', loadHyp);
  $('#hy-export').addEventListener('click', exportReport);
  $('#topTitle').textContent = '科研假设生成';
  loadHyp();

  async function loadHyp() {
    const herb = $('#hy-herb').value.trim(), partner = $('#hy-partner').value.trim(), disease = $('#hy-disease').value;
    const body = $('#hy-body'); body.innerHTML = '<div class="empty"><span class="loader"></span> 组装证据中…</div>';
    try {
      const card = await api(`/hypothesis?herb=${encodeURIComponent(herb)}${partner ? '&partner=' + encodeURIComponent(partner) : ''}&disease=${encodeURIComponent(disease)}`);
      renderHypCard(body, card);
    } catch (e) { body.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
  }
  async function exportReport() {
    const herb = $('#hy-herb').value.trim(), disease = $('#hy-disease').value;
    try {
      const r = await api(`/report/${encodeURIComponent(herb)}?disease=${encodeURIComponent(disease)}`);
      const blob = new Blob([r.markdown], { type: 'text/markdown' });
      const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `Herb-Hermes_${herb}.md`; a.click();
      toast('已导出 Markdown 报告');
    } catch (e) { toast('导出失败：' + e.message); }
  }
};

function renderHypCard(body, card) {
  const mc = card.mechanism_chain || {};
  const list = (arr) => (arr || []).map(x => `<li>${esc(x)}</li>`).join('');
  body.innerHTML = '';
  body.appendChild(el(`<div class="grid g-side">
    <div class="card">
      <div class="flex between center"><span class="hyp-id">${esc(card.hypothesis_id)}</span><span class="badge b">证据等级 ${esc(card.evidence_score)}</span></div>
      <div class="hyp-q">${esc(card.research_question)} <span class="speak" onclick="speak('${esc(card.research_question)}')">🔊 朗读</span></div>
      <div class="sec-label">古籍证据（语料实证）</div><ul class="list">${list(card.classical_evidence)}</ul>
      <div class="sec-label">现代证据（待外部数据接入）</div><ul class="list">${list(card.modern_evidence)}</ul>
    </div>
    <div>
      <div class="card" style="margin-bottom:18px"><h3><span class="dot"></span>机制链</h3>
        <div class="field"><div class="k">疾病</div><div class="v">${esc(mc.disease)}</div></div>
        <div class="field"><div class="k">证候</div><div class="v">${esc(mc.syndrome)}</div></div>
        <div class="field"><div class="k">方/对</div><div class="v">${esc(mc.formula_or_pair)}</div></div>
        <div class="field"><div class="k">关键轴</div><div class="v" style="color:var(--gold-soft)">${esc(mc.axis)}</div></div>
        <div class="sec-label">候选通路</div><div class="tags">${(mc.pathways || []).map(p => `<span class="chip gold">${esc(p)}</span>`).join('')}</div>
        <div class="sec-label">候选细胞类型</div><div class="tags">${(mc.cell_types || []).map(p => `<span class="chip">${esc(p)}</span>`).join('')}</div>
      </div>
      <div class="card"><h3><span class="dot"></span>验证计划</h3><ul class="list">${list(card.validation_plan)}</ul>
        <div class="sec-label" style="color:var(--rust)">风险与反证</div><ul class="list">${list(card.risk_and_counterevidence)}</ul>
      </div>
    </div></div>`));
  body.appendChild(el(`<div class="disclaimer">⚠ 现代机制为模板化候选假设，须经网络药理学、GEO 差异表达、单细胞定位与实验验证；本卡不构成临床处方建议。</div>`));
}

/* ========================= Agent ========================= */
const TOOL_LABEL = {
  search_corpus: '古籍检索', trace_herb: '本草溯源', herb_info: '结构化条目',
  herb_pairs: '药对挖掘', formula_genealogy: '方剂谱系', analyze_formula: '君臣佐使·剂量',
  formulas_with_herb: '含药方剂', generate_hypothesis: '科研假设',
};

VIEWS.agent = async function () {
  const c = $('#content');
  c.appendChild(el(`<div class="view">
    <div class="view-head"><h2>智能问答</h2><p>大模型自主调用接地工具，在真实古籍证据上推理作答（每步可溯，引文落地）</p></div>
    <div class="agent-toolbar">
      <div id="ag-model-status"></div>
      <button class="btn ghost" style="font-size:12.5px;padding:6px 14px" onclick="openSettings()">⚙ 模型配置</button>
    </div>
    <div class="controls">
      <div class="ctrl" style="flex:1;max-width:640px"><label>提问</label>
        <input id="ag-in" style="flex:1" placeholder="如：补肾强骨可用哪些本草？桂枝汤的君臣佐使？黄芪当归药对科研价值？" /></div>
      <button class="btn" id="ag-go">提问</button>
    </div>
    <div class="tags" style="margin:-6px 0 14px">
      <span class="chip" onclick="agAsk('杜仲的功效与历代著录？')">杜仲历代著录</span>
      <span class="chip gold" onclick="agAsk('桂枝汤的君臣佐使与衍生方？')">桂枝汤君臣佐使</span>
      <span class="chip" onclick="agAsk('补肾活血治疗骨质疏松的候选药对与科研假设？')">骨质疏松候选药对</span>
      <span class="chip" onclick="agAsk('六味地黄丸的类方网络与历代演变？')">六味地黄丸类方</span>
    </div>
    <div id="ag-body"></div></div>`));
  $('#topTitle').textContent = '智能问答 · Herb-Hermes Agent';
  $('#ag-go').addEventListener('click', () => agAsk($('#ag-in').value.trim()));
  $('#ag-in').addEventListener('keydown', e => { if (e.key === 'Enter') agAsk($('#ag-in').value.trim()); });
  _refreshAgentStatus();
};

async function _refreshAgentStatus() {
  const host = $('#ag-model-status');
  if (!host) return;
  if (Settings.hasLocal()) {
    const s = Settings.get();
    const label = (s.model || '').split('/').pop() || '已配置';
    host.innerHTML = `<span class="model-badge"><span class="dot-live"></span>${esc(label)} <span class="muted" style="font-size:11px">· 浏览器设置</span></span>`;
    return;
  }
  try {
    const st = await api('/llm/status');
    if (st.configured) {
      const label = (st.model || '').split('/').pop() || '已配置';
      host.innerHTML = `<span class="model-badge"><span class="dot-live"></span>${esc(label)} <span class="muted" style="font-size:11px">· 服务端</span></span>`;
    } else {
      host.innerHTML = `<span class="model-badge warn">未接入 LLM · <a href="#" onclick="openSettings();return false;" style="color:var(--celadon)">立即配置</a></span>`;
    }
  } catch (e) {
    host.innerHTML = `<span class="muted sm">（离线）</span>`;
  }
}

window.agAsk = function (q) { if ($('#ag-in')) $('#ag-in').value = q; _doAgAsk(q); };
async function agAsk(q) { q = (q || '').trim(); if (q) _doAgAsk(q); }

async function _doAgAsk(q) {
  if (!q) return;

  // Ensure we're in agent view
  if (CURRENT !== 'agent') { go('agent'); await new Promise(r => setTimeout(r, 40)); }
  if ($('#ag-in')) $('#ag-in').value = q;

  const body = $('#ag-body');
  if (!body) return;
  body.innerHTML = '';

  // Question card (will be updated during streaming)
  const qCard = el(`<div class="card" style="margin-bottom:14px">
    <div class="evi" style="border:none"><b style="color:var(--celadon)">问：</b>${esc(q)}</div>
    <div id="ag-status" class="muted sm" style="margin-top:6px"><span class="loader"></span> 判断配置中…</div>
  </div>`);
  body.appendChild(qCard);
  const statusEl = qCard.querySelector('#ag-status');

  // Check if LLM available (local settings or server)
  const hasLocal = Settings.hasLocal();
  let serverConfigured = false;
  if (!hasLocal) {
    try { const st = await api('/llm/status'); serverConfigured = st.configured; } catch (e) {}
  }

  if (!hasLocal && !serverConfigured) {
    statusEl.innerHTML = '<span class="muted sm">⚡ 规则模式（未配置 LLM · <a href="#" onclick="openSettings();return false;" style="color:var(--celadon)">配置模型</a>）</span>';
    await _agRuleBasedFallback(q, body);
    return;
  }

  statusEl.innerHTML = '<span class="loader"></span> 智能体推理中…';

  // Streaming steps card (shown when first tool fires)
  const stepsCard = el(`<div class="card" style="display:none;margin-bottom:14px">
    <h3><span class="dot" style="background:var(--gold)"></span>推理过程 <span id="ag-step-count" class="muted sm"></span></h3>
    <div id="ag-steps-live"></div></div>`);
  body.appendChild(stepsCard);

  const payload = Settings.agentPayload({ question: q });
  let stepIdx = 0;
  let thinkingEl = null;
  let thinkingBuf = '';

  try {
    const resp = await fetch(API + '/agent/stream', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (resp.status === 503) {
      statusEl.innerHTML = '<span class="muted sm">⚡ 规则模式（服务端未配置 LLM）</span>';
      await _agRuleBasedFallback(q, body);
      return;
    }
    if (!resp.ok) throw new Error('HTTP ' + resp.status);

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const parts = buf.split('\n\n');
      buf = parts.pop() || '';
      for (const part of parts) {
        if (!part.startsWith('data: ')) continue;
        let event;
        try { event = JSON.parse(part.slice(6)); } catch (e) { continue; }

        if (event.type === 'thinking') {
          thinkingBuf += event.content;
          if (!thinkingEl) {
            thinkingEl = el(`<details class="think-block"><summary>MiniMax 思考过程</summary><pre class="think-text"></pre></details>`);
            qCard.insertBefore(thinkingEl, statusEl);
          }
          thinkingEl.querySelector('.think-text').textContent = thinkingBuf;
        } else if (event.type === 'tool') {
          stepIdx++;
          stepsCard.style.display = '';
          stepsCard.querySelector('#ag-step-count').textContent = `(${stepIdx} 步)`;
          stepsCard.querySelector('#ag-steps-live').appendChild(el(
            `<div class="evi"><div class="cite">▸ 第${stepIdx}步 · <b>${esc(TOOL_LABEL[event.step.tool] || event.step.tool)}</b></div>
             <div class="txt">${_stepSummary(event.step)}</div></div>`));
          statusEl.innerHTML = `<span class="loader"></span> 执行第 ${stepIdx} 步 · ${esc(TOOL_LABEL[event.step.tool] || event.step.tool)}…`;
        } else if (event.type === 'done') {
          statusEl.innerHTML = '';
          _renderAgentAnswer(body, event.result, stepsCard);
        } else if (event.type === 'error') {
          statusEl.innerHTML = `<span style="color:var(--rust)">出错：${esc(event.content)}</span>`;
        }
      }
    }
  } catch (e) {
    statusEl.innerHTML = `<span style="color:var(--rust)">网络出错：${esc(e.message)}</span>`;
  }
}

function _renderAgentAnswer(body, res, stepsCard) {
  const ans = el(`<div class="card" style="margin-bottom:14px">
    <h3><span class="dot"></span>回答 <span class="speak" onclick="speak(${JSON.stringify(res.answer)})">🔊 朗读</span></h3>
    <div style="line-height:1.95;white-space:pre-wrap">${esc(res.answer)}</div>
    ${res.citations && res.citations.length
      ? '<div class="sec-label">引文</div><div class="tags">' + res.citations.map(c => `<span class="chip muted">${esc(c)}</span>`).join('') + '</div>'
      : ''}
    <div class="disclaimer">回答由大模型综合工具检索的古籍证据生成；现代机制为待验证假设，不构成临床处方建议。模型：${esc(res.model || '—')}</div>
  </div>`);
  if (stepsCard && stepsCard.parentNode) {
    stepsCard.parentNode.insertBefore(ans, stepsCard);
  } else {
    body.appendChild(ans);
    // Fallback: render steps if stepsCard wasn't used
    if (res.steps && res.steps.length) {
      const sc = el(`<div class="card"><h3><span class="dot" style="background:var(--gold)"></span>推理过程（${res.steps.length} 步）</h3><div></div></div>`);
      body.appendChild(sc);
      const host = sc.querySelector('div');
      res.steps.forEach((s, i) => {
        const argStr = Object.entries(s.arguments || {}).map(([k, v]) => `${k}=${v}`).join(', ');
        host.appendChild(el(`<div class="evi"><div class="cite">▸ 第${i+1}步 · <b>${esc(TOOL_LABEL[s.tool] || s.tool)}</b> <span class="sm muted">(${esc(argStr)})</span></div>
          <div class="txt">${_stepSummary(s)}</div></div>`));
      });
    }
  }
}

function _stepSummary(s) {
  const r = s.result || {};
  if (r.error) return `<span style="color:var(--rust)">${esc(r.error)}</span>`;
  if (r.results) return r.results.slice(0, 3).map(x => `${esc(x.citation)}：${esc(x.snippet)}`).join('<br>') || '（无命中）';
  if (r.evidence) return `异名 ${esc((r.aliases || []).join('、') || '—')}；证据 ${r.evidence.length} 条，例：${esc((r.evidence[0] || {}).citation || '')}`;
  if (r.found && r.composition) return '组成：' + esc((Array.isArray(r.composition) ? r.composition : []).map(x => x.herb || x).join('、'));
  if (r.pairs) return '药对：' + esc(r.pairs.slice(0, 6).map(p => `${p.with}(${p.count})`).join('、'));
  if (r.formulas) return `${r.count} 首，例：` + esc(r.formulas.slice(0, 5).map(f => f.name).join('、'));
  if (r.hypothesis_id) return `假设卡 ${esc(r.hypothesis_id)}：${esc(r.research_question || '')}`;
  if (r.found === false) return '（未找到）';
  return esc(_trim(JSON.stringify(r), 160));
}
function _trim(s, n) { return s.length > n ? s.slice(0, n) + '…' : s; }

/* ---- Rule-based fallback (when no LLM configured) ---- */
async function _agRuleBasedFallback(q, body) {
  const fallCard = el(`<div class="card">
    <h3><span class="dot" style="background:var(--muted)"></span>规则检索结果</h3>
    <div class="rule-mode-badge">⚡ 规则模式 · <a href="#" onclick="openSettings();return false;">配置大语言模型</a>以获得智能综合回答</div>
    <div id="ag-rule-content"></div>
  </div>`);
  body.appendChild(fallCard);
  const content = fallCard.querySelector('#ag-rule-content');

  // 1. BM25 full-text search
  try {
    const sr = await api('/search?limit=6&q=' + encodeURIComponent(q));
    if (sr.results.length) {
      const sec = el('<div></div>');
      sec.appendChild(el('<div class="sec-label">引文检索（BM25）</div>'));
      sr.results.slice(0, 4).forEach(r => sec.appendChild(el(
        `<div class="evi"><div class="cite">▪ ${esc(r.citation)}<span class="score">score ${r.score}</span></div>
         <div class="txt">${esc(r.snippet)}</div></div>`)));
      content.appendChild(sec);
    }
  } catch (e) {}

  // 2. Detect formula names in query
  const words = q.match(/[一-龥]{2,10}/g) || [];
  for (const w of words) {
    if (!isFormulaName(w)) continue;
    try {
      const g = await api('/formula/' + encodeURIComponent(w));
      if (!g.found) continue;
      const herbs = (g.primary.composition_herbs || []).slice(0, 8)
        .map(h => `<span class="chip" onclick="go('sourcing','${esc(h)}')">${esc(h)}</span>`).join('');
      const sec = el('<div></div>');
      sec.appendChild(el(`<div class="sec-label">方剂谱系 · ${esc(w)}</div>`));
      sec.appendChild(el(`<div style="margin-bottom:8px"><div class="tags">${herbs || '—'}</div></div>`));
      if (g.ancestors.length || g.descendants.length) {
        sec.appendChild(el(`<p class="sm muted" style="margin:4px 0">源方：${esc((g.ancestors[0]||{}).name||'—')} · 衍生 ${g.descendants.length} 首</p>`));
      }
      sec.appendChild(el(`<button class="btn ghost" style="margin-top:6px;font-size:12px" onclick="go('formula','${esc(w)}')">查看完整谱系 →</button>`));
      content.appendChild(sec);
    } catch (e) {}
    break;
  }

  // 3. Detect herb names → trace
  for (const w of words) {
    if (isFormulaName(w) || w.length < 2) continue;
    try {
      const tr = await api('/trace/' + encodeURIComponent(w) + '?limit=5');
      if (!tr.found && !tr.evidence) continue;
      const n = (tr.evidence || []).length;
      if (!n) continue;
      const sec = el('<div></div>');
      sec.appendChild(el(`<div class="sec-label">本草溯源 · ${esc(w)}（${n} 条引文）</div>`));
      (tr.evidence || []).slice(0, 2).forEach(e => sec.appendChild(el(
        `<div class="evi"><div class="cite">▪ ${esc(e.citation || '')}</div><div class="txt">${esc(e.snippet)}</div></div>`)));
      sec.appendChild(el(`<button class="btn ghost" style="margin-top:6px;font-size:12px" onclick="go('sourcing','${esc(w)}')">完整溯源 →</button>`));
      content.appendChild(sec);
      break;
    } catch (e) {}
  }

  content.appendChild(el(`<div class="disclaimer" style="margin-top:14px">
    配置大语言模型后，智能体将自动调用以上工具并综合生成带引文的分析回答。
    <a href="#" onclick="openSettings();return false;" style="color:var(--celadon)">立即配置 MiniMax / OpenAI / Anthropic →</a>
  </div>`));
}

/* ========================= Voice ========================= */
const Voice = {
  serverASR: false, serverTTS: false, recognizing: false, rec: null, mediaRec: null, chunks: [],
  async init() {
    try {
      const s = await api('/voice/status');
      this.serverASR = s.asr && s.asr.configured;
      this.serverTTS = s.tts && s.tts.configured && s.tts.has_default_prompt;
    } catch (e) { /* offline: browser only */ }
  },
  dispatch(text) {
    const q = (text || '').trim().replace(/[。.\s]+$/, '');
    if (!q) return;
    $('#globalSearch').value = q;
    if (isFormulaName(q)) go('formula', q); else go('sourcing', q);
    toast('🎤 ' + q);
  },
  async toggleMic() {
    const btn = $('#micBtn');
    if (this.recognizing) { this.stop(); return; }
    if (this.serverASR && navigator.mediaDevices) { return this.recordServer(btn); }
    return this.browserASR(btn);
  },
  browserASR(btn) {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { toast('当前浏览器不支持语音识别，且服务端 ASR 未配置'); return; }
    const rec = new SR(); this.rec = rec;
    rec.lang = 'zh-CN'; rec.interimResults = false; rec.maxAlternatives = 1;
    rec.onstart = () => { this.recognizing = true; btn.classList.add('rec'); };
    rec.onerror = () => toast('识别失败，请重试');
    rec.onend = () => { this.recognizing = false; btn.classList.remove('rec'); };
    rec.onresult = (e) => this.dispatch(e.results[0][0].transcript);
    rec.start();
  },
  async recordServer(btn) {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.mediaRec = new MediaRecorder(stream); this.chunks = [];
    this.mediaRec.ondataavailable = (e) => this.chunks.push(e.data);
    this.mediaRec.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      const blob = new Blob(this.chunks, { type: 'audio/webm' });
      try {
        const r = await fetch(API + '/voice/asr', { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: blob });
        if (!r.ok) throw new Error('server ASR ' + r.status);
        const d = await r.json(); this.dispatch(d.text);
      } catch (e) { toast('服务端识别失败，回退浏览器'); this.browserASR(btn); }
    };
    this.recognizing = true; btn.classList.add('rec'); this.mediaRec.start();
  },
  stop() {
    this.recognizing = false; $('#micBtn').classList.remove('rec');
    if (this.rec) try { this.rec.stop(); } catch (e) {}
    if (this.mediaRec && this.mediaRec.state !== 'inactive') this.mediaRec.stop();
  },
  async speak(text) {
    if (!text) return;
    if (this.serverTTS) {
      try {
        const r = await fetch(API + '/voice/tts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) });
        if (r.ok) { new Audio(URL.createObjectURL(await r.blob())).play(); return; }
      } catch (e) { /* fall back */ }
    }
    if (window.speechSynthesis) {
      const u = new SpeechSynthesisUtterance(text); u.lang = 'zh-CN'; u.rate = 0.95;
      speechSynthesis.cancel(); speechSynthesis.speak(u);
    } else { toast('当前环境不支持朗读'); }
  }
};
window.speak = (t) => Voice.speak(t);
$('#micBtn').addEventListener('click', () => Voice.toggleMic());

/* ========================= Boot ========================= */
Voice.init();
go('overview');
