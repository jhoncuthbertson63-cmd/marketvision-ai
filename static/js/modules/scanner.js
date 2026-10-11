import * as U from '../ui.js';

export default {
  async render(el) {
    el.innerHTML = `<div class="hero"><div><h1>Future Growth Opportunity Scanner</h1><p class="sub" style="margin:0">Industries ranked by measurable evidence — constituent revenue growth from SEC filings, thematic-ETF trend & risk, and valuation — with every formula shown.</p></div>${U.legend()}</div>
      <div id="sc">${U.loading('Scanning ~100 companies across 14 industries (first run pulls SEC filings; can take 1–2 minutes)…')}</div>
      <div style="margin-top:14px" id="radar"></div>${U.disclaimer()}`;
    loadRadar(el.querySelector('#radar'));
    let d; try { d = await U.api('/api/scanner'); } catch (e) { el.querySelector('#sc').innerHTML = U.unavailable('scanner', e.message); return; }
    draw(el.querySelector('#sc'), d);
  }
};

function draw(box, d) {
  const I = d.industries;
  box.innerHTML = `<div class="grid" style="grid-template-columns:minmax(0,1.25fr) minmax(0,1fr)" id="scTop">
    ${U.panel({ title: 'Industry ranking', right: U.lbl('model', 'Evidence-weighted score'), body: `<div class="tw"><table class="t" id="rank"><thead><tr><th>#</th><th class="l">Industry</th><th>Score</th><th>Growth</th><th>Valuation</th><th>Risk</th><th>Stage</th><th>Signal</th><th>Med. rev YoY</th><th>ETF 1Y</th></tr></thead><tbody>
      ${I.map(x => `<tr class="click" data-id="${x.id}"><td>${x.rank}</td><td class="l"><b>${U.esc(x.name)}</b> <span class="dim mono">${x.evidence.etf.symbol}</span></td>
        <td><b>${x.scores.composite.toFixed(0)}</b><div class="bar" style="width:60px;margin-left:auto"><i style="width:${x.scores.composite}%"></i></div></td>
        <td>${x.scores.growth.toFixed(0)}</td><td>${x.scores.valuation.toFixed(0)}</td><td>${x.scores.risk.toFixed(0)}</td>
        <td><span class="badge ${x.stage}">${x.stage}</span></td><td><span class="badge ${x.signal}">${x.signal}</span></td>
        <td>${U.cpct(x.evidence.median_rev_ttm_yoy, 1)}</td><td>${U.cpct(x.evidence.etf['1y'], 1)}</td></tr>
`).join('')}</tbody></table></div>
      <p class="dim" style="font-size:11px;margin:8px 0 0">Click an industry for its evidence, constituents and score breakdown. Scores are relative to the industries scanned (0–100).</p>`, foot: U.src(d.meta) })}
    ${U.panel({ title: 'Growth evidence vs valuation', right: '<span class="dim" style="font-size:11px">bubble size = lower risk</span>', body: '<div class="chart lg" id="bub"></div>', foot: `<div class="pf">x = Growth Evidence score, y = Valuation Attractiveness score. Upper-right = strong measured growth at relatively lower multiples.</div>` })}
  </div>
  <div id="detail" style="margin-top:14px"></div>
  <div class="grid g2" style="margin-top:14px">
    ${U.panel({ title: 'Scoring methodology (fully transparent)', right: U.lbl('model'), body: `<div class="formula">${Object.entries(d.formula).map(([k, v]) => `<div><b style="color:var(--tx)">${k}</b>: ${U.esc(v)}</div>`).join('')}</div>
      <p class="dim" style="font-size:11px">Missing evidence scores a neutral 50 for that component. Company lists are editorial selections of US SEC filers; thematic ETF prices are market facts.</p>` })}
    ${U.panel({ title: 'Constituent revenue growth by industry', right: U.lbl('derived'), body: '<div class="chart lg" id="revbar"></div>', foot: `<div class="pf">Median TTM revenue YoY vs median 3-year CAGR of each industry’s companies (SEC filings). Bars above the 3-yr marker = accelerating.</div>` })}
  </div>`;
  if (innerWidth < 980) box.querySelector('#scTop').style.gridTemplateColumns = '1fr';
  const show = (id, scroll) => {
    const x = I.find(x => x.id === id), ex = box.querySelector('#detail');
    box.querySelectorAll('#rank tr.click').forEach(t => t.style.background = t.dataset.id === id ? '#4da3ff14' : '');
    ex.innerHTML = U.panel({ title: `#${x.rank} ${U.esc(x.name)} — evidence & constituents`, right: `<span class="badge ${x.stage}">${x.stage}</span> <span class="badge ${x.signal}">${x.signal}</span> <b class="mono">Score ${x.scores.composite.toFixed(0)}</b>`, body: detail(x), foot: U.src(d.meta) });
    aggChart(ex.querySelector('.aggc'), x);
    ex.querySelectorAll('tr[data-s]').forEach(t => t.onclick = () => location.hash = '#/research/' + t.dataset.s);
    if (scroll) ex.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };
  box.querySelectorAll('#rank tr.click').forEach(tr => tr.onclick = () => show(tr.dataset.id, true));
  show(I[0].id, false);
  const sc = { 'Early-stage': '#b18cff', Expanding: '#19c37d', Mature: '#8fa3bf', Declining: '#ff5466' };
  U.chart(box.querySelector('#bub'), {
    grid: { left: 44, right: 20, top: 16, bottom: 40 }, tooltip: { formatter: p => `<b>${p.data.name}</b><br>Growth ${p.data.value[0].toFixed(0)} · Valuation ${p.data.value[1].toFixed(0)} · Risk ${p.data.risk.toFixed(0)}<br>Stage: ${p.data.stage}` },
    xAxis: { type: 'value', min: 0, max: 100, name: 'Growth Evidence', nameLocation: 'middle', nameGap: 24, nameTextStyle: { color: '#66768a' }, ...U.axisStyle() },
    yAxis: { type: 'value', min: 0, max: 100, name: 'Valuation Attractiveness', nameTextStyle: { color: '#66768a' }, ...U.axisStyle() },
    series: [{ type: 'scatter', data: I.map(x => ({ name: x.name, stage: x.stage, risk: x.scores.risk, value: [x.scores.growth, x.scores.valuation], symbolSize: 14 + (100 - x.scores.risk) / 3.5, itemStyle: { color: sc[x.stage] + 'cc', borderColor: sc[x.stage] } })),
      label: { show: true, formatter: p => p.data.name.split(' ')[0].replace(/[,&]/g, ''), position: 'top', fontSize: 10, color: '#9aa8ba' },
      markLine: { silent: true, symbol: 'none', lineStyle: { color: '#3a4656', type: 'dashed' }, data: [{ xAxis: 50 }, { yAxis: 50 }], label: { show: false } } }]
  });
  const s2 = [...I].sort((a, b) => (b.evidence.median_rev_ttm_yoy ?? -99) - (a.evidence.median_rev_ttm_yoy ?? -99));
  U.chart(box.querySelector('#revbar'), {
    grid: { left: 150, right: 30, top: 24, bottom: 20 }, legend: { top: 0, textStyle: { color: '#8796aa', fontSize: 10.5 } }, tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: v => U.pct(v, 1) },
    xAxis: { type: 'value', ...U.axisStyle(), axisLabel: { ...U.axisStyle().axisLabel, formatter: v => v + '%' } }, yAxis: { type: 'category', inverse: true, data: s2.map(x => x.name.replace(' (emerging)', '').replace(' (emerging adjacency)', '')), ...U.axisStyle() },
    series: [{ name: 'Median TTM revenue YoY', type: 'bar', data: s2.map(x => +(x.evidence.median_rev_ttm_yoy ?? 0).toFixed(1)), itemStyle: { color: '#4da3ff', borderRadius: 3 } },
      { name: 'Median 3-yr CAGR', type: 'scatter', symbol: 'diamond', symbolSize: 10, data: s2.map(x => +(x.evidence.median_rev_cagr_3y ?? 0).toFixed(1)), itemStyle: { color: '#f5b84a' } }]
  });
}

function detail(x) {
  const e = x.evidence, s = x.scores, c = s.components;
  const stat = (k, v, kind = 'derived') => `<div class="stat"><span class="k">${k} ${U.lbl(kind)}</span><span class="v">${v}</span></div>`;
  return `<div style="padding:8px 4px">
   <div class="grid g2">
    <div><h3>Measured evidence (${U.esc(e.coverage)})</h3><div class="stats">
      ${stat('Median rev. YoY (TTM)', U.cpct(e.median_rev_ttm_yoy, 1))}${stat('Median 3Y rev. CAGR', U.cpct(e.median_rev_cagr_3y, 1))}${stat('Median 5Y rev. CAGR', U.cpct(e.median_rev_cagr_5y, 1))}${stat('Median acceleration', U.cpct(e.median_acceleration, 1))}
      ${stat('Aggregate rev. CAGR', U.cpct(e.aggregate_revenue_cagr, 1))}${stat('Median fwd P/E', U.mult(e.median_fwd_pe) + (e.pe_not_meaningful ? ' <span class="dim" style="font-size:10px">n/m</span>' : ''), 'estimate')}${stat('Median P/S', U.mult(e.median_ps), 'derived')}${stat('Median net margin', U.pct(e.median_net_margin, 1, false))}${stat('% profitable', U.pct(e.pct_profitable, 0, false))}</div>
     <h3 style="margin-top:10px">${U.esc(e.etf.symbol)} — ${U.esc(e.etf.name || '')} ${U.lbl('fact', 'Market data')}</h3><div class="stats">
      ${['3m', '6m', '1y', '3y', '5y'].map(k => stat(k.toUpperCase(), U.cpct(e.etf[k], 1), 'fact')).join('')}${stat('RS vs SPY 6M', U.cpct(e.etf.rs_6m, 1))}${stat('1Y volatility', U.pct(e.etf.vol_1y, 0, false))}${stat('3Y max drawdown', U.pct(e.etf.max_dd_3y, 0))}${stat('vs 200DMA', e.etf.above200 ? '<span class="up">above</span>' : '<span class="dn">below</span>')}</div></div>
    <div><h3>Constituent revenue (same-company aggregate, SEC)</h3><div class="chart sm aggc"></div>
      <p class="dim" style="font-size:11px;margin:4px 0">Companies in aggregate: ${U.esc(e.aggregate_companies.join(', ') || '—')}</p></div></div>
   <div class="tw" style="margin-top:10px"><table class="t"><thead><tr><th>Company</th><th>Mkt cap</th><th>Rev TTM</th><th>Rev YoY</th><th>3Y CAGR</th><th>Accel.</th><th>Net margin</th><th>Fwd P/E</th><th>P/S</th><th>52W</th></tr></thead><tbody>
    ${x.companies.map(k => k.error && k.revenue_ttm_yoy === undefined ? `<tr><td class="l"><span class="mono">${k.symbol}</span></td><td colspan="9" class="l" style="color:var(--warn)">${U.esc(k.error)} — excluded from medians</td></tr>` :
    `<tr class="click" data-s="${k.symbol}"><td class="l"><span class="mono" style="color:var(--acc)">${k.symbol}</span> <span class="dim">${U.esc(k.name || '')}</span></td><td>${U.money(k.market_cap)}</td><td>${U.money(k.revenue_ttm)}</td><td>${U.cpct(k.revenue_ttm_yoy, 1)}</td><td>${U.cpct(k.revenue_cagr_3y, 1)}</td><td>${U.cpct(k.acceleration, 1)}</td><td>${U.pct(k.net_margin_ttm, 1, false)}</td><td>${k.fwd_pe > 0 ? U.mult(k.fwd_pe) : '—'}</td><td>${U.mult(k.ps)}</td><td>${U.cpct(k.chg_52w, 1)}</td></tr>`).join('')}</tbody></table></div>
   <div class="grid g3" style="margin-top:10px">
    <div><h3>Score breakdown ${U.lbl('model')}</h3><div class="math">Growth ${s.growth.toFixed(1)} = .35×${c.p_ttm_yoy.toFixed(0)} + .25×${c.p_cagr3.toFixed(0)} + .20×${c.p_accel.toFixed(0)} + .20×${c.p_rs6m.toFixed(0)}
Valuation ${s.valuation.toFixed(1)} = .4×(100−${c.p_fwd_pe.toFixed(0)}) + .3×(100−${c.p_gadj_pe.toFixed(0)}) + .3×(100−${c.p_ps.toFixed(0)})${e.pe_not_meaningful ? '\n  (P/E not meaningful: <50% of constituents have positive fwd EPS → P/S percentile used)' : ''}
Risk ${s.risk.toFixed(1)} = .5×${c.p_vol.toFixed(0)} + .3×${c.p_dd.toFixed(0)} + .2×(100−${c.p_profitable.toFixed(0)})
Score ${s.composite.toFixed(1)} = .5×${s.growth.toFixed(1)} + .3×${s.valuation.toFixed(1)} + .2×(100−${s.risk.toFixed(1)})</div></div>
    <div><h3>Stage & early indicators</h3><p><span class="badge ${x.stage}">${x.stage}</span> <span class="badge ${x.signal}">${x.signal}</span></p><p class="dim" style="font-size:11.5px">Stage and signal follow the published rules (see methodology). Acceleration ${U.pct(e.median_acceleration, 1)} · ETF 3M RS ${U.pct(e.etf.rs_3m, 1)}.</p>
     <h3>Market size & projected growth</h3>${x.market_size ? `<p>${U.lbl('fact', 'Cited')} ${U.esc(x.market_size.metric)}: $${x.market_size.value_usd_bn}B (${x.market_size.year}), projected CAGR ${x.market_size.projected_cagr_pct}% (${U.esc(x.market_size.projection_horizon)}) — <a href="${U.esc(x.market_size.url)}" target="_blank" rel="noopener">${U.esc(x.market_size.source)}</a></p>` : `<div class="unavail" style="padding:8px 10px"><b>Needs licensed research data</b>No cited market-size source configured. Add one in data/market_sizes.json.</div>`}</div>
    <div><h3>Growth drivers to monitor ${U.lbl('editorial', 'Editorial thesis')}</h3><ul class="narr">${x.drivers.map(d => `<li>${U.lbl('speculation', 'Thesis')} ${U.esc(d)}</li>`).join('')}</ul><p class="dim" style="font-size:11px">Qualitative drivers are hypotheses to verify, not measured data.</p>
     <h3>Valuation & investment risks</h3><p style="font-size:12px">Growth-adjusted P/E ${s.growth_adj_pe == null ? '—' : s.growth_adj_pe.toFixed(2)} · Volatility ${U.pct(e.etf.vol_1y, 0, false)} · Drawdown ${U.pct(e.etf.max_dd_3y, 0)} · ${U.pct(e.pct_profitable, 0, false)} profitable.</p></div></div></div>`;
}

function aggChart(el, x) {
  const a = x.evidence.aggregate_revenue; if (!a?.length) { el.innerHTML = U.unavailable('aggregate', 'Not enough complete histories.'); return; }
  U.chart(el, { grid: { left: 54, right: 8, top: 10, bottom: 22 }, tooltip: { trigger: 'axis', valueFormatter: v => U.money(v) }, xAxis: { type: 'category', data: a.map(p => 'FY' + p[0]), ...U.axisStyle() }, yAxis: { type: 'value', ...U.axisStyle(), axisLabel: { ...U.axisStyle().axisLabel, formatter: v => U.money(v, Math.abs(v) >= 1e12 ? 1 : 0) } }, series: [{ type: 'bar', data: a.map(p => p[1]), itemStyle: { color: '#4da3ff', borderRadius: [3, 3, 0, 0] } }] });
}

async function loadRadar(box) {
  box.innerHTML = U.panel({ title: 'Emerging themes radar', body: U.loading() });
  let d; try { d = await U.api('/api/scanner/radar'); } catch (e) { box.innerHTML = U.panel({ title: 'Emerging themes radar', body: U.unavailable('radar', e.message) }); return; }
  box.innerHTML = U.panel({ title: 'Emerging themes radar — momentum beyond the core list', right: U.lbl('derived', 'Price momentum only'), body: `<div class="grid" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr)" id="rg"><div class="tw" style="max-height:440px"><table class="t"><thead><tr><th class="l">Theme (ETF)</th><th>1M</th><th>3M</th><th>1Y</th><th>RS 3M</th><th>RS accel.</th><th>Flag</th></tr></thead><tbody>
    ${d.items.map(r => r.error ? `<tr><td class="l">${U.esc(r.name)} <span class="dim">${r.symbol}</span></td><td colspan="6" class="l" style="color:var(--warn)">data unavailable</td></tr>` : `<tr><td class="l">${U.esc(r.name)} <span class="dim mono">${r.symbol}</span></td><td>${U.cpct(r['1m'], 1)}</td><td>${U.cpct(r['3m'], 1)}</td><td>${U.cpct(r['1y'], 1)}</td><td>${U.cpct(r.rs_3m, 1)}</td><td>${U.cpct(r.rs_accel, 0)}</td><td>${r.emerging ? '<span class="badge Accelerating">Emerging momentum</span>' : ''}</td></tr>`).join('')}</tbody></table></div><div class="chart lg" id="radc"></div></div>`, foot: U.src(d.meta, `<span>${U.esc(d.rule)}</span>`) });
  if (innerWidth < 980) box.querySelector('#rg').style.gridTemplateColumns = '1fr';
  const ok = d.items.filter(r => !r.error);
  U.chart(box.querySelector('#radc'), { grid: { left: 44, right: 14, top: 14, bottom: 36 }, tooltip: { formatter: p => `<b>${p.data.name}</b> (${p.data.sym})<br>RS 12M ${U.pct(p.data.value[0], 1)} · RS 3M ${U.pct(p.data.value[1], 1)}` },
    xAxis: { type: 'value', name: '12-mo return vs SPY', nameLocation: 'middle', nameGap: 22, nameTextStyle: { color: '#66768a' }, ...U.axisStyle() }, yAxis: { type: 'value', name: '3-mo return vs SPY', nameTextStyle: { color: '#66768a' }, ...U.axisStyle() },
    series: [{ type: 'scatter', symbolSize: 11, data: ok.map(r => ({ name: r.name, sym: r.symbol, value: [+r.rs_1y.toFixed(1), +r.rs_3m.toFixed(1)], itemStyle: { color: r.emerging ? '#19c37d' : '#4da3ff88' } })), label: { show: true, formatter: p => p.data.sym, position: 'right', fontSize: 9.5, color: '#8796aa' },
      markLine: { silent: true, symbol: 'none', lineStyle: { color: '#3a4656', type: 'dashed' }, data: [{ xAxis: 0 }, { yAxis: 0 }], label: { show: false } } }] });
}
