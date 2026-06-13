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

async function api(path) {
  const r = await fetch(API + path);
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

/* ----------------------------- Router ----------------------------- */
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

/* --------------------------- Overview ----------------------------- */
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
      ['谱系/类方边', (s.formula_with_parent || 0) + (s.formula_similarity_edges || 0), '条']
    ];
    const g = $('#ov-stats');
    cards.forEach(([lab, num, sub], i) => g.appendChild(el(
      `<div class="card stat"><div class="num">${(num || 0).toLocaleString()}</div><div class="lab">${lab}</div><div class="sub">${sub}</div></div>`)));
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

/* --------------------------- Sourcing ----------------------------- */
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
    const [trace, info] = await Promise.all([api('/trace/' + encodeURIComponent(herb) + '?limit=30'), api('/herb/' + encodeURIComponent(herb))]);
    body.innerHTML = '';
    if (trace.ambiguous) {
      body.appendChild(el(`<div class="card"><h3><span class="dot" style="background:var(--rust)"></span>名物歧义 · ${esc(trace.herb)}</h3>
        <p class="muted" style="line-height:1.9">${esc(trace.ambiguity_note)}</p>
        <p class="sm" style="color:var(--gold-soft)">⚖ Herb-Hermes 对歧义名物不强行归一，需依朝代 / 主治 / 性味 / 配伍判断 —— 此为名物考订的专业壁垒。</p></div>`));
      return;
    }
    // header card
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

/* ---------------------------- Formula ----------------------------- */
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

function renderGenealogyTree(node, g) {
  // ancestors (outermost first) -> name -> descendants
  const kids = (g.descendants || []).slice(0, 14).map(d => ({ name: d.name, value: (d.herbs || []).join('、'), itemStyle: { color: COL.celadon } }));
  let root = { name: g.name, value: (g.primary.composition_herbs || []).join('、'), itemStyle: { color: COL.jade }, label: { fontWeight: 'bold' }, children: kids };
  // wrap ancestors as parents (nearest first in array)
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
  if (!sim.length) { node.parentElement.querySelector('.chart').innerHTML = ''; node.innerHTML = '<p class="empty">暂无组成相似的类方（该方含较多通用药，区分度低）。</p>'; node.className = ''; return; }
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

/* ----------------------------- Pairs ------------------------------ */
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

/* ----------------------------- Search ----------------------------- */
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
    card.appendChild(el(`<h3><span class="dot"></span>命中 ${data.results.length} 条 · “${esc(q)}”</h3>`));
    data.results.forEach(r => card.appendChild(el(
      `<div class="evi"><div class="cite">▪ ${esc(r.citation)}<span class="score">score ${r.score}</span></div><div class="txt">${esc(r.snippet)}</div></div>`)));
    body.appendChild(card);
  } catch (e) { body.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
};

/* --------------------------- Hypothesis --------------------------- */
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
      <div class="hyp-q">${esc(card.research_question)}</div>
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

/* ----------------------------- Boot ------------------------------- */
go('overview');
