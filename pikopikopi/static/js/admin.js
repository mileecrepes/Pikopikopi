(() => {
  const $ = (selector) => document.querySelector(selector);
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const loginCard = $('#loginCard');
  const dashboard = $('#adminDashboard');

  async function api(url, options = {}) {
    const response = await fetch(url, {credentials:'same-origin', ...options});
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(data.detail || 'Terjadi kendala.');
    return data;
  }

  function message(selector, text, isError = false) {
    const el = $(selector);
    el.textContent = text;
    el.style.color = isError ? '#a64e40' : '#906441';
  }

  async function refreshDashboard() {
    const [banners, status] = await Promise.all([api('/api/admin/banners'), api('/api/admin/dataset-status')]);
    $('#datasetMetrics').innerHTML = `<div><strong>${new Intl.NumberFormat('id-ID').format(status.respondents)}</strong><span>responden survei</span></div><div><strong>${new Intl.NumberFormat('id-ID').format(status.image_count)}</strong><span>foto aktual tersedia</span></div>`;
    renderBanners(banners.banners || []);
  }

  function renderBanners(banners) {
    if (!banners.length) {
      $('#bannerList').innerHTML = '<p class="muted">Belum ada banner sponsor. Tambahkan banner pertama melalui formulir di atas.</p>';
      return;
    }
    $('#bannerList').innerHTML = banners.map((b) => `
      <div class="banner-row">
        ${b.image_url ? `<img src="${esc(b.image_url)}" alt="">` : '<div class="banner-row-placeholder">✦</div>'}
        <div class="banner-row-copy"><strong>${esc(b.title)} · ${esc(b.sponsor)}</strong><p>Kata kunci: ${esc((b.keywords || []).join(', '))} · ${b.active ? 'Aktif' : 'Nonaktif'}</p></div>
        <div class="banner-row-actions"><button type="button" data-toggle="${esc(b.id)}" data-active="${b.active}">${b.active ? 'Nonaktifkan' : 'Aktifkan'}</button><button class="delete" type="button" data-delete="${esc(b.id)}">Hapus</button></div>
      </div>`).join('');
    $$('[data-toggle]').forEach((button) => button.addEventListener('click', async () => {
      try { await api(`/api/admin/banners/${button.dataset.toggle}`, {method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({active:button.dataset.active !== 'true'})}); await refreshDashboard(); }
      catch (error) { alert(error.message); }
    }));
    $$('[data-delete]').forEach((button) => button.addEventListener('click', async () => {
      if (!confirm('Hapus banner ini?')) return;
      try { await api(`/api/admin/banners/${button.dataset.delete}`, {method:'DELETE'}); await refreshDashboard(); }
      catch (error) { alert(error.message); }
    }));
  }
  const $$ = (selector) => [...document.querySelectorAll(selector)];

  async function showDashboard() {
    loginCard.hidden = true;
    dashboard.hidden = false;
    await refreshDashboard();
  }

  $('#loginForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    message('#loginMessage', 'Memeriksa akses...');
    try {
      await api('/api/admin/login', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:$('#adminPassword').value})});
      await loadCoffeeTypes();
      await showDashboard();
    } catch (error) { message('#loginMessage', error.message, true); }
  });

  $('#logoutButton').addEventListener('click', async () => {
    await api('/api/admin/logout', {method:'POST'});
    dashboard.hidden = true;
    loginCard.hidden = false;
    $('#adminPassword').value = '';
    message('#loginMessage', 'Kamu sudah keluar dari dashboard.');
  });

  $('#bannerForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    message('#bannerMessage', 'Menyimpan banner...');
    try {
      let imageFile = '';
      const file = $('#bannerImage').files[0];
      if (file) {
        const upload = new FormData(); upload.append('file', file);
        const result = await api('/api/admin/upload-banner-image', {method:'POST',body:upload});
        imageFile = result.filename;
      }
      const payload = {
        sponsor: $('#sponsorName').value,
        title: $('#bannerTitle').value,
        description: $('#bannerDescription').value,
        keywords: $('#bannerKeywords').value.split(',').map((x) => x.trim()).filter(Boolean),
        target_url: $('#bannerUrl').value,
        image_file: imageFile,
        active: $('#bannerActive').checked
      };
      await api('/api/admin/banners', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      $('#bannerForm').reset(); $('#bannerActive').checked = true;
      message('#bannerMessage', 'Banner berhasil disimpan.');
      await refreshDashboard();
    } catch (error) { message('#bannerMessage', error.message, true); }
  });

  $('#datasetForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const file = $('#datasetFile').files[0];
    if (!file) return;
    if (!confirm('Dataset aktif akan diganti dengan file CSV ini. Lanjutkan?')) return;
    message('#datasetMessage', 'Mengunggah dan menghitung ulang data...');
    try {
      const form = new FormData(); form.append('file', file);
      const result = await api('/api/admin/dataset', {method:'POST',body:form});
      message('#datasetMessage', `Dataset diperbarui. ${new Intl.NumberFormat('id-ID').format(result.respondents)} respons terbaca.`);
      $('#datasetForm').reset();
      await refreshDashboard();
    } catch (error) { message('#datasetMessage', error.message, true); }
  });


  $('#coffeeImageForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const files = [...$('#coffeeImageFiles').files];
    if (!files.length) return;
    message('#coffeeImageMessage', 'Mengunggah foto katalog...');
    try {
      const form = new FormData();
      form.append('label', $('#coffeeImageLabel').value);
      form.append('credit', $('#coffeeImageCredit').value);
      form.append('license', $('#coffeeImageLicense').value);
      form.append('source_url', $('#coffeeImageSource').value);
      files.forEach((file) => form.append('files', file));
      const result = await api('/api/admin/upload-coffee-images', {method:'POST',body:form});
      message('#coffeeImageMessage', `${result.saved} foto berhasil ditambahkan ke katalog.`);
      $('#coffeeImageForm').reset();
      await refreshDashboard();
    } catch (error) { message('#coffeeImageMessage', error.message, true); }
  });

  async function loadCoffeeTypes() {
    try {
      const data = await api('/api/catalog');
      const select = $('#coffeeImageLabel');
      (data.items || []).forEach((item) => {
        const option = document.createElement('option');
        option.value = item.label;
        option.textContent = item.display_name;
        select.append(option);
      });
    } catch (_) {}
  }

  api('/api/admin/status').then(async (status) => {
    if (status.authenticated) { await loadCoffeeTypes(); return showDashboard(); }
    if (!status.password_configured) message('#loginMessage', 'Admin belum diaktifkan. Atur ADMIN_PASSWORD pada konfigurasi environment sebelum login.', true);
  }).catch((error) => message('#loginMessage', error.message, true));
})();
