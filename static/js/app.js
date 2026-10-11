import * as U from './ui.js';
import dashboard from './modules/dashboard.js';
import research from './modules/research.js';
import scanner from './modules/scanner.js';
import planned from './modules/planned.js';

const LIVE = { dashboard, research, scanner };
const ICON = { grid: '▦', search: '⌕', radar: '◎', clock: '⏳', spark: '✦', trophy: '★', bank: '⌂', chart: '📈', rotate: '⟳', scale: '⚖', bell: '🔔', check: '✓', sliders: '☰', chat: '💬', news: '☰' };
let MODULES = [];

async function boot() {
  const m = await U.api('/api/modules').catch(() => ({ modules: [] }));
  MODULES = m.modules || [];
  const pill = document.getElementById('llmPill');
  if (U.STATIC) {
    try {
      const meta = await (await fetch('data/meta.json', { cache: 'no-cache' })).json();
      const t = U.fmtTime(meta.snapshot_finished);
      const ageMin = (Date.now() - new Date(meta.snapshot_finished)) / 60000;
      const bar = document.createElement('div');
      bar.className = 'snapbar' + (ageMin > 26 * 60 ? ' old' : '');
      bar.innerHTML = `<b>Static snapshot</b> taken ${t} (${ageMin < 90 ? Math.round(ageMin) + ' min' : Math.round(ageMin / 60) + ' h'} ago) · ${U.esc(meta.schedule)} · prices delayed · ${meta.research_count} pre-generated research reports${Object.keys(meta.errors || {}).length ? ` · <span class="dn">some sources failed at snapshot time</span>` : ''}`;
      document.querySelector('.main').insertBefore(bar, document.querySelector('.content'));
    } catch { }
  }
  if (U.STATIC) pill.innerHTML = `<span class="dot"></span>Static snapshot · rule-based narratives`;
  else if (m.llm && m.llm.configured) pill.innerHTML = `<span class="dot ok"></span>AI: ${m.llm.provider}`;
  else pill.innerHTML = `<span class="dot"></span>AI narrative: rule-based (no LLM key)`;
  pill.title = 'Set XAI_API_KEY, OPENAI_API_KEY or ANTHROPIC_API_KEY on the server to enable LLM narratives.';
  renderNav();
  window.addEventListener('hashchange', route);
  route();
  setInterval(clock, 1000); clock();
  U.initSearch();
  document.getElementById('burger').onclick = () => document.body.classList.toggle('navopen');
  document.getElementById('theme').onclick = () => {
    const h = document.documentElement; h.dataset.theme = h.dataset.theme === 'dark' ? 'light' : 'dark';
    localStorage.mvTheme = h.dataset.theme; route();
  };
  if (localStorage.mvTheme) document.documentElement.dataset.theme = localStorage.mvTheme;
}
function clock() {
  const d = new Date();
  const et = d.toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit' });
  const ct = d.toLocaleTimeString('en-US', { timeZone: 'America/Chicago', hour: '2-digit', minute: '2-digit' });
  document.getElementById('clock').textContent = `${et} ET · ${ct} CT`;
}
function renderNav() {
  const live = MODULES.filter(m => m.status === 'live'), plan = MODULES.filter(m => m.status !== 'live');
  const a = m => `<a href="${m.route}" data-id="${m.id}"><span class="ic">${ICON[m.icon] || '•'}</span>${m.name}${m.status !== 'live' ? `<span class="soon" title="Coming in a later stage">Stage ${m.stage}</span>` : ''}</a>`;
  document.getElementById('nav').innerHTML = `<h6>Stage 1 · Live</h6>${live.map(a).join('')}<h6>Coming in a later stage</h6>${plan.map(a).join('')}`;
}
function route() {
  const h = location.hash || '#/';
  const [, seg, ...rest] = h.split('/');
  const id = seg === '' || seg === undefined ? 'dashboard' : seg;
  document.querySelectorAll('#nav a').forEach(a => a.classList.toggle('on', a.dataset.id === id));
  document.body.classList.remove('navopen');
  U.disposeCharts();
  const view = document.getElementById('view');
  window.scrollTo(0, 0);
  const mod = LIVE[id];
  if (mod) return mod.render(view, rest.map(decodeURIComponent));
  const pm = MODULES.find(m => m.id === id);
  if (pm) return planned.render(view, pm);
  view.innerHTML = `<div class="unavail"><b>Page not found</b><a href="#/">Back to dashboard</a></div>`;
}
boot();
