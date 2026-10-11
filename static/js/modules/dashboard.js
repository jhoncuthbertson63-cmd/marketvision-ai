import * as U from '../ui.js';
const PER = [['1d', '1D'], ['1w', '1W'], ['1m', '1M'], ['ytd', 'YTD'], ['1y', '1Y'], ['5y', '5Y']];
let state = { per: '1d', heat: 'chg_1d', secPer: '1m' };

export default {
  async render(el) {
    el.innerHTML = `
      <div class="hero"><div><h1>Market Intelligence</h1><p class="sub" style="margin:0">What is moving, where capital is rotating, and what's scheduled next — from sourced, timestamped data.</p></div>
      ${U.legend()}</div>
      <div class="grid g5" id="idx">${'<div class="panel kpi"><div class="skel"></div><div class="skel" style="margin-top:10px;height:24px"></div></div>'.repeat(5)}</div>
      <div class="grid" style="grid-template-columns:2fr 1fr;margin-top:14px" id="row2">
        <div id="heatP"></div><div class="grid" id="breadthP" style="align-content:start"></div>
      </div>
      <div class="grid g2" style="margin-top:14px"><div id="secP"></div><div id="rotP"></div></div>
      <div class="grid g3" style="margin-top:14px" id="moversP"></div>
      <div style="margin-top:14px" id="macroP"></div>
      <div class="grid g2" style="margin-top:14px"><div id="earnP"></div><div id="econP"></div></div>
      ${U.disclaimer()}`;
    const r2 = el.querySelector('#row2'); if (innerWidth < 980) r2.style.gridTemplateColumns = '1fr';
    loadIndexes(el); loadHeat(el); loadSectors(el); loadMacro(el); loadCal(el);
  }
};

async function loadIndexes(el) {
  const box = el.querySelector('#idx');
  let d; try { d = await U.api('/api/dashboard/indexes'); } catch (e) { box.outerHTML = U.unavailable('major indexes', e.message); return; }
  const show = ['^GSPC', '^IXIC', '^DJI', '^RUT', '^VIX'];
  const by = Object.fromEntries(d.items.map(i => [i.symbol, i]));
  const draw = () => {
    box.innerHTML = show.map(s => {
      const i = by[s]; if (!i || i.error) return `<div class="panel kpi">${U.unavailable(i?.name || s, i?.error)}</div>`;
      const v = i.perf[state.per];
      return `<div class="panel kpi" data-s="${s}"><div class="n"><span>${U.esc(i.name)}</span><span class="dim mono">${state.per.toUpperCase()}</span></div>
        <div class="v">${U.num(i.price)}</div><div class="c">${U.cpct(v)}</div><div class="spark"></div>
        <div class="dim" style="font-size:10.5px;margin-top:4px">${U.lbl('delayed', 'Delayed')} ${U.fmtTime(i.meta.as_of, 'America/New_York', 'ET')}</div></div>`;
    }).join('');
    box.querySelectorAll('.kpi[data-s]').forEach(k => { k.onclick = () => { const m = { '^GSPC': 'SPY', '^IXIC': 'QQQ', '^DJI': 'DIA', '^RUT': 'IWM' }[k.dataset.s]; if (m) location.hash = '#/research/' + m; }; const i = by[k.dataset.s]; U.sparkline(k.querySelector('.spark'), i.spark, (i.perf['1y'] ?? 0) >= 0); });
  };
  draw();
  // performance table panel after index cards
  const rows = ['^GSPC', '^IXIC', '^DJI', '^RUT', 'SPY', 'QQQ', 'DIA', 'IWM', 'RSP', '^VIX'].map(s => by[s]).filter(Boolean);
  const tbl = `<div class="tw"><table class="t"><thead><tr><th>Index / ETF</th><th>Last</th>${PER.map(p => `<th>${p[1]}</th>`).join('')}<th>3Y</th><th>vs 200DMA</th><th>1Y vol</th></tr></thead><tbody>
    ${rows.map(i => i.error ? `<tr><td>${U.esc(i.name)}</td><td colspan="10" class="l" style="color:var(--warn)">data unavailable</td></tr>` :
    `<tr class="click" data-s="${i.symbol}"><td>${U.esc(i.name)} <span class="dim mono">${i.symbol}</span></td><td>${U.num(i.price)}</td>${PER.map(p => `<td>${U.cpct(i.perf[p[0]])}</td>`).join('')}<td>${U.cpct(i.perf['3y'])}</td>
      <td>${i.perf.above200 ? '<span class="up">above</span>' : '<span class="dn">below</span>'}</td><td>${U.pct(i.perf.vol_1y, 1, false)}</td></tr>`).join('')}</tbody></table></div>`;
  const meta = rows.find(i => i.meta)?.meta;
  const host = document.createElement('div'); host.style.marginTop = '14px';
  host.innerHTML = U.panel({ title: 'Index performance', right: U.chips('per', PER, state.per), body: tbl, foot: U.src(meta, '<span>Returns use dividend/split-adjusted closes; 1D uses the latest quote.</span>') });
  box.after(host);
  U.onChips(host, 'per', v => { state.per = v; draw(); loadHeat(el, true); loadSectors(el, true); });
  host.querySelectorAll('tr[data-s]').forEach(tr => tr.onclick = () => { const s = tr.dataset.s; if (!s.startsWith('^')) location.hash = '#/research/' + s; });
  window.__rsp = d.rsp_minus_spy; window.__rspNote = d.rsp_note; renderBreadth(el);
}

let heatData = null;
async function loadHeat(el, redraw) {
  const p = el.querySelector('#heatP');
  if (!redraw) { p.innerHTML = U.panel({ title: 'Market heat map', body: U.loading('Loading ~110 large caps (first load can take ~30s)…') }); }
  if (!heatData || !redraw) { try { heatData = await U.api('/api/dashboard/heatmap'); } catch (e) { p.innerHTML = U.panel({ title: 'Market heat map', body: U.unavailable('heat map', e.message) }); return; } }
  const d = heatData;
  if (d.error) { p.innerHTML = U.panel({ title: 'Market heat map', body: U.unavailable('heat map', d.error) }); return; }
  const H = [['chg_1d', '1D'], ['chg_1w', '1W'], ['chg_1m', '1M'], ['chg_ytd', 'YTD'], ['chg_52w', '52W']];
  p.innerHTML = U.panel({ title: 'Market heat map', right: `<span class="dim" style="font-size:11px">size = market cap · color = return · click to research</span>` + U.chips('heat', H, state.heat), body: '<div class="heat"></div>', foot: U.src(d.meta) });
  U.onChips(p, 'heat', v => { state.heat = v; loadHeat(el, true); });
  const k = state.heat, lim = { chg_1d: 3, chg_1w: 6, chg_1m: 10, chg_ytd: 30, chg_52w: 40 }[k];
  const col = v => { if (v == null) return '#2a3340'; const t = Math.max(-1, Math.min(1, v / lim)); const a = Math.abs(t);
    return t >= 0 ? `rgb(${Math.round(30 - 20 * a)},${Math.round(60 + 120 * a)},${Math.round(60 + 30 * a)})` : `rgb(${Math.round(70 + 170 * a)},${Math.round(50 - 10 * a)},${Math.round(60 - 5 * a)})`; };
  const secs = {}; d.items.forEach(i => (secs[i.sector] ||= []).push(i));
  const data = Object.entries(secs).map(([s, arr]) => ({ name: s, children: arr.map(i => ({ name: i.symbol, value: i.market_cap || 1, chg: i[k], full: i.name, itemStyle: { color: col(i[k]) } })) }));
  const c = U.chart(p.querySelector('.heat'), {
    tooltip: { formatter: x => x.data.chg !== undefined ? `<b>${x.name}</b> ${U.esc(x.data.full || '')}<br>${H.find(h => h[0] === k)[1]}: ${U.pct(x.data.chg)}<br>Mkt cap: ${U.money(x.value)}` : `<b>${x.name}</b>` },
    series: [{ type: 'treemap', data, roam: false, nodeClick: false, breadcrumb: { show: false }, width: '100%', height: '100%', top: 0, left: 0,
      label: { show: true, formatter: x => x.data.chg !== undefined ? `{a|${x.name}}\n{b|${U.pct(x.data.chg, 1)}}` : x.name, rich: { a: { fontWeight: 700, fontSize: 12, color: '#fff' }, b: { fontSize: 10.5, color: '#ffffffcc' } } },
      upperLabel: { show: true, height: 18, color: '#cfd8e3', fontSize: 11, fontWeight: 600, backgroundColor: 'transparent' },
      itemStyle: { borderColor: U.isDark() ? '#07090d' : '#fff', borderWidth: 1, gapWidth: 1 },
      levels: [{ itemStyle: { borderWidth: 3, borderColor: U.isDark() ? '#07090d' : '#fff', gapWidth: 3 } }, { itemStyle: { borderWidth: 1, gapWidth: 1 } }] }]
  });
  c && c.on('click', x => { if (x.data && x.data.chg !== undefined) location.hash = '#/research/' + x.name; });
  if (!redraw) { renderBreadth(el); renderMovers(el); }
}

function renderBreadth(el) {
  const p = el.querySelector('#breadthP'); if (!p) return;
  const b = heatData?.breadth, r = window.__rsp;
  const gauge = (lab, v) => `<div style="margin:8px 0"><div style="display:flex;justify-content:space-between;font-size:12px"><span class="muted">${lab}</span><b class="mono">${v == null ? '—' : v.toFixed(0) + '%'}</b></div><div class="bar"><i style="width:${v || 0}%"></i></div></div>`;
  p.innerHTML = U.panel({ title: 'Market breadth', right: U.lbl('derived'), body: b ? `
      <div class="stats" style="grid-template-columns:repeat(3,1fr)"><div class="stat"><span class="k">Advancers</span><span class="v up">${b.advancers}</span></div><div class="stat"><span class="k">Decliners</span><span class="v dn">${b.decliners}</span></div><div class="stat"><span class="k">Near 52W high</span><span class="v">${b.near_52w_high}</span></div></div>
      ${gauge('Above 50-day average', b.pct_above_50dma)}${gauge('Above 200-day average', b.pct_above_200dma)}
      ${r ? `<h3 style="margin-top:12px">Equal-weight vs cap-weight (RSP − SPY)</h3><div class="stats" style="grid-template-columns:repeat(4,1fr)">${Object.entries(r).map(([k, v]) => `<div class="stat"><span class="k">${k.toUpperCase()}</span><span class="v">${U.cpct(v, 1)}</span></div>`).join('')}</div><p class="dim" style="font-size:11px;margin:6px 0 0">${U.esc(window.__rspNote)}</p>` : ''}`
      : U.loading(), foot: b ? `<div class="pf">${U.esc(b.note)}</div>` : '' });
}

function renderMovers(el) {
  const d = heatData, p = el.querySelector('#moversP');
  const t = (rows, cols) => `<div class="tw"><table class="t"><thead><tr><th>Ticker</th>${cols.map(c => `<th>${c[0]}</th>`).join('')}</tr></thead><tbody>${rows.map(i => `<tr class="click" data-s="${i.symbol}"><td class="tk">${i.symbol}</td>${cols.map(c => `<td>${c[1](i)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  p.innerHTML = U.panel({ title: 'Unusual volume', right: U.lbl('derived'), body: t(d.unusual_volume, [['Rel. vol', i => U.mult(i.rel_volume, 2)], ['1D', i => U.cpct(i.chg_1d)], ['Volume', i => U.big(i.volume)]]), foot: `<div class="pf">Rel. vol = latest session volume ÷ 3-month average daily volume (Yahoo Finance). Universe: ${d.items.length} large caps.</div>` })
    + U.panel({ title: 'Biggest moves (1D)', body: t([...d.gainers.slice(0, 5), ...d.losers.slice(0, 5)], [['Price', i => U.num(i.price)], ['1D', i => U.cpct(i.chg_1d)], ['1M', i => U.cpct(i.chg_1m, 1)]]), foot: U.src(d.meta) })
    + U.panel({ title: '1-month momentum leaders', right: U.lbl('derived'), body: t(d.momentum_1m, [['1M', i => U.cpct(i.chg_1m, 1)], ['YTD', i => U.cpct(i.chg_ytd, 1)], ['From 52W hi', i => U.cpct(i.pct_from_52w_high, 1)]]), foot: `<div class="pf">Momentum computed from daily adjusted closes (Yahoo Finance).</div>` });
  p.querySelectorAll('tr[data-s]').forEach(tr => tr.onclick = () => location.hash = '#/research/' + tr.dataset.s);
}

let secData = null;
async function loadSectors(el, redraw) {
  const p = el.querySelector('#secP'), q = el.querySelector('#rotP');
  if (!redraw) { p.innerHTML = U.panel({ title: 'Sector performance', body: U.loading() }); q.innerHTML = U.panel({ title: 'Sector rotation', body: U.loading() }); }
  if (!secData || !redraw) { try { secData = await U.api('/api/dashboard/sectors'); } catch (e) { p.innerHTML = U.panel({ title: 'Sector performance', body: U.unavailable('sector ETFs', e.message) }); q.innerHTML = ''; return; } }
  const ok = secData.items.filter(i => !i.error), per = state.per === '1d' ? '1d' : state.per;
  const sorted = [...ok].sort((a, b) => (b.perf[per] ?? -1e9) - (a.perf[per] ?? -1e9));
  p.innerHTML = U.panel({ title: 'Sector performance', right: `<span class="dim mono" style="font-size:11px">${per.toUpperCase()} · SPDR sector ETFs</span>`, body: '<div class="chart"></div>', foot: U.src(secData.meta, '<span>Change period with the chips in "Index performance".</span>') });
  U.chart(p.querySelector('.chart'), {
    grid: { left: 110, right: 50, top: 6, bottom: 20 }, tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: v => U.pct(v) },
    xAxis: { type: 'value', ...U.axisStyle(), axisLabel: { ...U.axisStyle().axisLabel, formatter: v => v + '%' } },
    yAxis: { type: 'category', inverse: true, data: sorted.map(i => `${i.name} (${i.symbol})`), ...U.axisStyle() },
    series: [{ type: 'bar', data: sorted.map(i => ({ value: +(i.perf[per] ?? 0).toFixed(2), itemStyle: { color: (i.perf[per] ?? 0) >= 0 ? '#19c37d' : '#ff5466', borderRadius: 3 } })), label: { show: true, position: 'right', formatter: x => U.pct(x.value, 1), color: '#9aa8ba', fontSize: 10.5 } }]
  });
  q.innerHTML = U.panel({ title: 'Sector rotation — where capital appears to be flowing', right: U.lbl('derived'), body: '<div class="chart"></div>', foot: `<div class="pf">${U.esc(secData.rotation_rule)}</div>` });
  const qc = { Leading: '#19c37d', Weakening: '#f5b84a', Improving: '#4da3ff', Lagging: '#ff5466' };
  U.chart(q.querySelector('.chart'), {
    grid: { left: 44, right: 20, top: 20, bottom: 34 },
    tooltip: { formatter: x => `<b>${x.data.name}</b> (${x.data.sym})<br>3M vs SPY: ${U.pct(x.data.value[0])}<br>RS momentum: ${U.pct(x.data.value[1])}<br>${x.data.q}` },
    xAxis: { type: 'value', name: '3M relative strength vs SPY', nameLocation: 'middle', nameGap: 22, nameTextStyle: { color: '#66768a', fontSize: 10.5 }, ...U.axisStyle() },
    yAxis: { type: 'value', name: 'RS momentum', nameTextStyle: { color: '#66768a', fontSize: 10.5 }, ...U.axisStyle() },
    series: [{ type: 'scatter', symbolSize: 13, data: ok.map(i => ({ name: i.name, sym: i.symbol, q: i.rotation.quadrant, value: [+i.rotation.x.toFixed(2), +i.rotation.y.toFixed(2)], itemStyle: { color: qc[i.rotation.quadrant] } })),
      label: { show: true, formatter: x => x.data.sym, position: 'right', fontSize: 10, color: '#9aa8ba' },
      markLine: { silent: true, symbol: 'none', lineStyle: { color: '#3a4656', type: 'dashed' }, data: [{ xAxis: 0 }, { yAxis: 0 }], label: { show: false } },
      markArea: { silent: true, data: [] } }],
    graphic: [['Leading', '78%', '6%'], ['Weakening', '78%', '86%'], ['Improving', '9%', '6%'], ['Lagging', '9%', '86%']].map(([t, l, tp]) => ({ type: 'text', left: l, top: tp, style: { text: t, fill: qc[t] + '99', font: '600 11px Inter' } }))
  });
}

async function loadMacro(el) {
  const p = el.querySelector('#macroP');
  p.innerHTML = U.panel({ title: 'Rates, volatility & the economy', body: U.loading() });
  let d; try { d = await U.api('/api/dashboard/macro'); } catch (e) { p.innerHTML = U.panel({ title: 'Rates & economy', body: U.unavailable('FRED', e.message) }); return; }
  const by = Object.fromEntries(d.items.map(i => [i.id, i]));
  const card = i => i.error ? `<div class="panel">${U.unavailable(i.name, i.error)}</div>` : `<div class="panel" style="padding:10px 12px">
      <div style="display:flex;justify-content:space-between;font-size:11.5px"><span class="muted">${U.esc(i.name)}</span>${U.lbl('fact')}</div>
      <div style="display:flex;align-items:baseline;gap:8px"><span class="mono" style="font-size:19px;font-weight:600">${i.unit === '$' ? '$' : ''}${i.id === 'ICSA' ? U.big(i.value) : U.num(i.value, 2)}${i.unit === '%' ? '%' : ''}</span>
      <span class="mono" style="font-size:11.5px">${i.change_1y != null ? `<span class="${i.change_1y > 0 ? 'up' : 'dn'}">${i.change_1y > 0 ? '+' : ''}${i.id === 'ICSA' ? U.big(i.change_1y) : i.change_1y.toFixed(2)}</span> <span class="dim">1y</span>` : ''}</span></div>
      <div class="spark" style="height:38px" data-id="${i.id}"></div>
      <div class="dim" style="font-size:10.5px">As of ${i.date} · <a href="${i.meta.url}" target="_blank" rel="noopener">FRED ${i.id}</a></div></div>`;
  const curve = ['DGS3MO', 'DGS2', 'DGS10'].map(s => by[s]).filter(x => x && !x.error);
  p.innerHTML = U.panel({ title: 'Rates, volatility & the economy', right: U.lbl('fact', 'Official data'), body: `<div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(200px,1fr))">${d.items.map(card).join('')}</div>
     ${curve.length === 3 ? `<div class="callout" style="margin-top:12px">Yield curve snapshot: 3M ${curve[0].value.toFixed(2)}% · 2Y ${curve[1].value.toFixed(2)}% · 10Y ${curve[2].value.toFixed(2)}% → 10Y−3M = <b class="mono">${(curve[2].value - curve[0].value).toFixed(2)}pp</b> (${curve[2].value - curve[0].value < 0 ? 'inverted' : 'positively sloped'}). ${U.lbl('derived')}</div>` : ''}`,
    foot: U.src(d.items.find(i => i.meta)?.meta, '<span>Each series updates on its own release schedule (daily/weekly/monthly/quarterly).</span>') });
  p.querySelectorAll('.spark[data-id]').forEach(s => { const i = by[s.dataset.id]; U.chart(s, { grid: { left: 0, right: 0, top: 3, bottom: 0 }, xAxis: { type: 'category', show: false, data: i.series.map(x => x[0]) }, yAxis: { type: 'value', show: false, scale: true }, tooltip: { trigger: 'axis', valueFormatter: v => U.num(v) }, series: [{ type: 'line', data: i.series.map(x => x[1]), showSymbol: false, lineStyle: { width: 1.3, color: '#4da3ff' }, areaStyle: { color: '#4da3ff18' } }] }); });
}

async function loadCal(el) {
  const a = el.querySelector('#earnP'), b = el.querySelector('#econP');
  a.innerHTML = U.panel({ title: 'Upcoming earnings', body: U.loading() }); b.innerHTML = U.panel({ title: 'Economic calendar (US)', body: U.loading() });
  let d; try { d = await U.api('/api/dashboard/calendar'); } catch (e) { a.innerHTML = U.panel({ title: 'Upcoming earnings', body: U.unavailable('earnings calendar', e.message) }); b.innerHTML = ''; return; }
  const day = s => new Date(s + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
  const tm = { 'time-pre-market': 'Pre-mkt', 'time-after-hours': 'After-close', 'time-not-supplied': '—' };
  a.innerHTML = U.panel({ title: 'Upcoming earnings', right: U.lbl('estimate', 'EPS = consensus'), body: d.earnings.length ? `<div class="tw" style="max-height:420px"><table class="t"><thead><tr><th>Date</th><th>Ticker</th><th class="l">Company</th><th>When</th><th>Mkt cap</th><th>EPS est.</th><th>Yr-ago EPS</th></tr></thead><tbody>
      ${d.earnings.map(x => `<tr class="click" data-s="${U.esc(x.symbol)}"><td class="l">${day(x.date)}</td><td class="tk">${U.esc(x.symbol)}</td><td class="l" style="max-width:220px;overflow:hidden;text-overflow:ellipsis">${U.esc(x.name)}</td><td>${tm[x.time] || '—'}</td><td>${U.money(x.market_cap, 0)}</td><td>${U.esc(x.eps_forecast || '—')}</td><td>${U.esc(x.last_year_eps || '—')}</td></tr>`).join('')}</tbody></table></div>`
      : U.unavailable('earnings', 'No large-cap reports found in the next 7 business days from the source.'), foot: U.src(d.meta_earnings) });
  a.querySelectorAll('tr[data-s]').forEach(tr => tr.onclick = () => location.hash = '#/research/' + tr.dataset.s);
  b.innerHTML = U.panel({ title: 'Economic calendar (US)', right: U.lbl('estimate', 'Consensus'), body: d.economic.length ? `<div class="tw" style="max-height:420px"><table class="t"><thead><tr><th>Date</th><th>GMT</th><th class="l">Event</th><th>Actual</th><th>Cons.</th><th>Prior</th></tr></thead><tbody>
      ${d.economic.map(x => `<tr><td class="l">${day(x.date)}</td><td>${U.esc(x.gmt)}</td><td class="l" style="white-space:normal">${U.esc(x.event)}</td><td>${U.esc(x.actual || '—')}</td><td>${U.esc(x.consensus || '—')}</td><td>${U.esc(x.previous || '—')}</td></tr>`).join('')}</tbody></table></div>`
      : U.unavailable('economic events', 'No US events returned for the next 7 business days.'), foot: U.src(d.meta_econ) + (d.errors.length ? `<div class="pf stale">${U.esc(d.errors.join('; '))}</div>` : '') });
}
