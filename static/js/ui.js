// Shared UI helpers: fetch, formatting, source footers, evidence labels, charts.
export const $ = (s, el = document) => el.querySelector(s);
const charts = [];
export const STATIC = !!window.MV_STATIC;
let _tickers = null;
export async function staticTickers() {
  if (!_tickers) { const r = await fetch('data/tickers.json', { cache: 'no-cache' }); _tickers = (await r.json()).tickers || {}; }
  return _tickers;
}
export class NotGenerated extends Error {}
function staticPath(url) {
  const [p] = url.split('?');
  if (p === '/api/modules') return 'data/modules.json';
  if (p.startsWith('/api/dashboard/')) return 'data/dashboard/' + p.slice(15) + '.json';
  if (p === '/api/scanner') return 'data/scanner.json';
  if (p === '/api/scanner/radar') return 'data/radar.json';
  if (p.startsWith('/api/research/')) return 'data/research/' + p.slice(14) + '.json';
  return null;
}
export async function api(url) {
  if (STATIC) {
    if (url.startsWith('/api/search')) {
      const q = decodeURIComponent(url.split('q=')[1] || '').trim().toUpperCase(); const T = await staticTickers();
      const all = Object.entries(T).map(([s, v]) => ({ symbol: s, name: v.name || '' }));
      const hits = all.filter(x => x.symbol.startsWith(q)).sort((a, b) => (a.symbol !== q) - (b.symbol !== q) || a.symbol.length - b.symbol.length);
      const more = q.length >= 2 ? all.filter(x => !x.symbol.startsWith(q) && x.name.toUpperCase().includes(q)) : [];
      return { results: [...hits, ...more].slice(0, 8) };
    }
    const sp = staticPath(url);
    const r = await fetch(sp, { cache: 'no-cache' });
    if (r.status === 404 && url.startsWith('/api/research/')) throw new NotGenerated('not pre-generated');
    if (!r.ok) throw new Error(`Snapshot file missing (HTTP ${r.status})`);
    const j = await r.json(); if (j && j.error && Object.keys(j).length === 1) throw new Error(j.error); return j;
  }
  const r = await fetch(url);
  let j; try { j = await r.json(); } catch { throw new Error(`HTTP ${r.status}`); }
  if (!r.ok) throw new Error(j.detail || j.error || `HTTP ${r.status}`);
  return j;
}
export const isDark = () => document.documentElement.dataset.theme !== 'light';
export function esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
export function num(v, d = 2) { return v == null || isNaN(v) ? '—' : Number(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }); }
export function pct(v, d = 2, sign = true) { if (v == null || isNaN(v)) return '—'; return (sign && v > 0 ? '+' : '') + Number(v).toFixed(d) + '%'; }
export function cpct(v, d = 2) { if (v == null || isNaN(v)) return '<span class="dim">—</span>'; return `<span class="${v > 0 ? 'up' : v < 0 ? 'dn' : ''}">${pct(v, d)}</span>`; }
export function money(v, d = 2) {
  if (v == null || isNaN(v)) return '—'; const a = Math.abs(v), s = v < 0 ? '-' : '';
  if (a >= 1e12) return `${s}$${(a / 1e12).toFixed(d)}T`; if (a >= 1e9) return `${s}$${(a / 1e9).toFixed(d)}B`;
  if (a >= 1e6) return `${s}$${(a / 1e6).toFixed(1)}M`; if (a >= 1e3) return `${s}$${(a / 1e3).toFixed(1)}K`; return `${s}$${a.toFixed(d)}`;
}
export function mult(v, d = 1) { return v == null || isNaN(v) ? '—' : `${Number(v).toFixed(d)}×`; }
export function big(v) { if (v == null) return '—'; const a = Math.abs(v); if (a >= 1e9) return (v / 1e9).toFixed(2) + 'B'; if (a >= 1e6) return (v / 1e6).toFixed(1) + 'M'; if (a >= 1e3) return (v / 1e3).toFixed(0) + 'K'; return String(v); }
const KIND = { fact: 'Fact · reported', derived: 'Derived · calculated', estimate: 'Analyst estimate', model: 'Model forecast', editorial: 'Interpretation', ai: 'AI-generated', news: 'News', speculation: 'Speculation' };
export function lbl(kind, text) { return `<span class="lbl ${kind}" title="${KIND[kind] || kind}">${text || (KIND[kind] || kind).split(' ·')[0]}</span>`; }
export function legend() {
  return `<div class="legend"><span class="dim">Evidence labels:</span>${lbl('fact', 'Fact')} reported in filings/market data ${lbl('derived', 'Derived')} arithmetic on facts ${lbl('estimate', 'Estimate')} third-party analyst consensus ${lbl('model', 'Model')} MarketVision formula forecast ${lbl('editorial', 'Interpretation')} rule-based reading ${lbl('ai', 'AI')} LLM text</div>`;
}
function ago(iso) {
  if (!iso) return ''; const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 90) return 'just now'; if (s < 3600) return `${Math.round(s / 60)} min ago`; if (s < 86400) return `${Math.round(s / 3600)} h ago`; return `${Math.round(s / 86400)} d ago`;
}
export function fmtTime(iso, tz = 'America/Chicago', lab = 'CT') {
  if (!iso) return '—'; return new Date(iso).toLocaleString('en-US', { timeZone: tz, month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) + ' ' + lab;
}
export function src(m, extra = '') {
  if (!m) return `<div class="pf"><span class="stale">Source attribution unavailable</span></div>`;
  return `<div class="pf"><span>Source: ${m.url ? `<a href="${esc(m.url)}" target="_blank" rel="noopener">${esc(m.source)}</a>` : esc(m.source)}</span>
    ${m.fetched_at ? `<span title="${esc(m.fetched_at)}">Fetched ${fmtTime(m.fetched_at)} (${ago(m.fetched_at)})</span>` : ''}
    ${m.as_of ? `<span>Data as of ${fmtTime(m.as_of, 'America/New_York', 'ET')}</span>` : ''}
    ${m.delayed ? `<span>${lbl('delayed', 'Delayed')} ${esc(m.delayed)}</span>` : ''}
    ${m.stale ? `<span class="stale">⚠ Served from cache — upstream refresh failed</span>` : ''}
    ${m.note ? `<span>${esc(m.note)}</span>` : ''}${extra}</div>`;
}
export function unavailable(what, why) { return `<div class="unavail"><b>Data unavailable — ${esc(what)}</b>${esc(why || 'The upstream source did not respond. No placeholder values are shown.')}</div>`; }
export function loading(t = 'Loading live data…') { return `<div class="loading">${esc(t)}</div>`; }
export function panel({ title, right = '', body = '', foot = '', cls = '', id = '' }) {
  return `<section class="panel ${cls}" ${id ? `id="${id}"` : ''}><div class="ph"><h2>${title}</h2><span class="sp"></span>${right}</div><div class="pb">${body}</div>${foot}</section>`;
}
export function chips(name, opts, on) { return `<div class="chips" data-chips="${name}">${opts.map(([v, t]) => `<button class="chip ${v === on ? 'on' : ''}" data-v="${v}">${t}</button>`).join('')}</div>`; }
export function onChips(root, name, fn) {
  root.querySelectorAll(`[data-chips="${name}"] .chip`).forEach(b => b.onclick = () => {
    b.parentElement.querySelectorAll('.chip').forEach(x => x.classList.toggle('on', x === b)); fn(b.dataset.v);
  });
}
export function chart(el, opt) {
  if (!el || !window.echarts) return null;
  const old = echarts.getInstanceByDom(el); if (old) old.dispose();
  const c = echarts.init(el, isDark() ? 'dark' : null, { renderer: 'canvas' });
  c.setOption({ backgroundColor: 'transparent', textStyle: { fontFamily: 'Inter,system-ui,sans-serif' }, animationDuration: 500, ...opt });
  charts.push(c); return c;
}
export function disposeCharts() { while (charts.length) { try { charts.pop().dispose(); } catch { } } }
window.addEventListener('resize', () => charts.forEach(c => { try { c.resize(); } catch { } }));
export const axisStyle = () => ({ axisLine: { lineStyle: { color: isDark() ? '#2a3646' : '#cfd7e2' } }, splitLine: { lineStyle: { color: isDark() ? '#1a222d' : '#eef1f5' } }, axisLabel: { color: isDark() ? '#8796aa' : '#4a5a70', fontSize: 10.5 } });
export function sparkline(el, pts, up) {
  return chart(el, { grid: { left: 0, right: 0, top: 2, bottom: 0 }, xAxis: { type: 'time', show: false }, yAxis: { type: 'value', show: false, scale: true },
    series: [{ type: 'line', data: pts, showSymbol: false, lineStyle: { width: 1.5, color: up ? '#19c37d' : '#ff5466' }, areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: up ? '#19c37d33' : '#ff546633' }, { offset: 1, color: 'transparent' }]) } }], tooltip: { show: false } });
}
export function initSearch() {
  const q = $('#q'), box = $('#sugg'); let t, items = [], sel = -1;
  const go = s => { box.style.display = 'none'; q.value = ''; q.blur(); location.hash = `#/research/${encodeURIComponent(s.toUpperCase())}`; };
  const draw = () => { box.innerHTML = items.map((x, i) => `<div class="${i === sel ? 'on' : ''}" data-s="${esc(x.symbol)}"><b>${esc(x.symbol)}</b><span class="muted">${esc(x.name)}</span></div>`).join(''); box.style.display = items.length ? 'block' : 'none'; box.querySelectorAll('div').forEach(d => d.onmousedown = () => go(d.dataset.s)); };
  q.oninput = () => { clearTimeout(t); const v = q.value.trim(); if (!v) { items = []; draw(); return; } t = setTimeout(async () => { try { items = (await api('/api/search?q=' + encodeURIComponent(v))).results; sel = -1; draw(); } catch { } }, 160); };
  q.onkeydown = e => {
    if (e.key === 'ArrowDown') { sel = Math.min(items.length - 1, sel + 1); draw(); e.preventDefault(); }
    else if (e.key === 'ArrowUp') { sel = Math.max(-1, sel - 1); draw(); e.preventDefault(); }
    else if (e.key === 'Enter') { const v = sel >= 0 ? items[sel].symbol : q.value.trim(); if (v) go(v); }
    else if (e.key === 'Escape') { box.style.display = 'none'; }
  };
  q.onblur = () => setTimeout(() => box.style.display = 'none', 150);
  document.addEventListener('keydown', e => { if (e.key === '/' && document.activeElement !== q) { e.preventDefault(); q.focus(); } });
}
export const disclaimer = () => `<div class="disclaimer">MarketVision AI is a research tool, not investment advice. Prices are delayed and may be end-of-day. Analyst estimates are third-party opinions; model forecasts are formula outputs from stated assumptions and are not predictions or guarantees. Always verify against the linked primary sources.</div>`;
