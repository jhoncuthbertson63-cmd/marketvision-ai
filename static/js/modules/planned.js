import * as U from '../ui.js';
const NEEDS = {
  history: 'Free: FRED + Yahoo/Stooq long-run price history (works today). Optional: Shiller CAPE dataset.',
  discovery: 'Free: SEC "frames" API for cross-sectional screening. Faster with Financial Modeling Prep or Polygon fundamentals.',
  winners: 'Builds on Scanner + Discovery; an LLM key adds filing/transcript reading.',
  institutional: 'Free: SEC 13F & Form 4 (EDGAR). Paid: Finnhub/Quiver/Unusual Whales for congressional trades & options flow.',
  charts: 'Free: Yahoo daily/intraday (delayed). Real-time needs Polygon/Alpaca/IEX Cloud.',
  rotation: 'Free: sector ETF prices (already used on the dashboard).',
  valuation: 'Free: SEC history + prices. Better forward estimates via FMP/Finnhub/Zacks.',
  watchlists: 'Needs user accounts + a database; alert delivery needs an email/SMS/push provider.',
  thesis: 'Needs accounts/database; an LLM key for thesis-evidence matching against new filings & news.',
  simulator: 'No extra keys — per-stock simulator is live on every research page.',
  assistant: 'Requires an LLM API key (xAI / OpenAI / Anthropic) — the adapter is already built.',
  brief: 'LLM key for narrative; news API (NewsAPI, Benzinga, Finnhub) for broader coverage.',
};
export default {
  render(el, m) {
    el.innerHTML = `<div class="planned"><span class="badge Mature">Coming in a later stage · Stage ${m.stage}</span><h1 style="margin-top:10px">${U.esc(m.name)}</h1>
      <div class="panel"><p>${U.esc(m.desc || '')}</p><h3>Data / infrastructure needed</h3><p class="muted">${U.esc(NEEDS[m.id] || '—')}</p>
      <div class="callout">This module slot is registered in the platform's module registry (<span class="mono">app/modules/registry.py</span> + <span class="mono">static/js/modules/</span>) and will plug into the shared data, caching and source-attribution layers. Nothing on this page is simulated.</div>
      <p style="margin-top:14px"><a class="btn" href="#/">← Dashboard</a> <a class="btn" href="#/scanner">Growth Scanner</a> <a class="btn" href="#/research">Stock Research</a></p></div></div>`;
  }
};
