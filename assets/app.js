'use strict';

const DATA_URL  = './data/articles.json';
const REFRESH_MS = 5 * 60 * 1000;

let allArticles  = [];
let currentCat   = 'all';
let refreshTimer = null;

// ─── HELPERS ────────────────────────────────────────────────────────────────

function slugify(str) {
  return str
    .toLowerCase()
    .replace(/ą/g,'a').replace(/ć/g,'c').replace(/ę/g,'e')
    .replace(/ł/g,'l').replace(/ń/g,'n').replace(/ó/g,'o')
    .replace(/ś/g,'s').replace(/ź/g,'z').replace(/ż/g,'z')
    .replace(/[^a-z0-9]/g,'');
}

function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('pl-PL', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
}

function trustInfo(score, fake) {
  if (fake) return { cls: 'trust-fake', icon: 'X', color: 'var(--red)', label: 'FAKE NEWS' };
  if (score >= 75) return { cls: 'trust-high', icon: 'V', color: 'var(--green)', label: score + '%' };
  if (score >= 50) return { cls: 'trust-mid',  icon: '!', color: 'var(--yellow)', label: score + '%' };
  return { cls: 'trust-low', icon: 'X', color: 'var(--red)', label: score + '%' };
}

function catTag(category) {
  const slug = slugify(category);
  return `<span class="cat-tag cat-${slug}">${category}</span>`;
}

function trustBadge(score, fake) {
  const t = trustInfo(score, fake);
  return `<span class="trust-badge ${t.cls}">${t.icon} ${t.label}</span>`;
}

function imgWrap(url, alt, wrapClass, imgClass) {
  const fallback = `<div class="img-fallback">${alt}</div>`;
  if (!url) {
    return `<div class="${wrapClass}">${fallback}</div>`;
  }
  return `<div class="${wrapClass}">
    <img src="${url}" alt="${alt}" class="${imgClass}"
      onerror="this.style.display='none';this.nextElementSibling.style.display='flex';">
    <div class="img-fallback" style="display:none;">${alt}</div>
  </div>`;
}

// ─── LOAD & REFRESH ─────────────────────────────────────────────────────────

async function loadArticles(showIndicator) {
  if (showIndicator) {
    document.getElementById('article-count').textContent = 'Ładowanie...';
  }
  try {
    const res = await fetch(DATA_URL + '?t=' + Date.now());
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    allArticles = data.articles || [];
    updateTopBar(data);
    updateTicker(allArticles);
    renderAll(filterArticles(allArticles, currentCat));
  } catch (e) {
    console.error('Błąd ładowania danych:', e);
    document.getElementById('article-count').textContent = 'Błąd ładowania';
  }
}

function filterArticles(list, cat) {
  if (cat === 'all') return list;
  return list.filter(a => slugify(a.category) === cat);
}

// ─── UPDATE TOP BAR ──────────────────────────────────────────────────────────

function updateTopBar(data) {
  const countEl = document.getElementById('article-count');
  const updateEl = document.getElementById('last-update');
  countEl.textContent = allArticles.length + ' artykułów';
  if (data.generated_at) {
    const d = new Date(data.generated_at);
    const hh = String(d.getHours()).padStart(2,'0');
    const mm = String(d.getMinutes()).padStart(2,'0');
    updateEl.textContent = 'Ost. aktualizacja: ' + hh + ':' + mm;
  }
}

// ─── TICKER ──────────────────────────────────────────────────────────────────

function updateTicker(articles) {
  const inner = document.getElementById('ticker-inner');
  if (!articles.length) return;
  const items = articles.map(a =>
    `<span class="ticker-item" data-id="${a.id}">${a.title}</span>`
  );
  // double for seamless loop
  inner.innerHTML = items.join('') + items.join('');
  inner.querySelectorAll('.ticker-item').forEach(el => {
    el.addEventListener('click', () => openModal(parseInt(el.dataset.id)));
  });
}

// ─── CLOCK ───────────────────────────────────────────────────────────────────

function startClock() {
  function tick() {
    const now = new Date();
    const hh = String(now.getHours()).padStart(2,'0');
    const mm = String(now.getMinutes()).padStart(2,'0');
    const ss = String(now.getSeconds()).padStart(2,'0');
    document.getElementById('clock').textContent = hh + ':' + mm + ':' + ss;
  }
  tick();
  setInterval(tick, 1000);
}

// ─── NAV ─────────────────────────────────────────────────────────────────────

function setupNav() {
  document.getElementById('nav-pills').addEventListener('click', e => {
    const pill = e.target.closest('.nav-pill');
    if (!pill) return;
    document.querySelectorAll('.nav-pill').forEach(p => p.classList.remove('active'));
    pill.classList.add('active');
    currentCat = pill.dataset.cat;
    renderAll(filterArticles(allArticles, currentCat));
  });
  document.getElementById('btn-refresh').addEventListener('click', () => loadArticles(true));
}

// ─── RENDER ALL ──────────────────────────────────────────────────────────────

function renderAll(articles) {
  const hero       = articles[0] || null;
  const sides      = articles.slice(1, 3);
  const secondary  = articles.slice(3, 6);
  const grid       = articles.slice(6);

  renderHeroRow(hero, sides);
  renderSecondaryRow(secondary);
  renderCardGrid(grid);
}

// ─── HERO ROW ────────────────────────────────────────────────────────────────

function renderHeroRow(hero, sides) {
  const container = document.getElementById('hero-row');
  if (!hero) { container.innerHTML = ''; return; }

  const heroHtml = buildCard(hero, 'hero-main', 'card-img-hero', 'card-title-hero');
  const sidesHtml = sides.map(a => buildCard(a, 'hero-side', 'card-img-side', 'card-title-side')).join('');

  container.innerHTML = heroHtml + `<div class="hero-sides">${sidesHtml}</div>`;
  bindCardClicks(container);
  animateCards(container);
}

// ─── SECONDARY ROW ───────────────────────────────────────────────────────────

function renderSecondaryRow(articles) {
  const container = document.getElementById('secondary-row');
  container.innerHTML = articles
    .map(a => buildCard(a, 'secondary', 'card-img-secondary', 'card-title-secondary'))
    .join('');
  bindCardClicks(container);
  animateCards(container);
}

// ─── CARD GRID ───────────────────────────────────────────────────────────────

function renderCardGrid(articles) {
  const container = document.getElementById('card-grid');
  if (!articles.length) {
    container.innerHTML = '';
    return;
  }
  container.innerHTML = articles
    .map((a, i) => buildCard(a, 'grid', 'card-img-grid', 'card-title-grid', i * 60))
    .join('');
  bindCardClicks(container);
}

// ─── CARD BUILDER ────────────────────────────────────────────────────────────

function buildCard(article, variant, imgClass, titleClass, delayMs) {
  const t = trustInfo(article.trust_score, article.is_fake);
  const style = delayMs ? ` style="animation-delay:${delayMs}ms"` : '';
  const fakeBannerHtml = article.is_fake ? `<div class="fake-banner">FAKE NEWS</div>` : '';

  return `<div class="card card-${variant}"${style} data-id="${article.id}">
    ${imgWrap(article.image_url, article.category, 'card-img ' + imgClass, '')}
    <div class="card-body">
      ${fakeBannerHtml}
      <div class="card-meta">
        ${catTag(article.category)}
        ${trustBadge(article.trust_score, article.is_fake)}
      </div>
      <div class="card-title ${titleClass}">${article.title}</div>
      ${variant !== 'hero-side' ? `<div class="card-excerpt">${article.excerpt}</div>` : ''}
      <div class="card-date">${fmtDate(article.published_at)}</div>
    </div>
  </div>`;
}

function bindCardClicks(container) {
  container.querySelectorAll('.card[data-id]').forEach(el => {
    el.addEventListener('click', () => openModal(parseInt(el.dataset.id)));
  });
}

function animateCards(container) {
  container.querySelectorAll('.card').forEach((el, i) => {
    el.style.animationDelay = (i * 60) + 'ms';
  });
}

// ─── MODAL ───────────────────────────────────────────────────────────────────

function openModal(id) {
  const article = allArticles.find(a => a.id === id);
  if (!article) return;

  const overlay = document.getElementById('modal-overlay');
  const t = trustInfo(article.trust_score, article.is_fake);

  // Image
  const imgWrapEl = document.getElementById('modal-image-wrap');
  if (article.image_url) {
    imgWrapEl.innerHTML = `<img class="modal-image" src="${article.image_url}" alt="${article.category}"
      onerror="this.style.display='none';this.nextElementSibling.style.display='flex';">
      <div class="modal-image-fallback" style="display:none;">${article.category}</div>`;
  } else {
    imgWrapEl.innerHTML = `<div class="modal-image-fallback">${article.category}</div>`;
  }

  // Meta
  document.getElementById('modal-meta').innerHTML =
    catTag(article.category) + trustBadge(article.trust_score, article.is_fake) +
    `<span class="modal-date">${fmtDate(article.published_at)}</span>`;

  // Title
  document.getElementById('modal-title').textContent = article.title;

  // Sources count
  const srcCount = article.sources ? article.sources.length : 0;
  document.getElementById('modal-sources-count').textContent =
    `${srcCount} ${srcCount === 1 ? 'źródło' : srcCount < 5 ? 'źródła' : 'źródeł'}`;

  // Verification panel
  const checks = article.verification && article.verification.checks ? article.verification.checks : [];
  const checksHtml = checks.map(c => {
    const cls = c.status === 'pass' ? 'check-pass' : c.status === 'warn' ? 'check-warn' : 'check-fail';
    const icon = c.status === 'pass' ? 'V' : c.status === 'warn' ? '!' : 'X';
    return `<div class="check-item ${cls}">
      <span class="check-icon">${icon}</span>
      <span>${c.label}</span>
    </div>`;
  }).join('');

  const scoreColor = t.color;
  document.getElementById('modal-verification').innerHTML = `
    <div class="verification-panel">
      <div class="verif-header">Wskaźnik wiarygodności</div>
      <div class="trust-score-number" style="color:${scoreColor}">${article.trust_score}%</div>
      <div class="trust-bar-wrap">
        <div class="trust-bar-fill" id="trust-bar" style="background:${scoreColor};width:0"></div>
      </div>
      <div class="checks-grid">${checksHtml}</div>
    </div>`;

  // Animate trust bar
  setTimeout(() => {
    const bar = document.getElementById('trust-bar');
    if (bar) bar.style.width = article.trust_score + '%';
  }, 80);

  // Fake alert
  const fakeEl = document.getElementById('modal-fake-alert');
  if (article.is_fake && article.fake_reason) {
    fakeEl.innerHTML = `<div class="fake-alert">
      <div class="fake-alert-title">UWAGA: POTENCJALNE FAKE NEWS</div>
      <div class="fake-alert-text">${article.fake_reason}</div>
    </div>`;
  } else {
    fakeEl.innerHTML = '';
  }

  // Discrepancies
  const discEl = document.getElementById('modal-discrepancies');
  const disc = article.verification && article.verification.discrepancies;
  if (disc && disc.length > 0) {
    discEl.innerHTML = `<div class="discrepancies-panel">
      <div class="discrepancies-label">Rozbieżności</div>
      ${disc}
    </div>`;
  } else {
    discEl.innerHTML = '';
  }

  // Content
  const paras = (article.content || '').split('\n\n').filter(Boolean);
  document.getElementById('modal-content').innerHTML =
    paras.map(p => `<p>${p}</p>`).join('');

  // Sources
  const sourcesEl = document.getElementById('modal-sources');
  if (article.sources && article.sources.length) {
    const srcHtml = article.sources.map(s =>
      `<div class="source-item">
        <span class="source-name">${s.name}</span>
        <span class="source-headline">
          ${s.url ? `<a href="${s.url}" target="_blank" rel="noopener">${s.headline}</a>` : s.headline}
        </span>
      </div>`
    ).join('');
    sourcesEl.innerHTML = `<div class="sources-header">Źródła (${article.sources.length})</div>${srcHtml}`;
  } else {
    sourcesEl.innerHTML = '';
  }

  overlay.classList.add('open');
  document.body.classList.add('modal-open');
  document.getElementById('modal-box').scrollTop = 0;
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('open');
  document.body.classList.remove('modal-open');
}

// ─── MODAL CLOSE EVENTS ──────────────────────────────────────────────────────

document.getElementById('modal-close').addEventListener('click', closeModal);
document.getElementById('modal-overlay').addEventListener('click', e => {
  if (e.target === document.getElementById('modal-overlay')) closeModal();
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
});

// ─── INIT ────────────────────────────────────────────────────────────────────

function init() {
  startClock();
  setupNav();
  loadArticles(true);

  if (refreshTimer) clearInterval(refreshTimer);
  refreshTimer = setInterval(() => loadArticles(false), REFRESH_MS);
}

init();
