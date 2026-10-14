<script>
  import { onMount } from 'svelte';
  import Icon from './components/Icon.svelte';
  import Timeline from './components/Timeline.svelte';

  // Core State
  let jobs = $state([]);
  let searches = $state([]);
  let latestRuns = $state([]);
  let companies = $state([]);
  let loading = $state(false);
  let runningScraper = $state(false);
  let activeJob = $state(null);

  // Filters State
  let selectedArea = $state('all');
  let selectedRole = $state('all');
  let selectedExperience = $state('all');
  let selectedSource = $state('all');
  let selectedCompany = $state('all');
  let onlyNew = $state(false);
  let searchQuery = $state('');

  // Add search modal
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
    { id: 'unspecified', label: 'Jakarta / Tangerang (Umum)' },
  ];

  const roleCategories = [
    { id: 'all', label: 'Semua Role' },
    { id: 'backend', label: 'Backend' },
    { id: 'frontend', label: 'Frontend' },
    { id: 'fullstack', label: 'Fullstack' },
    { id: 'mobile', label: 'Mobile' },
    { id: 'data', label: 'Data / AI' },
    { id: 'infra_network', label: 'Infra / DevOps' },
    { id: 'qa', label: 'QA / Testing' },
    { id: 'product_engineer', label: 'Product Engineer' },
    { id: 'software_engineer', label: 'Software Engineer' },
  ];

  const experienceLevels = [
    { id: 'all', label: 'Semua Level' },
    { id: 'entry', label: 'Entry Level (0-1 / 0-2 th)' },
    { id: 'mid', label: 'Mid Level (Min 1-2 th)' },
    { id: 'senior', label: 'Senior (>3 / >5 th / Lead)' },
  ];

  const platforms = [
    { id: 'all', label: 'Semua Situs' },
    { id: 'jobstreet', label: 'JobStreet' },
    { id: 'kalibrr', label: 'Kalibrr' },
    { id: 'linkedin', label: 'LinkedIn' },
    { id: 'glints', label: 'Glints' },
    { id: 'dealls', label: 'Dealls' },
    { id: 'karir', label: 'Karir.com' },
    { id: 'techinasia', label: 'Tech in Asia' },
  ];

  async function loadJobs() {
    loading = true;
    try {
      const params = new URLSearchParams();
      if (selectedArea !== 'all') params.set('area', selectedArea);
      if (selectedRole !== 'all') params.set('role_category', selectedRole);
      if (selectedExperience !== 'all') params.set('experience_level', selectedExperience);
      if (selectedSource !== 'all') params.set('source', selectedSource);
      if (selectedCompany !== 'all') params.set('company', selectedCompany);
      if (onlyNew) params.set('is_new', '1');
      if (searchQuery.trim()) params.set('q', searchQuery.trim());
      params.set('limit', '300');

      const res = await fetch(`/api/jobs?${params.toString()}`);
      const data = await res.json();
      jobs = data.jobs || [];

      // Update activeJob reference if still in list
      if (activeJob) {
        const found = jobs.find(j => j.id === activeJob.id);
        if (found) activeJob = found;
      }
    } catch (e) {
      console.error('Error loading jobs:', e);
    } finally {
      loading = false;
    }
  }

  async function loadCompanies() {
    try {
      const res = await fetch('/api/companies');
      const data = await res.json();
      companies = data.companies || [];
    } catch (e) {
      console.error('Error loading companies:', e);
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
      await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      await loadRuns();
      await loadJobs();
      await loadCompanies();
    } catch (e) {
      alert('Gagal menjalankan scraper: ' + e);
    } finally {
      runningScraper = false;
    }
  }

  function selectJob(job) {
    activeJob = job;
    if (job && job.is_new) {
      markJobSeen(job);
    }
  }

  function filterByCompany(compName) {
    if (!compName) return;
    selectedCompany = compName;
    loadJobs();
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
      await loadJobs();
      await loadCompanies();
    } catch (e) {
      alert('Gagal menyimpan pencarian: ' + e);
    }
  }

  function formatTime(isoStr) {
    if (!isoStr) return '-';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString('id-ID', { day: 'numeric', month: 'short' });
    } catch {
      return isoStr;
    }
  }

  function formatArea(areaStr) {
    if (!areaStr) return 'Lokasi Umum';
    return areaStr.replace(/_/g, ' ').toUpperCase();
  }

  function formatRole(roleStr) {
    if (!roleStr || roleStr === 'other' || roleStr === 'unspecified') return 'TECHNICAL ROLE';
    if (roleStr === 'infra_network') return 'INFRA / DEVOPS';
    if (roleStr === 'product_engineer') return 'PRODUCT ENGINEER';
    return roleStr.replace(/_/g, ' ').toUpperCase();
  }

  function formatExp(job) {
    if (job.experience_raw) return job.experience_raw;
    if (job.experience_level === 'entry') return '0-2 Tahun / Entry';
    if (job.experience_level === 'mid') return 'Min 1-2 Tahun';
    if (job.experience_level === 'senior') return '>3 Tahun / Senior';
    return 'Pengalaman Fleksibel';
  }

  function resetAllFilters() {
    selectedArea = 'all';
    selectedRole = 'all';
    selectedExperience = 'all';
    selectedSource = 'all';
    selectedCompany = 'all';
    onlyNew = false;
    searchQuery = '';
    loadJobs();
  }

  onMount(() => {
    loadJobs();
    loadCompanies();
    loadSearches();
    loadRuns();
  });
</script>

<div class="min-h-screen bg-[var(--color-page)] flex flex-col text-[var(--color-text-body)]">
  <!-- Top Navbar (Strict Monochrome) -->
  <header class="sticky top-0 z-40 bg-[var(--color-page)]/95 backdrop-blur-md border-b border-[var(--color-border-subtle)] px-4 sm:px-6 py-2.5">
    <div class="max-w-[1880px] mx-auto flex flex-col md:flex-row md:items-center md:justify-between gap-3">
      <!-- Brand & Status -->
      <div class="flex items-center gap-3">
        <a href="/" class="flex items-center gap-2 group text-decoration-none">
          <span class="w-7 h-7 rounded-full bg-black text-white flex items-center justify-center font-bold text-xs shadow-xs transition group-hover:scale-105">
            <Icon name="briefcase" size={14} />
          </span>
          <span class="text-lg font-bold tracking-tight text-black">
            kerjo
          </span>
        </a>

        <div class="h-4 w-[1px] bg-neutral-300 hidden sm:block"></div>

        <div class="hidden sm:flex items-center gap-2">
          <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-mono border border-neutral-300 bg-neutral-100 text-black">
            <span class="w-1.5 h-1.5 rounded-full bg-black"></span>
            Cronjob Tiap Jam Aktif
          </span>
          <span class="text-xs text-neutral-500 font-mono hidden xl:inline">
            Jabodetabek & BSD / Alsut
          </span>
        </div>
      </div>

      <!-- Action Controls -->
      <div class="flex items-center gap-2">
        <button
          onclick={markAllSeen}
          class="control-pill px-3 py-1.5 text-xs text-neutral-700 hover:text-black flex items-center gap-1.5 cursor-pointer"
          title="Tandai semua lowongan sebagai sudah dilihat"
        >
          <Icon name="checkCircle" size={13} />
          <span>Tandai Dilihat</span>
        </button>

        <button
          onclick={() => (showAddSearch = true)}
          class="control-pill px-3 py-1.5 text-xs text-neutral-700 hover:text-black flex items-center gap-1.5 cursor-pointer"
        >
          <Icon name="plus" size={13} />
          <span>Simpan Posisi</span>
        </button>

        <button
          onclick={triggerRun}
          disabled={runningScraper}
          class="control-pill control-pill-active px-3.5 py-1.5 text-xs font-medium flex items-center gap-1.5 cursor-pointer disabled:opacity-60"
        >
          {#if runningScraper}
            <span class="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
            <span>Scraping...</span>
          {:else}
            <Icon name="refresh" size={13} />
            <span>Scrape Sekarang</span>
          {/if}
        </button>
      </div>
    </div>
  </header>

  <!-- 3-Column Layout: Sidebar Filter : Main Component : Sidebar Detail -->
  <!-- Composition: 1:5 default, 1:4:1 when card detail open -->
  <div class="max-w-[1880px] w-full mx-auto px-3 sm:px-5 py-3 flex-1">
    <div class="grid grid-cols-1 lg:grid-cols-6 gap-3.5 items-start">

      <!-- ========================================== -->
      <!-- COLUMN 1: SIDEBAR FILTER (1 part)          -->
      <!-- Sticky, No outer section padding           -->
      <!-- ========================================== -->
      <aside class="lg:col-span-1 sticky top-16 max-h-[calc(100vh-4.75rem)] overflow-y-auto space-y-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3 shadow-xs">
        <!-- Filter Header -->
        <div class="flex items-center justify-between pb-2 border-b border-[var(--color-border-subtle)]">
          <div class="flex items-center gap-1.5 text-xs font-bold text-black">
            <Icon name="filter" size={13} />
            <span>Filter</span>
          </div>
          {#if selectedRole !== 'all' || selectedExperience !== 'all' || selectedArea !== 'all' || selectedSource !== 'all' || selectedCompany !== 'all' || onlyNew || searchQuery}
            <button
              onclick={resetAllFilters}
              class="text-[10px] text-neutral-500 hover:text-black cursor-pointer font-medium"
            >
              Reset Semua
            </button>
          {/if}
        </div>

        <!-- Section: Role Category (flush, no outer padding) -->
        <div class="space-y-1">
          <span class="block text-[10px] font-mono uppercase tracking-wider text-neutral-500">
            Kategori Role
          </span>
          <div class="space-y-0.5">
            {#each roleCategories as r}
              <button
                onclick={() => { selectedRole = r.id; loadJobs(); }}
                class="w-full text-left px-2 py-1 rounded-md text-xs transition flex items-center justify-between cursor-pointer {selectedRole === r.id ? 'bg-black text-white font-semibold' : 'text-neutral-700 hover:bg-neutral-200/60'}"
              >
                <span>{r.label}</span>
                {#if selectedRole === r.id}
                  <Icon name="check" size={11} />
                {/if}
              </button>
            {/each}
          </div>
        </div>

        <!-- Section: Experience Level (flush) -->
        <div class="space-y-1 pt-2.5 border-t border-[var(--color-border-subtle)]">
          <span class="block text-[10px] font-mono uppercase tracking-wider text-neutral-500">
            Pengalaman
          </span>
          <div class="space-y-0.5">
            {#each experienceLevels as exp}
              <button
                onclick={() => { selectedExperience = exp.id; loadJobs(); }}
                class="w-full text-left px-2 py-1 rounded-md text-xs transition flex items-center justify-between cursor-pointer {selectedExperience === exp.id ? 'bg-black text-white font-semibold' : 'text-neutral-700 hover:bg-neutral-200/60'}"
              >
                <span>{exp.label}</span>
                {#if selectedExperience === exp.id}
                  <Icon name="check" size={11} />
                {/if}
              </button>
            {/each}
          </div>
        </div>

        <!-- Section: Filter by Company Across Aggregators (flush) -->
        <div class="space-y-1 pt-2.5 border-t border-[var(--color-border-subtle)]">
          <div class="flex items-center justify-between">
            <label for="filter-company-select" class="block text-[10px] font-mono uppercase tracking-wider text-neutral-500">
              Perusahaan ({companies.length})
            </label>
            {#if selectedCompany !== 'all'}
              <button
                onclick={() => { selectedCompany = 'all'; loadJobs(); }}
                class="text-[10px] text-neutral-500 hover:text-black cursor-pointer font-medium"
              >
                Reset
              </button>
            {/if}
          </div>
          <select
            id="filter-company-select"
            bind:value={selectedCompany}
            onchange={loadJobs}
            class="w-full text-xs px-2 py-1.5 rounded-lg bg-white border border-[var(--color-border)] text-black focus:outline-none focus:ring-1 focus:ring-black cursor-pointer"
          >
            <option value="all">Semua Perusahaan</option>
            {#each companies as c}
              <option value={c.company}>{c.company} ({c.job_count})</option>
            {/each}
          </select>
        </div>

        <!-- Section: Area (flush) -->
        <div class="space-y-1 pt-2.5 border-t border-[var(--color-border-subtle)]">
          <label for="filter-area-select" class="block text-[10px] font-mono uppercase tracking-wider text-neutral-500">
            Area Lokasi
          </label>
          <select
            id="filter-area-select"
            bind:value={selectedArea}
            onchange={loadJobs}
            class="w-full text-xs px-2 py-1.5 rounded-lg bg-white border border-[var(--color-border)] text-black focus:outline-none focus:ring-1 focus:ring-black cursor-pointer"
          >
            {#each areas as a}
              <option value={a.id}>{a.label}</option>
            {/each}
          </select>
        </div>

        <!-- Section: Platform Portal (flush) -->
        <div class="space-y-1 pt-2.5 border-t border-[var(--color-border-subtle)]">
          <label for="filter-source-select" class="block text-[10px] font-mono uppercase tracking-wider text-neutral-500">
            Platform Portal
          </label>
          <select
            id="filter-source-select"
            bind:value={selectedSource}
            onchange={loadJobs}
            class="w-full text-xs px-2 py-1.5 rounded-lg bg-white border border-[var(--color-border)] text-black focus:outline-none focus:ring-1 focus:ring-black cursor-pointer"
          >
            {#each platforms as p}
              <option value={p.id}>{p.label}</option>
            {/each}
          </select>
        </div>

        <!-- Section: Only NEW (flush) -->
        <div class="pt-2.5 border-t border-[var(--color-border-subtle)]">
          <button
            onclick={() => { onlyNew = !onlyNew; loadJobs(); }}
            class="w-full ui-chip justify-between {onlyNew ? 'ui-chip-active' : ''}"
          >
            <span class="flex items-center gap-1.5">
              <span class="w-1.5 h-1.5 rounded-full {onlyNew ? 'bg-white' : 'bg-black'}"></span>
              <span>Hanya Baru (NEW)</span>
            </span>
            {#if onlyNew}
              <Icon name="check" size={11} />
            {/if}
          </button>
        </div>

        <!-- Section: Auto-Search Widget (flush) -->
        <div class="pt-2.5 border-t border-[var(--color-border-subtle)] space-y-1.5">
          <div class="flex items-center justify-between">
            <span class="text-[10px] font-mono uppercase tracking-wider text-neutral-500">
              Auto-Search ({searches.length})
            </span>
            <button
              onclick={() => (showAddSearch = true)}
              class="text-[11px] text-neutral-600 hover:text-black cursor-pointer p-0.5"
              title="Tambah Posisi"
            >
              <Icon name="plus" size={12} />
            </button>
          </div>

          {#if searches.length === 0}
            <p class="text-[11px] text-neutral-500 leading-snug">
              Belum ada posisi tersimpan untuk cronjob tiap jam.
            </p>
          {:else}
            <div class="space-y-1 max-h-44 overflow-y-auto pr-0.5">
              {#each searches as s}
                <div class="flex items-center justify-between gap-1 text-xs px-2 py-1 rounded-md border border-[var(--color-border-subtle)] bg-white {s.is_active ? '' : 'opacity-40'}">
                  <button
                    onclick={() => toggleSearch(s.id)}
                    class="flex items-center gap-1.5 truncate text-left cursor-pointer flex-1"
                    title={s.is_active ? 'Status aktif. Klik untuk jeda' : 'Status dijeda. Klik untuk aktifkan'}
                  >
                    <span class="w-1.5 h-1.5 rounded-full shrink-0 {s.is_active ? 'bg-black' : 'bg-neutral-400'}"></span>
                    <span class="font-medium text-black truncate text-[11px]">{s.keyword}</span>
                  </button>
                  <button
                    onclick={() => deleteSearch(s.id)}
                    class="text-neutral-400 hover:text-black cursor-pointer p-0.5 shrink-0"
                    title="Hapus"
                  >
                    <Icon name="trash" size={11} />
                  </button>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      </aside>

      <!-- ======================================================== -->
      <!-- COLUMN 2: MAIN COMPONENT (5 parts default, 4 when open)  -->
      <!-- Card Grid fits 4 cards across on desktop viewports       -->
      <!-- ======================================================== -->
      <main class="{activeJob ? 'lg:col-span-4' : 'lg:col-span-5'} space-y-3">
        <!-- Top Search Bar & Counter -->
        <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5 bg-[var(--color-surface)] p-2 rounded-xl border border-[var(--color-border-subtle)]">
          <div class="relative flex-1">
            <span class="absolute left-3 top-2 text-neutral-400">
              <Icon name="search" size={14} />
            </span>
            <input
              type="text"
              placeholder="Cari judul posisi, keahlian, teknologi, atau perusahaan..."
              bind:value={searchQuery}
              oninput={loadJobs}
              class="w-full text-xs pl-8 pr-8 py-1.5 rounded-lg bg-white border border-[var(--color-border-subtle)] text-black placeholder-neutral-400 focus:outline-none focus:ring-1 focus:ring-black"
            />
            {#if searchQuery}
              <button
                onclick={() => { searchQuery = ''; loadJobs(); }}
                class="absolute right-2.5 top-2 text-neutral-400 hover:text-black cursor-pointer"
              >
                <Icon name="x" size={12} />
              </button>
            {/if}
          </div>

          <div class="flex items-center gap-2 px-2 text-xs text-neutral-600">
            {#if loading}
              <span class="flex items-center gap-1.5 text-neutral-500">
                <span class="w-3 h-3 border-2 border-neutral-400 border-t-black rounded-full animate-spin"></span>
                Memperbarui...
              </span>
            {:else}
              <span class="font-mono text-[11px]">
                <strong class="text-black">{jobs.length}</strong> lowongan ditemukan
              </span>
            {/if}
          </div>
        </div>

        <!-- Active Filter Pills Bar (Strict Monochrome) -->
        {#if selectedRole !== 'all' || selectedExperience !== 'all' || selectedArea !== 'all' || selectedSource !== 'all' || selectedCompany !== 'all' || onlyNew}
          <div class="flex flex-wrap items-center gap-1.5 text-xs">
            <span class="text-[11px] font-mono text-neutral-500">Aktif:</span>
            {#if selectedRole !== 'all'}
              <span class="ui-chip ui-chip-active text-[11px] gap-1">
                Role: {selectedRole}
                <button onclick={() => { selectedRole = 'all'; loadJobs(); }} class="cursor-pointer ml-0.5"><Icon name="x" size={10} /></button>
              </span>
            {/if}
            {#if selectedExperience !== 'all'}
              <span class="ui-chip ui-chip-active text-[11px] gap-1">
                Exp: {selectedExperience}
                <button onclick={() => { selectedExperience = 'all'; loadJobs(); }} class="cursor-pointer ml-0.5"><Icon name="x" size={10} /></button>
              </span>
            {/if}
            {#if selectedCompany !== 'all'}
              <span class="ui-chip ui-chip-active text-[11px] gap-1">
                PT: {selectedCompany}
                <button onclick={() => { selectedCompany = 'all'; loadJobs(); }} class="cursor-pointer ml-0.5"><Icon name="x" size={10} /></button>
              </span>
            {/if}
            {#if selectedArea !== 'all'}
              <span class="ui-chip ui-chip-active text-[11px] gap-1">
                Area: {selectedArea}
                <button onclick={() => { selectedArea = 'all'; loadJobs(); }} class="cursor-pointer ml-0.5"><Icon name="x" size={10} /></button>
              </span>
            {/if}
            {#if selectedSource !== 'all'}
              <span class="ui-chip ui-chip-active text-[11px] gap-1">
                Platform: {selectedSource}
                <button onclick={() => { selectedSource = 'all'; loadJobs(); }} class="cursor-pointer ml-0.5"><Icon name="x" size={10} /></button>
              </span>
            {/if}
            {#if onlyNew}
              <span class="ui-chip ui-chip-active text-[11px] gap-1">
                Baru Saja
                <button onclick={() => { onlyNew = false; loadJobs(); }} class="cursor-pointer ml-0.5"><Icon name="x" size={10} /></button>
              </span>
            {/if}
          </div>
        {/if}

        <!-- Empty State -->
        {#if jobs.length === 0 && !loading}
          <div class="text-center py-16 px-4 bg-[var(--color-surface)] rounded-xl border border-[var(--color-border-subtle)] space-y-2">
            <div class="w-10 h-10 rounded-full bg-white border border-neutral-300 mx-auto flex items-center justify-center text-neutral-500">
              <Icon name="search" size={18} />
            </div>
            <p class="text-sm font-semibold text-black">Tidak ada lowongan yang sesuai kriteria.</p>
            <p class="text-xs text-neutral-500 max-w-sm mx-auto">
              Coba perluas filter role, perusahaan, atau level pengalaman, atau klik "Scrape Sekarang".
            </p>
          </div>
        {:else}
          <!-- Card Feed Grid: Configured to fit 4 cards across on desktop viewports -->
          <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-2 lg:grid-cols-3 {activeJob ? 'xl:grid-cols-3 2xl:grid-cols-4' : 'xl:grid-cols-4 2xl:grid-cols-4'} gap-2.5">
            {#each jobs as j}
              <div
                role="button"
                tabindex="0"
                onclick={() => selectJob(j)}
                onkeydown={(e) => e.key === 'Enter' && selectJob(j)}
                class="text-left bg-white rounded-xl p-3 border transition duration-150 flex flex-col justify-between cursor-pointer group hover:border-black hover:shadow-xs {activeJob && activeJob.id === j.id ? 'border-black ring-2 ring-black/20 bg-neutral-50' : (j.is_new ? 'border-black/40 bg-neutral-50/50' : 'border-[var(--color-border-subtle)]')}"
              >
                <div class="space-y-2">
                  <!-- Header: Company Logo + Title/Company + Badges -->
                  <div class="flex items-start gap-2.5">
                    <!-- Company Logo thumbnail with letter avatar fallback -->
                    <div class="w-9 h-9 rounded-lg border border-neutral-200 bg-white p-0.5 flex items-center justify-center shrink-0 overflow-hidden shadow-2xs">
                      {#if j.company_logo}
                        <img
                          src={j.company_logo}
                          alt={j.company}
                          class="w-full h-full object-contain"
                          onerror={(e) => { e.currentTarget.style.display = 'none'; if (e.currentTarget.nextElementSibling) e.currentTarget.nextElementSibling.style.display = 'flex'; }}
                        />
                        <span class="w-full h-full bg-neutral-100 text-black font-mono font-bold text-xs items-center justify-center hidden">
                          {j.company ? j.company.charAt(0).toUpperCase() : 'J'}
                        </span>
                      {:else}
                        <span class="w-full h-full bg-neutral-100 text-black font-mono font-bold text-xs flex items-center justify-center">
                          {j.company ? j.company.charAt(0).toUpperCase() : 'J'}
                        </span>
                      {/if}
                    </div>

                    <!-- Title & Company name -->
                    <div class="min-w-0 flex-1">
                      <h3 class="text-xs font-bold text-black line-clamp-2 leading-snug group-hover:underline">
                        {j.title}
                      </h3>
                      <!-- Clickable company name filters across aggregators -->
                      <button
                        type="button"
                        onclick={(e) => { e.stopPropagation(); filterByCompany(j.company); }}
                        class="text-[11px] text-neutral-600 hover:text-black hover:underline truncate text-left cursor-pointer font-medium block max-w-full mt-0.5"
                        title="Filter hanya perusahaan ini"
                      >
                        {j.company}
                      </button>
                    </div>

                    <!-- NEW badge if applicable -->
                    {#if j.is_new}
                      <span class="shrink-0 px-1.5 py-0.5 rounded bg-black text-white text-[9px] font-mono font-bold">
                        NEW
                      </span>
                    {/if}
                  </div>

                  <!-- Metadata Badges row -->
                  <div class="flex flex-wrap items-center gap-1 text-[10px] font-mono">
                    <!-- Source badge -->
                    {#if j.sources && j.sources.length > 1}
                      <span class="px-1.5 py-0.5 rounded bg-neutral-100 text-black border border-neutral-300 font-semibold">
                        {j.sources.length} SITUS
                      </span>
                    {:else}
                      <span class="px-1.5 py-0.5 rounded bg-neutral-100 text-neutral-700 border border-neutral-200 uppercase">
                        {j.source || 'PORTAL'}
                      </span>
                    {/if}

                    <!-- Role Category badge -->
                    <span class="px-1.5 py-0.5 rounded bg-neutral-100 text-neutral-800 border border-neutral-200">
                      {formatRole(j.role_category)}
                    </span>

                    <!-- Experience Bracket badge -->
                    {#if j.experience_level && j.experience_level !== 'unspecified'}
                      <span class="px-1.5 py-0.5 rounded bg-black text-white font-medium">
                        {j.experience_level.toUpperCase()}
                      </span>
                    {/if}
                  </div>

                  <!-- Experience requirement snippet -->
                  <div class="text-[11px] text-neutral-600 font-mono truncate flex items-center gap-1">
                    <Icon name="briefcase" size={11} class="text-neutral-400 shrink-0" />
                    <span class="truncate">{formatExp(j)}</span>
                  </div>

                  <!-- Location & Salary -->
                  <div class="flex items-center justify-between text-[11px] text-neutral-500 pt-0.5">
                    <span class="flex items-center gap-1 truncate max-w-[60%]">
                      <Icon name="mapPin" size={11} class="shrink-0 text-neutral-400" />
                      <span class="truncate">{formatArea(j.area)}</span>
                    </span>

                    {#if j.salary}
                      <span class="text-black font-semibold font-mono text-[10px] truncate">
                        {j.salary}
                      </span>
                    {/if}
                  </div>
                </div>

                <!-- Footer Card -->
                <div class="mt-2.5 pt-2 border-t border-[var(--color-border-subtle)] flex items-center justify-between text-[11px] text-neutral-500">
                  <span class="font-mono flex items-center gap-1 text-[10px]">
                    <Icon name="clock" size={11} />
                    {formatTime(j.posted_at || j.first_seen_at)}
                  </span>

                  <span class="text-xs font-semibold text-neutral-700 group-hover:text-black flex items-center gap-0.5">
                    <span>Lihat</span>
                    <Icon name="arrowDownRight" size={11} />
                  </span>
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </main>

      <!-- ========================================================= -->
      <!-- COLUMN 3: SIDEBAR DETAIL (1 part, visible when card clicked) -->
      <!-- Sticky, No outer section padding                         -->
      <!-- ========================================================= -->
      {#if activeJob}
        <aside class="lg:col-span-1 sticky top-16 max-h-[calc(100vh-4.75rem)] overflow-y-auto space-y-3.5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3 shadow-xs">
          <!-- Top Close & Action header -->
          <div class="flex items-center justify-between pb-2 border-b border-[var(--color-border-subtle)]">
            <span class="text-xs font-mono uppercase tracking-wider text-neutral-500">
              Detail Loker
            </span>
            <div class="flex items-center gap-1.5">
              <a
                href={activeJob.url}
                target="_blank"
                rel="noopener noreferrer"
                class="control-pill px-2.5 py-1 text-[11px] font-mono flex items-center gap-1 text-black font-semibold"
                title="Buka Halaman Loker Asli"
              >
                <span>Buka</span>
                <Icon name="arrowUpRight" size={11} />
              </a>

              <button
                onclick={() => (activeJob = null)}
                class="p-1 rounded-md text-neutral-500 hover:text-black hover:bg-neutral-200/60 cursor-pointer"
                title="Tutup Detail"
              >
                <Icon name="x" size={14} />
              </button>
            </div>
          </div>

          <!-- Company Logo + Title + Company (flush) -->
          <div class="space-y-2">
            <div class="flex items-start gap-2.5">
              <!-- Detail Company Logo -->
              <div class="w-11 h-11 rounded-lg border border-neutral-300 bg-white p-0.5 flex items-center justify-center shrink-0 overflow-hidden shadow-2xs">
                {#if activeJob.company_logo}
                  <img
                    src={activeJob.company_logo}
                    alt={activeJob.company}
                    class="w-full h-full object-contain"
                    onerror={(e) => { e.currentTarget.style.display = 'none'; if (e.currentTarget.nextElementSibling) e.currentTarget.nextElementSibling.style.display = 'flex'; }}
                  />
                  <span class="w-full h-full bg-neutral-100 text-black font-mono font-bold text-sm items-center justify-center hidden">
                    {activeJob.company ? activeJob.company.charAt(0).toUpperCase() : 'J'}
                  </span>
                {:else}
                  <span class="w-full h-full bg-neutral-100 text-black font-mono font-bold text-sm flex items-center justify-center">
                    {activeJob.company ? activeJob.company.charAt(0).toUpperCase() : 'J'}
                  </span>
                {/if}
              </div>

              <div class="min-w-0 flex-1">
                <h2 class="text-xs font-bold text-black leading-snug">
                  {activeJob.title}
                </h2>
                <!-- Clickable company filter in detail -->
                <button
                  type="button"
                  onclick={() => filterByCompany(activeJob.company)}
                  class="text-xs text-neutral-600 hover:text-black hover:underline font-semibold mt-0.5 text-left truncate block max-w-full cursor-pointer"
                  title="Filter hanya perusahaan ini"
                >
                  {activeJob.company}
                </button>
              </div>
            </div>

            <div class="text-xs text-neutral-600 space-y-1 pt-1 font-mono">
              <p class="flex items-center gap-1.5">
                <Icon name="mapPin" size={12} class="text-neutral-400 shrink-0" />
                <span class="truncate">{activeJob.location_raw || formatArea(activeJob.area)}</span>
              </p>
              {#if activeJob.salary}
                <p class="flex items-center gap-1.5 font-bold text-black">
                  <Icon name="banknote" size={12} class="text-neutral-400 shrink-0" />
                  <span>{activeJob.salary}</span>
                </p>
              {/if}
            </div>
          </div>

          <!-- Role & Experience Spec (flush, no outer padding) -->
          <div class="space-y-1.5 pt-2.5 border-t border-[var(--color-border-subtle)]">
            <div class="text-[10px] font-mono uppercase tracking-wider text-neutral-500">
              Klasifikasi Sistem
            </div>
            <div class="space-y-1 text-xs">
              <div class="flex items-center justify-between">
                <span class="text-neutral-500">Kategori:</span>
                <span class="font-bold text-black">{formatRole(activeJob.role_category)}</span>
              </div>
              <div class="flex items-center justify-between">
                <span class="text-neutral-500">Level:</span>
                <span class="font-bold text-black">{activeJob.experience_level ? activeJob.experience_level.toUpperCase() : 'FLEKSIBEL'}</span>
              </div>
              {#if activeJob.min_years !== null || activeJob.max_years !== null}
                <div class="flex items-center justify-between text-[11px] font-mono">
                  <span class="text-neutral-500">Rentang:</span>
                  <span class="text-black font-semibold">
                    {activeJob.min_years !== null ? activeJob.min_years : 0} - {activeJob.max_years !== null ? activeJob.max_years : '+'} th
                  </span>
                </div>
              {/if}
              {#if activeJob.experience_raw}
                <div class="pt-1 text-[10px] font-mono text-neutral-500">
                  Kutipan: "{activeJob.experience_raw}"
                </div>
              {/if}
            </div>
          </div>

          <!-- Timeline Section (flush) -->
          <div class="space-y-1.5 pt-2.5 border-t border-[var(--color-border-subtle)]">
            <div class="text-[10px] font-mono uppercase tracking-wider text-neutral-500">
              Timeline Loker
            </div>
            <Timeline job={activeJob} />
          </div>

          <!-- Description Section (flush) -->
          <div class="space-y-1.5 pt-2.5 border-t border-[var(--color-border-subtle)]">
            <div class="text-[10px] font-mono uppercase tracking-wider text-neutral-500">
              Deskripsi Pekerjaan
            </div>
            {#if activeJob.description && activeJob.description.trim()}
              <div class="text-xs text-neutral-700 whitespace-pre-wrap leading-relaxed max-h-52 overflow-y-auto pr-1 border border-[var(--color-border-subtle)] bg-white p-2 rounded-lg font-sans">
                {activeJob.description}
              </div>
            {:else}
              <p class="text-xs text-neutral-400 italic bg-white p-2.5 rounded-lg border border-[var(--color-border-subtle)]">
                Deskripsi lengkap tersedia langsung di portal perekrut.
              </p>
            {/if}
          </div>

          <!-- Direct Apply / Platform Links (flush) -->
          <div class="pt-2.5 border-t border-[var(--color-border-subtle)] space-y-1.5">
            {#if activeJob.sources && activeJob.sources.length > 1 && activeJob.urls}
              <div class="space-y-1">
                <span class="text-[10px] font-mono text-neutral-500">Tersedia di {activeJob.sources.length} portal:</span>
                <div class="grid grid-cols-2 gap-1.5 pt-0.5">
                  {#each activeJob.sources as src}
                    <a
                      href={activeJob.urls[src]}
                      target="_blank"
                      rel="noopener noreferrer"
                      class="control-pill px-2 py-1 text-xs text-center truncate capitalize text-black font-semibold"
                    >
                      {src} ↗
                    </a>
                  {/each}
                </div>
              </div>
            {:else}
              <a
                href={activeJob.url}
                target="_blank"
                rel="noopener noreferrer"
                class="control-pill control-pill-active w-full py-2 text-xs font-bold flex items-center justify-center gap-1.5 cursor-pointer text-decoration-none"
              >
                <span>Buka di {activeJob.source ? activeJob.source.toUpperCase() : 'Portal'}</span>
                <Icon name="arrowUpRight" size={13} />
              </a>
            {/if}
          </div>
        </aside>
      {/if}

    </div>
  </div>

  <!-- Add Saved Search Modal (Strict Monochrome) -->
  {#if showAddSearch}
    <div class="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
      <div class="bg-white rounded-2xl max-w-md w-full p-5 shadow-2xl border border-[var(--color-border)] space-y-4">
        <div class="flex items-center justify-between pb-3 border-b border-[var(--color-border-subtle)]">
          <div class="flex items-center gap-2">
            <span class="w-6 h-6 rounded-full bg-black text-white flex items-center justify-center">
              <Icon name="plus" size={13} />
            </span>
            <h3 class="text-sm font-bold text-black">
              Simpan Pencarian Otomatis
            </h3>
          </div>
          <button
            onclick={() => (showAddSearch = false)}
            class="text-neutral-500 hover:text-black cursor-pointer p-1"
          >
            <Icon name="x" size={15} />
          </button>
        </div>

        <form onsubmit={submitNewSearch} class="space-y-3.5">
          <div>
            <label for="kw-input" class="block text-xs font-mono uppercase tracking-wider text-neutral-600 mb-1">
              Kata Kunci Posisi / Skill
            </label>
            <input
              id="kw-input"
              type="text"
              required
              placeholder="e.g. Junior Backend Engineer, Golang, React"
              bind:value={newKeyword}
              class="w-full text-xs px-3 py-2 rounded-lg border border-[var(--color-border)] bg-white text-black focus:outline-none focus:ring-1 focus:ring-black"
            />
          </div>

          <div>
            <label for="area-select" class="block text-xs font-mono uppercase tracking-wider text-neutral-600 mb-1">
              Target Area
            </label>
            <select
              id="area-select"
              bind:value={newArea}
              class="w-full text-xs px-3 py-2 rounded-lg border border-[var(--color-border)] bg-white text-black focus:outline-none focus:ring-1 focus:ring-black"
            >
              {#each areas as a}
                <option value={a.id}>{a.label}</option>
              {/each}
            </select>
          </div>

          <div>
            <span class="block text-xs font-mono uppercase tracking-wider text-neutral-600 mb-1.5">
              Sumber Platform Tiap Jam
            </span>
            <div class="grid grid-cols-2 gap-2 text-xs font-mono">
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" bind:checked={newSources.jobstreet} class="accent-black rounded" />
                JobStreet
              </label>
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" bind:checked={newSources.kalibrr} class="accent-black rounded" />
                Kalibrr
              </label>
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" bind:checked={newSources.linkedin} class="accent-black rounded" />
                LinkedIn
              </label>
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" bind:checked={newSources.glints} class="accent-black rounded" />
                Glints
              </label>
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" bind:checked={newSources.dealls} class="accent-black rounded" />
                Dealls
              </label>
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" bind:checked={newSources.karir} class="accent-black rounded" />
                Karir.com
              </label>
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" bind:checked={newSources.techinasia} class="accent-black rounded" />
                Tech in Asia
              </label>
            </div>
          </div>

          <div class="pt-3 border-t border-[var(--color-border-subtle)] flex justify-end gap-2">
            <button
              type="button"
              onclick={() => (showAddSearch = false)}
              class="control-pill px-3 py-1.5 text-xs text-neutral-600 hover:text-black cursor-pointer"
            >
              Batal
            </button>
            <button
              type="submit"
              class="control-pill control-pill-active px-4 py-1.5 text-xs font-bold cursor-pointer"
            >
              Simpan Pencarian
            </button>
          </div>
        </form>
      </div>
    </div>
  {/if}
</div>
