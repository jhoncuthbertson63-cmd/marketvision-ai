import * as U from '../ui.js';
const SEC_TITLES = { business: 'What the company does', fundamentals: 'Financial fundamentals', valuation: 'Valuation', management: 'Management & capital allocation', advantages: 'Competitive advantage indicators', risks: 'Business & investment risks', growth: 'Future growth expectations', conclusion: 'Investment conclusion' };

export default {
  async render(el, [ticker]) {
    if (!ticker) return landing(el);
    document.body.classList.toggle('plain', localStorage.mvMode !== 'pro');
    el.innerHTML = `<div class="loading">Building research report for ${U.esc(ticker)} — pulling SEC filings, prices, analyst consensus and peers…</div>`;
    let r; try { r = await U.api('/api/research/' + encodeURIComponent(ticker)); }
    catch (e) {
      if (e instanceof U.NotGenerated) { return notGenerated(el, ticker); }
      el.innerHTML = U.unavailable(`report for ${ticker}`, e.message + '. Check the ticker (US listings via SEC EDGAR/Yahoo).'); return; }
    render(el, r);
  }
};

async function notGenerated(el, t) {
  const T = await U.staticTickers().catch(() => ({}));
  const meta = await fetch('data/meta.json').then(r => r.json()).catch(() => ({}));
  const sugg = Object.keys(T).filter(s => s.startsWith(t.slice(0, 2))).slice(0, 12);
  const issue = meta.repo ? `https://github.com/${meta.repo}/issues/new?title=${encodeURIComponent('research: ' + t)}&body=${encodeURIComponent('Please add ' + t + ' to the MarketVision snapshot.')}` : null;
  el.innerHTML = `<h1>${U.esc(t)}</h1><div class="unavail"><b>No pre-generated report for ${U.esc(t)} in this snapshot</b>This public version is a static snapshot: reports exist for ${Object.keys(T).length} tickers (S&P 500, Nasdaq-100, growth-scanner companies and popular small caps). Nothing is estimated or filled in for tickers outside that list.</div>
   ${issue ? `<p style="margin-top:12px"><a class="btn pri" href="${issue}" target="_blank" rel="noopener">Request ${U.esc(t)} (opens a GitHub issue — needs a GitHub account)</a> <span class="dim" style="font-size:12px">A workflow adds the ticker on the next build.</span></p>` : ''}
   ${sugg.length ? `<div class="panel" style="padding:14px;margin-top:12px"><h3>Similar tickers available</h3><div class="chips">${sugg.map(s => `<a class="chip" href="#/research/${s}">${s}</a>`).join('')}</div></div>` : ''}`;
}

function landing(el) {
  const ex = ['NVDA', 'AAPL', 'MSFT', 'VRT', 'CRWD', 'UFPT', 'RKLB', 'LLY', 'PLUG', 'JPM'];
  el.innerHTML = `<h1>AI Stock Research Analyst</h1><p class="sub">Enter any US-listed ticker in the search bar (press <span class="mono">/</span>). Each report combines SEC-reported financials, delayed prices, analyst consensus, peers and transparent scenario math.</p>
   <div class="panel" style="padding:16px"><h3>Try</h3><div class="chips">${ex.map(t => `<a class="chip" href="#/research/${t}">${t}</a>`).join('')}</div></div>${U.disclaimer()}`;
}

function render(el, r) {
  const q = r.quote || {}, F = r.fundamentals, A = r.analyst || {}, V = r.valuation || {}, S = r.scenarios || {};
  const chg = q.regularMarketChangePercent;
  el.innerHTML = `
  <div class="rhead">
    <div><h1><span class="tk-big">${U.esc(r.ticker)}</span>${U.esc(r.name)}</h1>
      <div class="muted">${U.esc([r.profile?.sector, r.profile?.industry, q.fullExchangeName].filter(Boolean).join(' · '))}${r.cik ? ` · <a href="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${r.cik}" target="_blank" rel="noopener">SEC CIK ${r.cik}</a>` : ''}</div></div>
    ${q.regularMarketPrice != null ? `<div><div class="px">${U.num(q.regularMarketPrice)} <span class="dim" style="font-size:13px">${U.esc(q.currency || '')}</span></div>
      <div class="chg">${U.cpct(chg)} <span class="dim">(${q.regularMarketChange > 0 ? '+' : ''}${U.num(q.regularMarketChange)})</span> ${U.lbl('delayed', 'Delayed')}</div></div>` : U.unavailable('quote', 'No delayed quote available.')}
    <span style="flex:1"></span>
    <div style="display:flex;flex-direction:column;gap:6px;align-items:flex-end">
      <div class="mode-toggle"><button data-m="plain">Plain English</button><button data-m="pro">Professional analysis</button></div>
      <span class="dim" style="font-size:11px">Report generated ${U.fmtTime(r.generated_at)}</span></div>
  </div>
  ${r.data_gaps?.length ? `<div class="callout warn" style="margin-bottom:12px"><b>Data limitations for this report:</b> ${r.data_gaps.map(U.esc).join(' · ')}</div>` : ''}
  <div class="grid" style="grid-template-columns:minmax(0,1.6fr) minmax(0,1fr)" id="top2">
    <div id="priceP"></div><div id="snapP"></div></div>
  <div class="grid g2" style="margin-top:14px" id="narr1"></div>
  <div style="margin-top:14px" id="finP"></div>
  <div class="grid g2" style="margin-top:14px"><div id="balP"></div><div id="capP"></div></div>
  <div style="margin-top:14px" id="valP"></div>
  <div class="grid g2" style="margin-top:14px"><div id="anP"></div><div id="outP"></div></div>
  <div style="margin-top:14px" id="scP"></div>
  <div class="grid g2" style="margin-top:14px" id="narr2"></div>
  <div class="grid g2" style="margin-top:14px"><div id="catP"></div><div id="newsP"></div></div>
  <div style="margin-top:14px" id="conP"></div>
  ${U.disclaimer()}`;
  if (innerWidth < 980) el.querySelector('#top2').style.gridTemplateColumns = '1fr';
  el.querySelectorAll('.mode-toggle button').forEach(b => { b.classList.toggle('on', (localStorage.mvMode || 'plain') === b.dataset.m); b.onclick = () => { localStorage.mvMode = b.dataset.m; document.body.classList.toggle('plain', b.dataset.m !== 'pro'); el.querySelectorAll('.mode-toggle button').forEach(x => x.classList.toggle('on', x === b)); window.dispatchEvent(new Event('resize')); }; });
  priceChart(el.querySelector('#priceP'), r);
  snapshot(el.querySelector('#snapP'), r);
  narrative(el.querySelector('#narr1'), r, ['business', 'fundamentals']);
  financials(el.querySelector('#finP'), r);
  balance(el.querySelector('#balP'), el.querySelector('#capP'), r);
  valuation(el.querySelector('#valP'), r);
  analyst(el.querySelector('#anP'), el.querySelector('#outP'), r);
  scenarios(el.querySelector('#scP'), r);
  narrative(el.querySelector('#narr2'), r, ['advantages', 'risks', 'management', 'valuation']);
  catalysts(el.querySelector('#catP'), el.querySelector('#newsP'), r);
  narrative(el.querySelector('#conP'), r, ['growth', 'conclusion'], true);
}

function narrBlock(r, key) {
  const N = r.narrative; const items = N?.sections?.[key] || [];
  if (!items.length) return U.unavailable(SEC_TITLES[key], 'Not enough data to generate this section.');
  return `<ul class="narr">${items.map(x => `<li>${U.lbl(x.kind)} ${U.esc(x.text)}</li>`).join('')}</ul>`;
}
function narrative(box, r, keys, wide) {
  const N = r.narrative;
  const foot = `<div class="pf">${N.mode === 'llm' ? U.lbl('ai') : U.lbl('editorial', 'Rule-based')} ${U.esc(N.label)}${N.llm_error ? ` <span class="stale">LLM call failed: ${U.esc(N.llm_error)}</span>` : ''}</div>`;
  box.innerHTML = keys.map(k => U.panel({ title: SEC_TITLES[k], body: narrBlock(r, k), foot, cls: wide ? '' : '' })).join('');
  if (wide) box.className = 'grid g2';
}

function priceChart(box, r) {
  const h = r.price_history || [];
  if (!h.length) { box.innerHTML = U.panel({ title: 'Price history', body: U.unavailable('price history') }); return; }
  const R = [['6m', '6M', 182], ['1y', '1Y', 365], ['3y', '3Y', 1095], ['5y', '5Y', 1826], ['10y', '10Y', 3660]];
  const P = r.price_perf || {};
  box.innerHTML = U.panel({ title: 'Price history', right: U.chips('rng', R.map(x => [x[0], x[1]]), '5y'), body: `<div class="chart lg"></div>
      <div class="stats" style="margin-top:8px">${[['1M', '1m'], ['YTD', 'ytd'], ['1Y', '1y'], ['3Y', '3y'], ['5Y', '5y']].map(([l, k]) => `<div class="stat"><span class="k">${l} return</span><span class="v">${U.cpct(P[k], 1)}</span></div>`).join('')}
      <div class="stat"><span class="k">1Y volatility</span><span class="v">${U.pct(P.vol_1y, 0, false)}</span></div><div class="stat"><span class="k">3Y max drawdown</span><span class="v dn">${U.pct(P.max_dd_3y, 0)}</span></div></div>`, foot: U.src(r.price_meta) });
  const el = box.querySelector('.chart');
  const draw = days => {
    const cut = h[h.length - 1][0] - days * 864e5; const d = h.filter(x => x[0] >= cut);
    const sma = (n) => d.map((x, i) => { const all = h.indexOf(x); if (all < n) return [x[0], null]; let s = 0; for (let j = all - n + 1; j <= all; j++) s += h[j][4]; return [x[0], +(s / n).toFixed(2)]; });
    U.chart(el, {
      grid: [{ left: 50, right: 12, top: 10, height: '68%' }, { left: 50, right: 12, top: '82%', height: '13%' }],
      tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } }, legend: { show: true, top: 0, right: 10, textStyle: { color: '#8796aa', fontSize: 10.5 }, data: ['Close', '50D', '200D'] },
      xAxis: [{ type: 'time', ...U.axisStyle() }, { type: 'time', gridIndex: 1, show: false }],
      yAxis: [{ type: 'value', scale: true, ...U.axisStyle() }, { type: 'value', gridIndex: 1, show: false }],
      dataZoom: [{ type: 'inside', xAxisIndex: [0, 1] }],
      series: [{ name: 'Close', type: 'line', data: d.map(x => [x[0], x[4]]), showSymbol: false, lineStyle: { width: 1.6, color: '#4da3ff' }, itemStyle: { color: '#4da3ff' }, areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: '#4da3ff30' }, { offset: 1, color: 'transparent' }]) } },
        { name: '50D', type: 'line', data: sma(50), showSymbol: false, lineStyle: { width: 1, color: '#f5b84a' }, itemStyle: { color: '#f5b84a' } },
        { name: '200D', type: 'line', data: sma(200), showSymbol: false, lineStyle: { width: 1, color: '#b18cff' }, itemStyle: { color: '#b18cff' } },
        { name: 'Volume', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: d.map(x => [x[0], x[5]]), itemStyle: { color: '#4da3ff55' } }]
    });
  };
  draw(1826);
  U.onChips(box, 'rng', v => draw(R.find(x => x[0] === v)[2]));
}

function snapshot(box, r) {
  const q = r.quote || {}, V = r.valuation?.self || {}, T = r.fundamentals?.ttm || {}, G = r.fundamentals?.growth || {}, B = r.fundamentals?.balance || {};
  const s = (k, v, kind) => `<div class="stat"><span class="k">${k} ${kind ? U.lbl(kind) : ''}</span><span class="v">${v}</span></div>`;
  box.innerHTML = U.panel({ title: 'Snapshot', body: `<div class="stats" style="grid-template-columns:repeat(2,1fr)">
      ${s('Market cap', U.money(q.marketCap), 'fact')}${s('P/E (TTM)', U.mult(q.trailingPE), 'derived')}
      ${s('Forward P/E', U.mult(q.forwardPE), 'estimate')}${s('Price / Sales', U.mult(V.ps), 'derived')}
      ${s('Revenue (TTM)', U.money(T.revenue), 'fact')}${s('Revenue growth (TTM YoY)', U.cpct(G.revenue_ttm_yoy, 1), 'derived')}
      ${s('Net margin (TTM)', U.pct(T.net_margin, 1, false), 'derived')}${s('FCF (TTM)', U.money(T.fcf), 'derived')}
      ${s('Net debt', B.net_debt == null ? '—' : (B.net_debt < 0 ? `<span class="up">${U.money(-B.net_debt)} net cash</span>` : U.money(B.net_debt)), 'derived')}${s('52-week range', `${U.num(q.fiftyTwoWeekLow)}–${U.num(q.fiftyTwoWeekHigh)}`, 'fact')}
      ${s('Employees', r.profile?.employees ? r.profile.employees.toLocaleString() : '—', 'fact')}${s('Next earnings', U.esc(r.analyst?.next_earnings?.date || '—'), 'fact')}
    </div>${r.profile?.website ? `<div style="margin-top:8px;font-size:12px"><a href="${U.esc(r.profile.website)}" target="_blank" rel="noopener">${U.esc(r.profile.website)}</a> · Investor materials: see company website / SEC filings below</div>` : ''}`,
    foot: U.src(q.meta, r.fundamentals ? `<span>Fundamentals: <a href="${U.esc(r.fundamentals.meta.url)}" target="_blank" rel="noopener">SEC XBRL</a> (TTM through ${U.esc(T.end || '—')})</span>` : '') });
}

function financials(box, r) {
  const F = r.fundamentals; const CUR = F?.currency || 'USD'; const M0 = U.money;
  const money = (v, d) => CUR === 'USD' ? M0(v, d) : (v == null ? '—' : M0(v, d).replace('$', CUR + ' '));
  if (!F || !F.rows?.length) { box.innerHTML = U.panel({ title: 'Financial history (SEC filings)', body: U.unavailable('SEC XBRL financials', 'This filer does not report standard US-GAAP revenue tags (ETFs, funds, some foreign filers).') }); return; }
  const rows = F.rows, G = F.growth;
  const line = (k, l, f, kind = 'fact') => `<tr><td>${l} ${U.lbl(kind)}</td>${rows.map(x => `<td>${f(x[k])}</td>`).join('')}<td>${F.ttm[k] !== undefined ? f(F.ttm[k]) : ''}</td></tr>`;
  const ttmM = { gross_margin: F.ttm.gross_margin, operating_margin: F.ttm.operating_margin, net_margin: F.ttm.net_margin, fcf_margin: F.ttm.fcf_margin };
  const mline = (k, l) => `<tr><td>${l} ${U.lbl('derived')}</td>${rows.map(x => `<td>${U.pct(x[k], 1, false)}</td>`).join('')}<td>${U.pct(ttmM[k], 1, false)}</td></tr>`;
  box.innerHTML = U.panel({ title: 'Financial history — 10 fiscal years (SEC filings)' + (CUR !== 'USD' ? ` · reported in ${CUR}` : ''), right: `<div class="stats" style="grid-template-columns:repeat(4,auto);gap:6px">${[['Rev CAGR 3Y', G.revenue_cagr_3y], ['5Y', G.revenue_cagr_5y], ['10Y', G.revenue_cagr_10y], ['EPS CAGR 5Y', G.eps_cagr_5y]].map(([k, v]) => `<div class="stat" style="padding:5px 9px"><span class="k">${k}</span><span class="v" style="font-size:13px">${U.cpct(v, 1)}</span></div>`).join('')}</div>`,
    body: `<div class="grid g2"><div class="chart"></div><div class="chart"></div></div>
     <div class="pro" style="margin-top:10px"><div class="tw"><table class="t"><thead><tr><th>Fiscal year</th>${rows.map(x => `<th title="FY end ${x.fy_end}">FY${x.fy}</th>`).join('')}<th>TTM</th></tr></thead><tbody>
      ${line('revenue', 'Revenue', money)}<tr><td>Revenue growth ${U.lbl('derived')}</td>${rows.map(x => `<td>${U.cpct(x.revenue_yoy, 1)}</td>`).join('')}<td>${U.cpct(G.revenue_ttm_yoy, 1)}</td></tr>
      ${line('gross_profit', 'Gross profit', money)}${mline('gross_margin', 'Gross margin')}${line('operating_income', 'Operating income', money)}${mline('operating_margin', 'Operating margin')}
      ${line('net_income', 'Net income', money)}${mline('net_margin', 'Net margin')}<tr><td>Diluted EPS ${U.lbl('fact')}</td>${rows.map(x => `<td>${x.eps_diluted == null ? '—' : '$' + x.eps_diluted.toFixed(2)}</td>`).join('')}<td></td></tr>
      ${line('ocf', 'Operating cash flow', money)}${line('capex', 'Capital expenditures', money)}${line('fcf', 'Free cash flow (OCF − capex)', money, 'derived')}${mline('fcf_margin', 'FCF margin')}
      ${line('rnd', 'R&D expense', money)}${line('sbc', 'Stock-based comp', money)}${line('buybacks', 'Share repurchases', money)}${line('dividends', 'Dividends paid', money)}
      <tr><td>Diluted shares ${U.lbl('fact')}</td>${rows.map(x => `<td>${U.big(x.diluted_shares)}</td>`).join('')}<td></td></tr></tbody></table></div>
      ${F.split_notes?.length ? `<p class="dim" style="font-size:11px">${F.split_notes.map(U.esc).join(' ')}</p>` : ''}
      <details style="margin-top:6px"><summary>XBRL tags used (audit trail)</summary><div class="math">${Object.entries(F.tags).map(([k, v]) => `${k}: ${(v || []).join(', ') || 'not reported'}`).join('\n')}</div></details></div>
     <p class="dim plain-only" style="font-size:11.5px;margin:8px 0 0">Switch to <b>Professional analysis</b> for the full 10-year table and XBRL audit trail.</p>`,
    foot: U.src(F.meta) });
  const [c1, c2] = box.querySelectorAll('.chart'); const yrs = rows.map(x => 'FY' + x.fy);
  U.chart(c1, { title: { text: 'Revenue, net income & free cash flow', textStyle: { fontSize: 12, color: '#9aa8ba', fontWeight: 500 } }, grid: { left: 56, right: 10, top: 40, bottom: 24 }, legend: { top: 18, textStyle: { color: '#8796aa', fontSize: 10.5 } }, tooltip: { trigger: 'axis', valueFormatter: v => money(v) },
    xAxis: { type: 'category', data: yrs, ...U.axisStyle() }, yAxis: { type: 'value', ...U.axisStyle(), axisLabel: { ...U.axisStyle().axisLabel, formatter: v => money(v, Math.abs(v) >= 1e12 ? 1 : 0) } },
    series: [['Revenue', 'revenue', '#4da3ff'], ['Net income', 'net_income', '#19c37d'], ['Free cash flow', 'fcf', '#b18cff']].map(([n, k, c]) => ({ name: n, type: 'bar', data: rows.map(x => x[k]), itemStyle: { color: c, borderRadius: [3, 3, 0, 0] } })) });
  U.chart(c2, { title: { text: 'Margins', textStyle: { fontSize: 12, color: '#9aa8ba', fontWeight: 500 } }, grid: { left: 44, right: 10, top: 40, bottom: 24 }, legend: { top: 18, textStyle: { color: '#8796aa', fontSize: 10.5 } }, tooltip: { trigger: 'axis', valueFormatter: v => U.pct(v, 1, false) },
    xAxis: { type: 'category', data: yrs, ...U.axisStyle() }, yAxis: { type: 'value', ...U.axisStyle(), axisLabel: { ...U.axisStyle().axisLabel, formatter: v => v + '%' } },
    series: [['Gross', 'gross_margin', '#4da3ff'], ['Operating', 'operating_margin', '#f5b84a'], ['Net', 'net_margin', '#19c37d'], ['FCF', 'fcf_margin', '#b18cff']].map(([n, k, c]) => ({ name: n, type: 'line', data: rows.map(x => x[k] == null ? null : +x[k].toFixed(2)), symbolSize: 5, lineStyle: { color: c, width: 2 }, itemStyle: { color: c } })) });
}

function balance(b1, b2, r) {
  const F = r.fundamentals; const CUR = F?.currency || 'USD';
  const UM = U.money; const U2 = { ...U, money: (v, d) => CUR === 'USD' ? UM(v, d) : (v == null ? '—' : UM(v, d).replace('$', CUR + ' ')) }; if (!F) { b1.innerHTML = U.panel({ title: 'Balance sheet', body: U.unavailable('balance sheet') }); b2.innerHTML = ''; return; }
  const B = F.balance, C = F.capital, s = (k, v, kind = 'fact') => `<div class="stat"><span class="k">${k} ${U.lbl(kind)}</span><span class="v">${v}</span></div>`;
  b1.innerHTML = U.panel({ title: 'Balance sheet & debt', body: `<div class="stats">${s('Cash + ST investments', U2.money(B.cash_and_st_investments))}${s('Total debt', U2.money(B.total_debt))}${s('Net debt', U2.money(B.net_debt), 'derived')}${s('Shareholders’ equity', U2.money(B.equity))}${s('Debt / equity', U.mult(B.debt_to_equity, 2), 'derived')}${s('Return on equity', U.pct(B.roe_ttm, 1, false), 'derived')}${s('Interest coverage', U.mult(B.interest_coverage), 'derived')}${s('Total assets', U2.money(B.assets))}</div>
     <p class="dim" style="font-size:11px;margin:8px 0 0">As of ${U.esc(B.as_of || '—')}. Debt method: ${U.esc(B.debt_method || '—')}. ROE = TTM net income ÷ average of last 5 reported equity balances. Interest coverage = TTM operating income ÷ TTM interest expense.</p>`, foot: U.src(F.meta) });
  b2.innerHTML = U.panel({ title: 'Capital allocation (last 5 fiscal years)', body: `<div class="stats">${s('Free cash flow (5Y)', U2.money(C.fcf_5y), 'derived')}${s('Buybacks (5Y)', U2.money(C.buybacks_5y))}${s('Dividends (5Y)', U2.money(C.dividends_5y))}${s('Capex (5Y)', U2.money(C.capex_5y))}${s('Stock comp (5Y)', U2.money(C.sbc_5y))}${s('Returned / FCF', U.pct(C.shareholder_return_pct_of_fcf, 0, false), 'derived')}${s('Share count CAGR', U.cpct(C.share_count_cagr_5y), 'derived')}</div>
     <p class="dim" style="font-size:11px;margin:8px 0 0">Share count CAGR uses diluted weighted-average shares (split-adjusted). Negative = buybacks shrinking the share base.</p>`, foot: U.src(F.meta) });
}

function valuation(box, r) {
  const V = r.valuation; if (!V || !V.self) { box.innerHTML = U.panel({ title: 'Valuation vs competitors', body: U.unavailable('valuation', 'Needs both a quote and SEC fundamentals.') }); return; }
  const S = V.self, M = V.peer_median || {}, peers = V.peers || [];
  const cell = (v, m) => { if (v == null) return '—'; const t = U.mult(v); if (!m) return t; const d = (v / m - 1) * 100; return `${t} <span class="dim" style="font-size:10.5px">${d > 0 ? '+' : ''}${d.toFixed(0)}%</span>`; };
  box.innerHTML = U.panel({ title: 'Valuation vs competitors', right: `<span class="dim" style="font-size:11px">Peers: ${U.esc(V.peer_source || '')}</span>`, body: `
    <div class="tw"><table class="t"><thead><tr><th>Company</th><th>Mkt cap</th><th>P/E ${U.lbl('derived')}</th><th>Fwd P/E ${U.lbl('estimate')}</th><th>P/S ${U.lbl('derived')}</th><th>P/B</th><th>Rev growth TTM</th><th>52W</th></tr></thead><tbody>
      <tr style="background:#4da3ff12"><td><b>${U.esc(r.ticker)}</b> <span class="dim">(vs peer median)</span></td><td>${U.money(r.quote.marketCap)}</td><td>${cell(S.pe, M.pe)}</td><td>${cell(S.fwd_pe > 0 ? S.fwd_pe : null, M.fwd_pe)}</td><td>${cell(S.ps, M.ps)}</td><td>${cell(S.pb, M.pb)}</td><td>${U.cpct(r.fundamentals?.growth?.revenue_ttm_yoy, 1)}</td><td>${U.cpct(r.price_perf?.['1y'], 1)}</td></tr>
      ${peers.map(p => `<tr class="click" data-s="${p.symbol}"><td><span class="tk mono" style="color:var(--acc)">${p.symbol}</span> <span class="dim">${U.esc(p.name || '')}</span></td><td>${U.money(p.market_cap)}</td><td>${U.mult(p.pe)}</td><td>${p.fwd_pe > 0 ? U.mult(p.fwd_pe) : '—'}</td><td>${U.mult(p.ps)}</td><td>${U.mult(p.pb)}</td><td>${U.cpct(p.revenue_ttm_yoy, 1)}</td><td>${U.cpct(p.chg_52w, 1)}</td></tr>`).join('')}
      <tr><td class="dim">Peer median</td><td></td><td>${U.mult(M.pe)}</td><td>${U.mult(M.fwd_pe)}</td><td>${U.mult(M.ps)}</td><td>${U.mult(M.pb)}</td><td>${U.cpct(M.revenue_ttm_yoy, 1)}</td><td></td></tr></tbody></table></div>
    <div class="stats" style="margin-top:10px">${[['Enterprise value', U.money(S.ev)], ['EV / Sales', U.mult(S.ev_sales)], ['Price / FCF', U.mult(S.p_fcf)], ['FCF yield', U.pct(S.fcf_yield, 2, false)]].map(([k, v]) => `<div class="stat"><span class="k">${k} ${U.lbl('derived')}</span><span class="v">${v}</span></div>`).join('')}</div>`, foot: U.src(V.meta) });
  box.querySelectorAll('tr[data-s]').forEach(tr => tr.onclick = () => location.hash = '#/research/' + tr.dataset.s);
}

function analyst(b1, b2, r) {
  const A = r.analyst || {};
  if (!A.meta) { b1.innerHTML = U.panel({ title: 'Analyst consensus', body: U.unavailable('analyst estimates', 'Yahoo Finance consensus data not available for this ticker.') }); }
  else {
    const T = A.targets || {}, px = r.quote.regularMarketPrice;
    const rt = A.rec_trend?.[0];
    const est = [['Current quarter', 'current_q'], ['Next quarter', 'next_q'], ['Current fiscal year', 'current_fy'], ['Next fiscal year', 'next_fy']];
    b1.innerHTML = U.panel({ title: 'Analyst consensus', right: U.lbl('estimate', 'Third-party estimates'), body: `
      <div class="tw"><table class="t"><thead><tr><th>Period</th><th>Revenue est.</th><th>Rev growth</th><th>EPS est.</th><th>EPS growth</th></tr></thead><tbody>
       ${est.map(([l, k]) => `<tr><td>${l} <span class="dim">${U.esc(A['period_end_' + k] || '')}</span></td><td>${U.money(A['revenue_est_' + k])}</td><td>${U.cpct(A['revenue_growth_' + k], 1)}</td><td>${A['eps_est_' + k] == null ? '—' : '$' + A['eps_est_' + k].toFixed(2)}</td><td>${U.cpct(A['eps_growth_' + k], 1)}</td></tr>`).join('')}</tbody></table></div>
      ${T.targetMeanPrice ? `<h3 style="margin-top:12px">12-month price targets (${T.numberOfAnalystOpinions || '?'} analysts)</h3>
       <div class="stats">${[['Low', T.targetLowPrice], ['Mean', T.targetMeanPrice], ['Median', T.targetMedianPrice], ['High', T.targetHighPrice]].map(([k, v]) => `<div class="stat"><span class="k">${k}</span><span class="v">${U.num(v)} <span style="font-size:11px">${px && v ? U.cpct((v / px - 1) * 100, 0) : ''}</span></span></div>`).join('')}</div>
       <p class="dim" style="font-size:11px;margin:6px 0 0">Consensus rating: <b>${U.esc((A.recommendation || '—').replace('_', ' '))}</b>${rt ? ` · Strong buy ${rt.strongBuy} · Buy ${rt.buy} · Hold ${rt.hold} · Sell ${rt.sell} · Strong sell ${rt.strongSell}` : ''}. Targets are opinions, not facts or MarketVision forecasts.</p>` : ''}
      ${A.surprises?.length ? `<h3 style="margin-top:12px">Recent earnings surprises</h3><div class="tw"><table class="t"><thead><tr><th>Quarter</th><th>EPS actual ${U.lbl('fact')}</th><th>Estimate</th><th>Surprise</th></tr></thead><tbody>${A.surprises.map(s => `<tr><td>${U.esc(s.quarter)}</td><td>${s.actual == null ? '—' : '$' + s.actual.toFixed(2)}</td><td>${s.estimate == null ? '—' : '$' + s.estimate.toFixed(2)}</td><td>${U.cpct(s.surprise_pct, 1)}</td></tr>`).join('')}</tbody></table></div>` : ''}`, foot: U.src(A.meta) });
  }
  const O = r.outlook || {};
  const row = (l, o, k) => o ? `<tr><td>${l}</td><td>${U.cpct(o[k], 1)}</td><td>${U.lbl(o.kind)}</td><td class="l dim">${U.esc(o.source)}</td></tr>` : `<tr><td>${l}</td><td colspan="3" class="l" style="color:var(--warn)">unavailable</td></tr>`;
  b2.innerHTML = U.panel({ title: 'Growth expectations — 1, 3 & 5 years', body: `<div class="tw"><table class="t"><thead><tr><th>Horizon</th><th>Revenue growth /yr</th><th>Type</th><th class="l">Basis</th></tr></thead><tbody>
      ${row('Next fiscal year', O.y1, 'revenue_growth')}${O.y1 && O.y1.eps_growth != null ? `<tr><td>Next FY — EPS</td><td>${U.cpct(O.y1.eps_growth, 1)}</td><td>${U.lbl('estimate')}</td><td class="l dim">Analyst consensus</td></tr>` : ''}
      ${row('3-year CAGR', O.y3, 'revenue_cagr')}${row('5-year CAGR', O.y5, 'revenue_cagr')}${O.y5_analyst_eps ? row('5-yr EPS growth (analyst LT)', O.y5_analyst_eps, 'eps_growth') : ''}
      <tr><td class="dim">Historical 3Y / 5Y CAGR</td><td>${U.cpct(r.fundamentals?.growth?.revenue_cagr_3y, 1)} / ${U.cpct(r.fundamentals?.growth?.revenue_cagr_5y, 1)}</td><td>${U.lbl('derived')}</td><td class="l dim">SEC filings</td></tr></tbody></table></div>
      <div class="callout" style="margin-top:10px">Analyst consensus rarely extends beyond 2 fiscal years, so 3- and 5-year figures are MarketVision <b>model</b> outputs: growth fades linearly from the next-year estimate to a 5% terminal rate (see scenario math below). They are assumptions made visible, not predictions.</div>
      <h3 style="margin-top:12px">Market opportunity</h3><div class="unavail" style="padding:10px"><b>Needs licensed research data</b>Total addressable market and industry growth projections require cited third-party research. See the Growth Opportunity Scanner for measured industry evidence.</div>`,
    foot: `<div class="pf">Analyst data: Yahoo Finance consensus · Model: MarketVision base case</div>` });
}

function scenarios(box, r) {
  const S = r.scenarios;
  if (!S?.available) { box.innerHTML = U.panel({ title: 'Bull / base / bear scenarios', body: S?.pre_revenue ? `<div class="unavail" style="border-color:var(--bd);color:var(--tx2)"><b>Scenario model not applicable — pre-revenue company</b>${U.esc(S.reason)}</div>` : U.unavailable('scenarios', S?.reason) }); return; }
  const base = S.scenarios.base.assumptions, isPE = S.method === 'pe';
  box.innerHTML = U.panel({ title: 'Bull / base / bear scenarios & simulator — 5-year model', right: U.lbl('model', 'Model forecast · not a prediction'), body: `
    <div class="sc-cards" id="cards"></div>
    <h3 style="margin-top:14px">Scenario simulator — adjust assumptions (applies to the custom scenario)</h3>
    <div class="sim">
      <label>Revenue growth, year 1 (%)<input id="s_g" type="number" step="0.5" value="${(base.g_start * 100).toFixed(1)}"></label>
      <label>Terminal growth, year N (%)<input id="s_gt" type="number" step="0.5" value="${(base.g_terminal * 100).toFixed(1)}"></label>
      <label>Net margin in year N (%)<input id="s_m" type="number" step="0.5" value="${(base.margin * 100).toFixed(1)}" ${isPE ? '' : 'title="Used only for the P/E method"'}></label>
      <label>Valuation method<select id="s_meth"><option value="pe" ${isPE ? 'selected' : ''}>Exit P/E</option><option value="ps" ${!isPE ? 'selected' : ''}>Exit Price/Sales</option></select></label>
      <label>Exit multiple (×)<input id="s_x" type="number" step="0.5" value="${base.exit_multiple.toFixed(1)}"></label>
      <label>Share count change / yr (%)<input id="s_sc" type="number" step="0.25" value="${(base.share_change * 100).toFixed(2)}"></label>
      <label>Horizon (years)<input id="s_n" type="number" min="1" max="10" step="1" value="${base.years}"></label>
      <label>&nbsp;<button class="btn" id="s_reset">Reset to base</button></label>
    </div>
    <div class="grid g2"><div class="chart sm" id="s_chart"></div><div class="math" id="s_math"></div></div>
    <h3 style="margin-top:12px">How the defaults were set</h3><ul class="narr">${S.notes.map(n => `<li>${U.lbl('model')} ${U.esc(n)}</li>`).join('')}<li>${U.lbl('model')} ${U.esc(S.spread_rule)}</li><li>${U.lbl('model')} ${U.esc(S.required.explain)}</li></ul>
    <details class="pro" style="margin-top:8px" open><summary>Formulas</summary><div class="formula">${Object.values(S.formula).map(f => `<div>${U.esc(f)}</div>`).join('')}</div></details>`,
    foot: `<div class="pf">Inputs: TTM revenue (SEC), price & market cap (Yahoo, delayed), analyst growth (Yahoo consensus). Shares = market cap ÷ price. Dividends excluded. Same formula runs in your browser for the simulator.</div>` });
  const C = box.querySelector('#cards');
  const proj = a => { const N = +a.years; let rev = a.revenue0; const path = []; for (let t = 1; t <= N; t++) { const g = a.g_start + (a.g_terminal - a.g_start) * (N > 1 ? (t - 1) / (N - 1) : 1); rev *= 1 + g; path.push({ t, g, rev }); }
    const sh = a.shares0 * Math.pow(1 + a.share_change, N); const ni = rev * a.margin; const price = a.method === 'pe' ? ni * a.exit_multiple / sh : rev * a.exit_multiple / sh;
    return { path, rev, sh, ni, price, ann: price > 0 ? Math.pow(price / a.price0, 1 / N) - 1 : null }; };
  const card = (k, a, res) => `<div class="sc ${k}"><div style="display:flex;justify-content:space-between"><b style="text-transform:capitalize">${k}${k === 'custom' ? ' (your inputs)' : ''}</b>${U.lbl('model')}</div>
     <div class="p">$${U.num(res.price)}</div><div class="mono" style="font-size:12px">${res.ann == null ? '—' : U.cpct(res.ann * 100, 1)} /yr · ${U.cpct((res.price / a.price0 - 1) * 100, 0)} total</div>
     <table style="margin-top:6px"><tr><td>Growth path</td><td>${(a.g_start * 100).toFixed(1)}% → ${(a.g_terminal * 100).toFixed(1)}%</td></tr><tr><td>Revenue yr ${a.years}</td><td>${U.money(res.rev)}</td></tr>
     ${a.method === 'pe' ? `<tr><td>Net margin</td><td>${(a.margin * 100).toFixed(1)}%</td></tr><tr><td>Exit P/E</td><td>${a.exit_multiple.toFixed(1)}×</td></tr>` : `<tr><td>Exit P/S</td><td>${a.exit_multiple.toFixed(2)}×</td></tr>`}<tr><td>Shares yr ${a.years}</td><td>${U.big(res.sh)}</td></tr></table></div>`;
  const drawCards = custom => {
    C.innerHTML = ['bear', 'base', 'bull'].map(k => card(k, S.scenarios[k].assumptions, proj(S.scenarios[k].assumptions))).join('');
    if (custom) C.insertAdjacentHTML('beforeend', card('custom', custom, proj(custom)));
    C.style.gridTemplateColumns = custom ? 'repeat(auto-fit,minmax(200px,1fr))' : '';
  };
  const read = () => ({ ...base, g_start: +box.querySelector('#s_g').value / 100, g_terminal: +box.querySelector('#s_gt').value / 100, margin: +box.querySelector('#s_m').value / 100, method: box.querySelector('#s_meth').value, exit_multiple: +box.querySelector('#s_x').value, share_change: +box.querySelector('#s_sc').value / 100, years: Math.max(1, Math.min(10, +box.querySelector('#s_n').value || 5)) });
  const update = (custom) => {
    const a = custom || base, res = proj(a);
    drawCards(custom);
    const m = box.querySelector('#s_math');
    m.textContent = [`Step-by-step (${custom ? 'custom' : 'base'} case):`,
      `Revenue_0 (TTM, SEC)   = ${U.money(a.revenue0)}`, ...res.path.map(p => `Year ${p.t}: growth ${(p.g * 100).toFixed(2)}% → revenue ${U.money(p.rev)}`),
      a.method === 'pe' ? `NetIncome_${a.years} = ${U.money(res.rev)} × ${(a.margin * 100).toFixed(1)}% = ${U.money(res.ni)}` : `(P/S method: margin not used)`,
      `Shares_${a.years} = ${U.big(a.shares0)} × (1 ${a.share_change >= 0 ? '+' : '−'} ${Math.abs(a.share_change * 100).toFixed(2)}%)^${a.years} = ${U.big(res.sh)}`,
      a.method === 'pe' ? `Price_${a.years} = ${U.money(res.ni)} × ${a.exit_multiple.toFixed(1)} ÷ ${U.big(res.sh)} = $${U.num(res.price)}` : `Price_${a.years} = ${U.money(res.rev)} × ${a.exit_multiple.toFixed(2)} ÷ ${U.big(res.sh)} = $${U.num(res.price)}`,
      `Implied return = ($${U.num(res.price)} ÷ $${U.num(a.price0)})^(1/${a.years}) − 1 = ${res.ann == null ? 'n/a' : (res.ann * 100).toFixed(2) + '%/yr'}`].join('\n');
    const yrs = Array.from({ length: Math.max(...['bear', 'base', 'bull'].map(k => S.scenarios[k].assumptions.years), a.years) + 1 }, (_, i) => 'Y' + i);
    const ser = (k, a2, c) => ({ name: k, type: 'line', data: [a2.revenue0, ...proj(a2).path.map(p => p.rev)], lineStyle: { color: c, width: 2 }, itemStyle: { color: c }, symbolSize: 4 });
    U.chart(box.querySelector('#s_chart'), { title: { text: 'Projected revenue paths', textStyle: { fontSize: 12, color: '#9aa8ba', fontWeight: 500 } }, legend: { top: 18, textStyle: { color: '#8796aa', fontSize: 10.5 } }, grid: { left: 56, right: 10, top: 44, bottom: 22 }, tooltip: { trigger: 'axis', valueFormatter: v => U.money(v) },
      xAxis: { type: 'category', data: yrs, ...U.axisStyle() }, yAxis: { type: 'value', ...U.axisStyle(), axisLabel: { ...U.axisStyle().axisLabel, formatter: v => U.money(v, Math.abs(v) >= 1e12 ? 1 : 0) } },
      series: [ser('bear', S.scenarios.bear.assumptions, '#ff5466'), ser('base', S.scenarios.base.assumptions, '#4da3ff'), ser('bull', S.scenarios.bull.assumptions, '#19c37d'), ...(custom ? [ser('custom', custom, '#f5b84a')] : [])] });
  };
  update(null);
  box.querySelectorAll('.sim input,.sim select').forEach(i => i.oninput = () => update(read()));
  box.querySelector('#s_reset').onclick = () => { box.querySelector('#s_g').value = (base.g_start * 100).toFixed(1); box.querySelector('#s_gt').value = (base.g_terminal * 100).toFixed(1); box.querySelector('#s_m').value = (base.margin * 100).toFixed(1); box.querySelector('#s_meth').value = base.method; box.querySelector('#s_x').value = base.exit_multiple.toFixed(1); box.querySelector('#s_sc').value = (base.share_change * 100).toFixed(2); box.querySelector('#s_n').value = base.years; update(null); };
}

function catalysts(b1, b2, r) {
  const C = r.catalysts || {}, ne = C.next_earnings || {};
  b1.innerHTML = U.panel({ title: 'Catalysts & business developments', body: `
    <div class="callout">${U.lbl('fact')} Next earnings: <b>${U.esc(ne.date || 'not announced')}</b>${ne.is_estimate ? ' (date estimated)' : ''}${ne.eps_avg != null ? ` · consensus EPS $${ne.eps_avg.toFixed(2)} ${U.lbl('estimate')}` : ''}${ne.revenue_avg ? ` · revenue ${U.money(ne.revenue_avg)}` : ''}</div>
    <h3 style="margin-top:12px">Recent material events (8-K filings)</h3>
    ${C.filings_8k?.length ? `<div class="tw"><table class="t"><thead><tr><th>Filed</th><th class="l">Reported items</th><th></th></tr></thead><tbody>${C.filings_8k.map(f => `<tr><td class="l">${U.esc(f.date)}</td><td class="l" style="white-space:normal">${U.esc(f.item_labels.join(', ') || f.form)}</td><td><a href="${U.esc(f.url)}" target="_blank" rel="noopener">filing ↗</a></td></tr>`).join('')}</tbody></table></div>` : U.unavailable('8-K filings', 'No recent 8-K filings found.')}
    <h3 style="margin-top:12px">Periodic reports (products, customers, contracts, risk factors are disclosed here)</h3>
    <div style="display:flex;flex-wrap:wrap;gap:6px">${(C.periodic || []).map(f => `<a class="chip" href="${U.esc(f.url)}" target="_blank" rel="noopener">${U.esc(f.form)} · ${U.esc(f.report_date || f.date)}</a>`).join('')}${C.proxy ? `<a class="chip" href="${U.esc(C.proxy.url)}" target="_blank" rel="noopener">Proxy (DEF 14A) · ${U.esc(C.proxy.date)}</a>` : ''}</div>
    <p class="dim" style="font-size:11px;margin:8px 0 0">Product, contract and customer-level catalysts need document parsing of these filings or an LLM key — planned for a later stage.</p>`, foot: U.src(C.meta_filings) });
  b2.innerHTML = U.panel({ title: 'Latest news', right: U.lbl('news', 'Third-party reporting'), body: C.news?.length ? `<div class="news"><ul>${C.news.map(n => `<li><a href="${U.esc(n.link)}" target="_blank" rel="noopener">${U.esc(n.title)}</a><div class="dim" style="font-size:11px">${U.esc(n.publisher || '')} · ${n.time ? new Date(n.time * 1000).toLocaleString('en-US', { timeZone: 'America/Chicago', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) + ' CT' : ''}</div></li>`).join('')}</ul></div>` : U.unavailable('news', 'No headlines returned by the source.'), foot: U.src(C.meta_news) });
}
