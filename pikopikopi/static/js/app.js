(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const form = $('#filterForm');
  const grid = $('#recommendationGrid');
  const resultSubtitle = $('#resultsSubtitle');
  const sponsorSlot = $('#sponsorSlot');
  const dialog = $('#detailDialog');
  let currentLimit = 5;
  let lastResults = [];

  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const titleCase = (value) => String(value || '').replaceAll('_', ' ').replace(/\b\w/g, (m) => m.toUpperCase());
  const formatCount = (value) => new Intl.NumberFormat('id-ID').format(Number(value || 0));
  const tasteLabels = {fruity:'Fruity', chocolatey:'Chocolatey', floral:'Floral', full_bodied:'Full bodied', sweet:'Sweet', nutty:'Nutty', bold:'Bold', caramelized:'Caramelized', bright:'Bright', juicy:'Juicy'};
  const roastLabels = {light:'Light', medium:'Medium', dark:'Dark'};
  const ratingLabel = (value) => ({1:'Sangat rendah',2:'Rendah',3:'Sedang',4:'Tinggi',5:'Sangat tinggi'}[value] || '—');

  async function api(url, options = {}) {
    const response = await fetch(url, {credentials:'same-origin', ...options});
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(data.detail || 'Terjadi kendala. Coba lagi.');
    return data;
  }

  function selectedPreferences() {
    return {
      taste: $('#taste').value,
      search: $('#searchKeyword').value.trim(),
      drink_type: $('#drinkType').value,
      roast: $('#roast').value,
      bitterness: $('#bitterness').value,
      acidity: $('#acidity').value,
      strength: $('#strength').value,
      limit: currentLimit
    };
  }

  function hasActivePreferences() {
    const p = selectedPreferences();
    return Boolean(p.search || p.taste || p.drink_type || p.roast || p.bitterness || p.acidity || p.strength);
  }

  function selectionSummary() {
    const p = selectedPreferences();
    const terms = [];
    if (p.search) terms.push(`"${p.search}"`);
    if (p.taste) terms.push(tasteLabels[p.taste] || p.taste);
    if (p.drink_type) terms.push(titleCase(p.drink_type));
    if (p.roast) terms.push(`${roastLabels[p.roast]} roast`);
    if (p.bitterness) terms.push(`pahit ${p.bitterness}/5`);
    if (p.acidity) terms.push(`acidity ${p.acidity}/5`);
    if (p.strength) terms.push(`kekuatan ${p.strength}/5`);
    return terms;
  }

  function updateRangeLabels() {
    ['bitterness','acidity','strength'].forEach((id) => {
      const val = $(`#${id}`).value;
      $(`#${id}Value`).textContent = val ? `${val}/5` : 'Bebas';
    });
  }

  function renderCard(item, index) {
    const tags = (item.tags || []).slice(0, 3).map((tag, i) => `<span class="taste-tag ${i === 0 ? 'blue' : ''}">${esc(tasteLabels[tag] || titleCase(tag))}</span>`).join('');
    const photo = item.image || '/static/images/coffee-placeholder.svg';
    const isPlaceholder = photo.includes('coffee-placeholder.svg');
    const votes = item.survey_votes ? `${formatCount(item.survey_votes)} pemilih di survei` : 'Belum ada hitungan khusus';
    const rawCredit = item.image_credit || '';
    const creditText = rawCredit.replace(/<[^>]+>/g, '').trim();
    return `
      <article class="coffee-card">
        <div class="card-image-wrap">
          <img src="${esc(photo)}" alt="${esc(item.display_name)}" loading="lazy" onerror="this.onerror=null;this.src='/static/images/coffee-placeholder.svg'">
          <span class="card-rank">#${index + 1} MATCH</span>
          <span class="match-pill">${hasActivePreferences() ? `${Number(item.match_score || 0).toFixed(0)}% cocok*` : 'Sering dipilih'}</span>
          ${isPlaceholder ? '<span class="photo-state">Ilustrasi sementara</span>' : (creditText ? `<span class="photo-credit" title="${esc(creditText)}">© Wikimedia Commons</span>` : '')}
        </div>
        <div class="card-body">
          <h3>${esc(item.display_name)}</h3>
          <p class="card-desc">${esc(item.description)}</p>
          <div class="tag-row">${tags}</div>
          <div class="card-meta">
            <div><span>Bitterness</span><strong>${item.bitterness}/5</strong></div>
            <div><span>Acidity</span><strong>${item.acidity}/5</strong></div>
            <div><span>Roast</span><strong>${esc(titleCase(item.roast))}</strong></div>
          </div>
          <div class="card-actions"><span class="card-votes">${esc(votes)}</span><button class="card-detail" type="button" data-detail="${esc(item.label)}">Lihat detail <span>↗</span></button></div>
        </div>
      </article>`;
  }

  function showEmpty() {
    grid.innerHTML = `<div class="loading-card"><strong>Belum ada hasil yang cocok.</strong><p>Coba longgarkan satu atau dua filter untuk melihat pilihan lainnya.</p></div>`;
  }

  function renderResults(items) {
    lastResults = items;
    if (!items.length) return showEmpty();
    grid.innerHTML = items.map(renderCard).join('');
    $$('.card-detail', grid).forEach((button) => button.addEventListener('click', () => openDetail(button.dataset.detail)));
  }

  function openDetail(label) {
    const item = lastResults.find((entry) => entry.label === label);
    if (!item) return;
    const tags = (item.tags || []).map((tag) => `<span class="taste-tag">${esc(tasteLabels[tag] || titleCase(tag))}</span>`).join('');
    const votesText = item.survey_votes ? `${formatCount(item.survey_votes)} responden menyebut minuman ini sebagai favorit.` : 'Belum ada jumlah pemilih yang cukup spesifik untuk minuman ini pada kolom favorit survei.';
    const reasons = (item.match_reasons || []).map((reason) => `<li>${esc(reason)}</li>`).join('');
    const isPlaceholder = (item.image || '').includes('coffee-placeholder.svg');
    const rawCredit = item.image_credit || '';
    const creditText = rawCredit.replace(/<[^>]+>/g, '').trim();
    const photoNote = isPlaceholder
      ? 'Foto produk belum tersedia. Gambar ini hanya ilustrasi sementara. '
      : (creditText ? `Foto: ${creditText} · Wikimedia Commons (CC). ` : 'Foto: Wikimedia Commons. ');
    $('#detailContent').innerHTML = `
      <div class="detail-layout">
        <div class="detail-visual">
          <img src="${esc(item.image || '/static/images/coffee-placeholder.svg')}" alt="${esc(item.display_name)}">
          ${!isPlaceholder ? `<p class="detail-photo-credit">© Wikimedia Commons${creditText ? ` · ${esc(creditText)}` : ''}</p>` : ''}
        </div>
        <div class="detail-copy">
          <div class="eyebrow eyebrow-brown">${hasActivePreferences() ? `YOUR COFFEE MATCH · ${Number(item.match_score || 0).toFixed(0)}%` : 'POPULAR FROM THE SURVEY'}</div>
          <h2>${esc(item.display_name)}</h2>
          <p>${esc(item.description)} ${esc(item.serving || '')}</p>
          <div class="tag-row">${tags}</div>
          <div class="detail-stats">
            <div class="detail-stat"><small>Bitterness</small><strong>${item.bitterness}/5</strong></div>
            <div class="detail-stat"><small>Acidity</small><strong>${item.acidity}/5</strong></div>
            <div class="detail-stat"><small>Strength</small><strong>${item.strength}/5</strong></div>
            <div class="detail-stat"><small>Roast</small><strong>${esc(titleCase(item.roast))}</strong></div>
          </div>
          <p><strong>Kenapa masuk rekomendasi?</strong></p><ul class="detail-reasons">${reasons}</ul>
          <p class="detail-votes">${esc(votesText)}</p>
          <div class="detail-footnote">${esc(photoNote)}Nilai bitterness, acidity, strength, dan roast adalah estimasi karakter umum minuman, bukan data pengukuran langsung.</div>
        </div>
      </div>`;
    if (typeof dialog.showModal === 'function') dialog.showModal();
    else dialog.setAttribute('open', '');
  }

  async function loadRecommendations() {
    grid.innerHTML = `<div class="loading-card"><span class="loading-spinner"></span><p>Mencocokkan preferensimu dengan katalog kopi...</p></div>`;
    const preferences = selectedPreferences();
    const selection = selectionSummary();
    resultSubtitle.textContent = selection.length ? `Preferensi yang dipilih: ${selection.join(' · ')}.` : 'Pilihan populer berdasarkan data preferensi survei.';
    try {
      const data = await api('/api/recommendations', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(preferences)});
      renderResults(data.results || []);
      await loadSponsor(selection.join(' '));
    } catch (error) {
      grid.innerHTML = `<div class="loading-card"><strong>Rekomendasi belum bisa dimuat.</strong><p>${esc(error.message)}</p></div>`;
    }
  }

  async function loadSponsor(query) {
    if (!query) { sponsorSlot.hidden = true; sponsorSlot.innerHTML = ''; return; }
    try {
      const data = await api(`/api/banner?q=${encodeURIComponent(query)}`);
      const b = data.banner;
      if (!b) { sponsorSlot.hidden = true; sponsorSlot.innerHTML = ''; return; }
      sponsorSlot.hidden = false;
      sponsorSlot.innerHTML = `${b.image_url ? `<img class="sponsor-image" src="${esc(b.image_url)}" alt="Banner ${esc(b.sponsor)}">` : '<div class="sponsor-image sponsor-placeholder">✦</div>'}
        <div class="sponsor-copy"><span class="sponsor-label">Sponsored · ${esc(b.sponsor)}</span><h3>${esc(b.title)}</h3><p>${esc(b.description || '')}</p></div>
        ${b.target_url ? `<a class="sponsor-cta" href="${esc(b.target_url)}" target="_blank" rel="noopener noreferrer">Lihat penawaran ↗</a>` : ''}`;
    } catch (_) { sponsorSlot.hidden = true; }
  }

  async function loadCatalog() {
    const data = await api('/api/catalog');
    const select = $('#drinkType');
    (data.items || []).forEach((item) => {
      const option = document.createElement('option');
      option.value = item.label;
      option.textContent = item.display_name;
      select.append(option);
    });
  }

  async function loadStats() {
    try {
      const stats = await api('/api/stats');
      const count = formatCount(stats.respondents);
      $('#respondentCount').textContent = count;
      $('#statResponses').textContent = count;
    } catch (_) {}
  }

  form.addEventListener('submit', (event) => { event.preventDefault(); loadRecommendations(); });
  form.addEventListener('reset', () => setTimeout(() => { updateRangeLabels(); loadRecommendations(); }, 0));
  ['bitterness','acidity','strength'].forEach((id) => $(`#${id}`).addEventListener('change', updateRangeLabels));
  $$('.segment').forEach((button) => button.addEventListener('click', () => {
    $$('.segment').forEach((b) => b.classList.toggle('active', b === button));
    currentLimit = Number(button.dataset.limit) === 10 ? 10 : 5;
    loadRecommendations();
  }));
  $('#dialogClose').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });
  $('#menuToggle').addEventListener('click', () => {
    const nav = $('#mainNav');
    const open = nav.classList.toggle('open');
    $('#menuToggle').setAttribute('aria-expanded', String(open));
  });
  $$('#mainNav a').forEach((a) => a.addEventListener('click', () => { $('#mainNav').classList.remove('open'); $('#menuToggle').setAttribute('aria-expanded','false'); }));

  loadStats();
  loadCatalog().then(loadRecommendations).catch((error) => {
    grid.innerHTML = `<div class="loading-card"><strong>Website belum siap.</strong><p>${esc(error.message)}</p></div>`;
  });
  updateRangeLabels();
})();
