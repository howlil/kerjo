<script>
  import { onMount } from 'svelte';

  // State
  let jobs = $state([]);
  let searches = $state([]);
  let latestRuns = $state([]);
  let loading = $state(false);
  let runningScraper = $state(false);

  // Filters
  let selectedArea = $state('all');
  let selectedSource = $state('all');
  let onlyNew = $state(false);
  let searchQuery = $state('');

  // Add search form modal
  let showAddSearch = $state(false);
  let newKeyword = $state('');
  let newArea = $state('all');
  let newSources = $state({
    jobstreet: true,
    kalibrr: true,
    linkedin: true,
    glints: true,
    dealls: true,
    karir: true,
    techinasia: true
  });

  const areas = [
    { id: 'all', label: 'Semua Area' },
    { id: 'jakarta_selatan', label: 'Jakarta Selatan' },
    { id: 'jakarta_barat', label: 'Jakarta Barat' },
    { id: 'jakarta_pusat', label: 'Jakarta Pusat' },
    { id: 'tangerang_selatan', label: 'Tangerang Selatan' },
    { id: 'bsd', label: 'BSD' },
    { id: 'alam_sutera', label: 'Alam Sutera' },
    { id: 'unspecified', label: 'Tidak Spesifik (Jakarta/Tng)' },
  ];

  const sourceColors = {
    jobstreet: 'bg-purple-100 text-purple-800 border-purple-200',
    kalibrr: 'bg-amber-100 text-amber-800 border-amber-200',
    linkedin: 'bg-sky-100 text-sky-800 border-sky-200',
    glints: 'bg-emerald-100 text-emerald-800 border-emerald-200',
    dealls: 'bg-rose-100 text-rose-800 border-rose-200',
    karir: 'bg-orange-100 text-orange-800 border-orange-200',
    techinasia: 'bg-red-100 text-red-800 border-red-200'
  };

  async function loadJobs() {
    loading = true;
    try {
      const params = new URLSearchParams();
      if (selectedArea !== 'all') params.set('area', selectedArea);
      if (selectedSource !== 'all') params.set('source', selectedSource);
      if (onlyNew) params.set('is_new', '1');
      if (searchQuery.trim()) params.set('q', searchQuery.trim());
      params.set('limit', '200');

      const res = await fetch(`/api/jobs?${params.toString()}`);
      const data = await res.json();
      jobs = data.jobs || [];
    } catch (e) {
      console.error('Error loading jobs:', e);
    } finally {
      loading = false;
    }
  }

  async function loadSearches() {
    try {
      const res = await fetch('/api/searches');
      const data = await res.json();
      searches = data.searches || [];
    } catch (e) {
      console.error('Error loading searches:', e);
    }
  }

  async function loadRuns() {
    try {
      const res = await fetch('/api/runs');
      const data = await res.json();
      latestRuns = data.runs || [];
    } catch (e) {
      console.error('Error loading runs:', e);
    }
  }

  async function triggerRun() {
    if (runningScraper) return;
    runningScraper = true;
    try {
      const res = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      await loadRuns();
      await loadJobs();
    } catch (e) {
      alert('Gagal menjalankan scraper: ' + e);
    } finally {
      runningScraper = false;
    }
  }

  async function markJobSeen(job) {
    if (!job.is_new) return;
    job.is_new = 0;
    try {
      const ids = job.ids && job.ids.length > 0 ? job.ids : [job.id];
      await Promise.all(ids.map(id => fetch(`/api/jobs/${id}/seen`, { method: 'POST' })));
    } catch (e) {
      console.error('Error marking seen:', e);
    }
  }

  async function markAllSeen() {
    if (!confirm('Tandai semua lowongan saat ini sebagai sudah dilihat?')) return;
    try {
      await fetch('/api/jobs/seen-all', { method: 'POST' });
      for (const j of jobs) j.is_new = 0;
    } catch (e) {
      alert('Error: ' + e);
    }
  }

  async function toggleSearch(searchId) {
    try {
      await fetch(`/api/searches/${searchId}/toggle`, { method: 'PUT' });
      await loadSearches();
    } catch (e) {
      alert('Gagal toggle: ' + e);
    }
  }

  async function deleteSearch(searchId) {
    if (!confirm('Hapus pencarian tersimpan ini?')) return;
    try {
      await fetch(`/api/searches/${searchId}`, { method: 'DELETE' });
      await loadSearches();
    } catch (e) {
      alert('Gagal menghapus: ' + e);
    }
  }

  async function submitNewSearch(e) {
    e.preventDefault();
    const chosenSources = Object.keys(newSources).filter(k => newSources[k]);
    if (chosenSources.length === 0) {
      alert('Pilih minimal satu sumber lowongan.');
      return;
    }
    try {
      await fetch('/api/searches', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          keyword: newKeyword,
          area: newArea,
          sources: chosenSources
        })
      });
      newKeyword = '';
      showAddSearch = false;
      await loadSearches();
    } catch (e) {
      alert('Gagal menyimpan pencarian: ' + e);
    }
  }

  function formatTime(isoStr) {
    if (!isoStr) return '-';
    try {
      const d = new Date(isoStr);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' ' + d.toLocaleDateString([], { day: 'numeric', month: 'short' });
    } catch {
      return isoStr;
    }
  }

  onMount(() => {
    loadJobs();
    loadSearches();
    loadRuns();
  });
</script>

<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <!-- Top Navigation & Actions -->
  <header class="flex flex-col md:flex-row md:items-center md:justify-between pb-6 border-b border-slate-200 gap-4">
    <div>
      <div class="flex items-center gap-3">
        <h1 class="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
          <span class="bg-indigo-600 text-white p-1.5 rounded-lg text-lg">⚡</span>
          Jobhunt
        </h1>
        <span class="text-xs px-2.5 py-0.5 rounded-full font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          Auto-run tiap jam
        </span>
      </div>
      <p class="text-sm text-slate-500 mt-1">
        Aggregator lowongan kerja lokal (JobStreet, Kalibrr, LinkedIn, Glints, Dealls, Karir.com, Tech in Asia)
      </p>
    </div>

    <div class="flex flex-wrap items-center gap-2.5">
      <button
        onclick={markAllSeen}
        class="text-xs font-medium px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 transition shadow-xs"
      >
        ✓ Tandai Semua Dilihat
      </button>

      <button
        onclick={() => (showAddSearch = true)}
        class="text-xs font-medium px-3.5 py-2 rounded-lg bg-white border border-indigo-200 text-indigo-700 hover:bg-indigo-50 transition shadow-xs"
      >
        + Simpan Pencarian
      </button>

      <button
        onclick={triggerRun}
        disabled={runningScraper}
        class="text-xs font-semibold px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white transition shadow-sm disabled:opacity-60 flex items-center gap-2"
      >
        {#if runningScraper}
          <span class="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
          Mengambil data...
        {:else}
          ↻ Run Sekarang
        {/if}
      </button>
    </div>
  </header>

  <!-- Saved Searches Quick Bar -->
  <section class="mt-6 p-4 bg-white rounded-xl border border-slate-200 shadow-xs">
    <div class="flex items-center justify-between mb-3">
      <h2 class="text-xs font-bold uppercase tracking-wider text-slate-500">Pencarian Tersimpan (Dijalankan Tiap Jam)</h2>
      <span class="text-xs text-slate-400">{searches.length} pencarian aktif</span>
    </div>

    {#if searches.length === 0}
      <div class="text-xs text-slate-500 py-2">
        Belum ada pencarian tersimpan. Klik "+ Simpan Pencarian" untuk mulai mengotomasi scraping tiap jam.
      </div>
    {:else}
      <div class="flex flex-wrap gap-2">
        {#each searches as s}
          <div class="inline-flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg border {s.is_active ? 'bg-slate-50 border-slate-300 text-slate-800' : 'bg-slate-100 border-dashed border-slate-300 text-slate-400 opacity-60'}">
            <button
              onclick={() => toggleSearch(s.id)}
              class="w-2.5 h-2.5 rounded-full {s.is_active ? 'bg-emerald-500' : 'bg-slate-300'}"
              title={s.is_active ? 'Klik untuk non-aktifkan' : 'Klik untuk aktifkan'}
            ></button>
            <span class="font-medium">{s.keyword}</span>
            <span class="text-[10px] text-slate-500">({s.area})</span>
            <button
              onclick={() => deleteSearch(s.id)}
              class="hover:text-red-500 ml-1 text-slate-400"
              title="Hapus"
            >✕</button>
          </div>
        {/each}
      </div>
    {/if}
  </section>

  <!-- Filters Row -->
  <section class="mt-6 flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between">
    <div class="flex flex-wrap gap-2 items-center">
      <!-- Area selector -->
      <select
        bind:value={selectedArea}
        onchange={loadJobs}
        class="text-xs font-medium px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-700 shadow-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
      >
        {#each areas as a}
          <option value={a.id}>{a.label}</option>
        {/each}
      </select>

      <!-- Source selector -->
      <select
        bind:value={selectedSource}
        onchange={loadJobs}
        class="text-xs font-medium px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-700 shadow-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
      >
        <option value="all">Semua Situs</option>
        <option value="jobstreet">JobStreet</option>
        <option value="kalibrr">Kalibrr</option>
        <option value="linkedin">LinkedIn</option>
        <option value="glints">Glints</option>
        <option value="dealls">Dealls</option>
        <option value="karir">Karir.com</option>
        <option value="techinasia">Tech in Asia</option>
      </select>

      <!-- Only NEW toggle -->
      <button
        onclick={() => { onlyNew = !onlyNew; loadJobs(); }}
        class="text-xs font-medium px-3 py-2 rounded-lg border transition shadow-xs flex items-center gap-1.5 {onlyNew ? 'bg-amber-50 border-amber-300 text-amber-900 font-semibold' : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50'}"
      >
        <span>🔥</span>
        Hanya yang NEW
      </button>
    </div>

    <!-- Search Text filter -->
    <div class="relative min-w-[240px]">
      <input
        type="text"
        placeholder="Filter judul / perusahaan..."
        bind:value={searchQuery}
        oninput={loadJobs}
        class="w-full text-xs px-3 py-2 pl-8 rounded-lg bg-white border border-slate-300 text-slate-800 placeholder-slate-400 shadow-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
      />
      <span class="absolute left-2.5 top-2 text-slate-400 text-xs">🔍</span>
    </div>
  </section>

  <!-- Job Cards List -->
  <main class="mt-6">
    <div class="flex items-center justify-between pb-3">
      <span class="text-xs font-semibold text-slate-600">
        Menampilkan {jobs.length} lowongan
      </span>
      {#if loading}
        <span class="text-xs text-indigo-600 flex items-center gap-1.5">
          <span class="w-2.5 h-2.5 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin"></span>
          Memuat...
        </span>
      {/if}
    </div>

    {#if jobs.length === 0 && !loading}
      <div class="text-center py-16 bg-white rounded-2xl border border-slate-200">
        <p class="text-slate-400 text-3xl mb-2">📋</p>
        <p class="text-sm font-semibold text-slate-700">Tidak ada lowongan yang sesuai kriteria.</p>
        <p class="text-xs text-slate-400 mt-1">Coba ubah filter area atau klik "Run Sekarang" untuk mengambil data terbaru.</p>
      </div>
    {:else}
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {#each jobs as j}
          <div
            class="bg-white rounded-xl border p-4 shadow-xs hover:shadow-md transition flex flex-col justify-between relative group {j.is_new ? 'border-amber-400 ring-2 ring-amber-400/20' : 'border-slate-200'}"
          >
            <div>
              <!-- Badges -->
              <div class="flex flex-wrap items-center gap-1.5 mb-2.5">
                {#if j.is_new}
                  <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500 text-white uppercase tracking-wider shadow-2xs">
                    NEW
                  </span>
                {/if}

                {#if j.sources && j.sources.length > 1}
                  <span class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                    {j.sources.length} SITUS
                  </span>
                  {#each j.sources as src}
                    <span class="text-[10px] font-semibold px-2 py-0.5 rounded-full border {sourceColors[src] || 'bg-slate-100 text-slate-700'}">
                      {src.toUpperCase()}
                    </span>
                  {/each}
                {:else}
                  <span class="text-[10px] font-semibold px-2 py-0.5 rounded-full border {sourceColors[j.source] || 'bg-slate-100 text-slate-700'}">
                    {(j.source || 'JOB').toUpperCase()}
                  </span>
                {/if}

                <span class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                  {j.area.replace('_', ' ').toUpperCase()}
                </span>

                {#if j.is_remote}
                  <span class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-teal-50 text-teal-700 border border-teal-200">
                    Remote/Hybrid
                  </span>
                {/if}
              </div>

              <!-- Title & Company -->
              <h3 class="text-sm font-bold text-slate-900 group-hover:text-indigo-600 transition line-clamp-2">
                <a
                  href={j.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onclick={() => markJobSeen(j)}
                >
                  {j.title}
                </a>
              </h3>

              <p class="text-xs font-semibold text-slate-700 mt-1">
                {j.company}
              </p>

              <!-- Salary & Details -->
              {#if j.salary}
                <p class="text-xs font-medium text-emerald-700 mt-2 flex items-center gap-1">
                  <span>💰</span> {j.salary}
                </p>
              {/if}

              <p class="text-[11px] text-slate-400 mt-2 flex items-center gap-1 line-clamp-1">
                <span>📍</span> {j.location_raw || 'Lokasi tidak spesifik'}
              </p>
            </div>

            <!-- Footer Card -->
            <div class="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
              <span>{formatTime(j.posted_at || j.first_seen_at)}</span>
              <div class="flex items-center gap-2">
                {#if j.sources && j.sources.length > 1 && j.urls}
                  {#each j.sources as src}
                    <a
                      href={j.urls[src]}
                      target="_blank"
                      rel="noopener noreferrer"
                      onclick={() => markJobSeen(j)}
                      class="text-indigo-600 font-semibold hover:underline capitalize"
                    >
                      {src} ↗
                    </a>
                  {/each}
                {:else}
                  <a
                    href={j.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    onclick={() => markJobSeen(j)}
                    class="text-indigo-600 font-semibold hover:underline inline-flex items-center gap-0.5"
                  >
                    Buka Postingan ↗
                  </a>
                {/if}
              </div>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </main>

  <!-- Add Saved Search Modal -->
  {#if showAddSearch}
    <div class="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
      <div class="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-100">
        <div class="flex items-center justify-between pb-4 border-b border-slate-100">
          <h3 class="text-base font-bold text-slate-900">Tambah Pencarian Tersimpan</h3>
          <button
            onclick={() => (showAddSearch = false)}
            class="text-slate-400 hover:text-slate-600"
          >✕</button>
        </div>

        <form onsubmit={submitNewSearch} class="mt-4 space-y-4">
          <div>
            <label for="kw-input" class="block text-xs font-semibold text-slate-700 mb-1">Kata Kunci / Posisi</label>
            <input
              id="kw-input"
              type="text"
              required
              placeholder="e.g. Backend Engineer, Golang, DevOps"
              bind:value={newKeyword}
              class="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            />
          </div>

          <div>
            <label for="area-select" class="block text-xs font-semibold text-slate-700 mb-1">Target Area</label>
            <select
              id="area-select"
              bind:value={newArea}
              class="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            >
              {#each areas as a}
                <option value={a.id}>{a.label}</option>
              {/each}
            </select>
          </div>

          <div>
            <span class="block text-xs font-semibold text-slate-700 mb-2">Pilih Situs yang Di-scrape Tiap Jam:</span>
            <div class="grid grid-cols-2 gap-2 text-xs">
              <label class="flex items-center gap-2">
                <input type="checkbox" bind:checked={newSources.jobstreet} class="rounded text-indigo-600" />
                JobStreet
              </label>
              <label class="flex items-center gap-2">
                <input type="checkbox" bind:checked={newSources.kalibrr} class="rounded text-indigo-600" />
                Kalibrr
              </label>
              <label class="flex items-center gap-2">
                <input type="checkbox" bind:checked={newSources.linkedin} class="rounded text-indigo-600" />
                LinkedIn
              </label>
              <label class="flex items-center gap-2">
                <input type="checkbox" bind:checked={newSources.glints} class="rounded text-indigo-600" />
                Glints
              </label>
              <label class="flex items-center gap-2">
                <input type="checkbox" bind:checked={newSources.dealls} class="rounded text-indigo-600" />
                Dealls
              </label>
              <label class="flex items-center gap-2">
                <input type="checkbox" bind:checked={newSources.karir} class="rounded text-indigo-600" />
                Karir.com
              </label>
              <label class="flex items-center gap-2">
                <input type="checkbox" bind:checked={newSources.techinasia} class="rounded text-indigo-600" />
                Tech in Asia
              </label>
            </div>
          </div>

          <div class="pt-4 flex justify-end gap-2">
            <button
              type="button"
              onclick={() => (showAddSearch = false)}
              class="text-xs px-3 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50"
            >Batal</button>
            <button
              type="submit"
              class="text-xs font-semibold px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs"
            >Simpan Pencarian</button>
          </div>
        </form>
      </div>
    </div>
  {/if}
</div>
