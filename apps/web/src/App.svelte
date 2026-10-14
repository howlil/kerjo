<script>
  import { onMount } from 'svelte';
  import Icon from './components/Icon.svelte';
  import Timeline from './components/Timeline.svelte';

  // Core State
  let jobs = $state([]);
  let searches = $state([]);
  let latestRuns = $state([]);
  let loading = $state(false);
  let runningScraper = $state(false);
  let activeJob = $state(null);

  // Filters State
  let selectedArea = $state('all');
  let selectedRole = $state('all');
  let selectedExperience = $state('all');
  let selectedSource = $state('all');
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
      if (onlyNew) params.set('is_new', '1');
      if (searchQuery.trim()) params.set('q', searchQuery.trim());
      params.set('limit', '250');

      const res = await fetch(`/api/jobs?${params.toString()}`);
      const data = await res.json();
      jobs = data.jobs || [];

      // Update activeJob reference if still in the list
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
    if (!roleStr || roleStr === 'other' || roleStr === 'unspecified') return 'Technical Role';
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
    onlyNew = false;
    searchQuery = '';
    loadJobs();
  }

  onMount(() => {
    loadJobs();
    loadSearches();
    loadRuns();
  });
</script>

<div class="min-h-screen bg-[var(--color-page)] flex flex-col text-[var(--color-text-body)]">
  <!-- Top Navbar -->
  <header class="sticky top-0 z-40 bg-[var(--color-page)]/95 backdrop-blur-md border-b border-[var(--color-border-subtle)] px-4 sm:px-6 py-3">
    <div class="max-w-[1800px] mx-auto flex flex-col md:flex-row md:items-center md:justify-between gap-3">
      <!-- Brand & Status -->
      <div class="flex items-center gap-3">
        <a href="/" class="flex items-center gap-2 group text-decoration-none">
          <span class="w-8 h-8 rounded-full bg-[var(--color-accent)] text-[#121212] flex items-center justify-center font-bold text-sm shadow-xs transition group-hover:scale-105">
            <Icon name="briefcase" size={16} />
          </span>
          <span class="text-xl font-bold tracking-tight text-[var(--color-text-heading)]">
            kerjo
          </span>
        </a>

        <div class="h-4 w-[1px] bg-[var(--color-border)] hidden sm:block"></div>

        <div class="hidden sm:flex items-center gap-2">
          <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono border border-[#ACE1AF]/60 bg-[#ACE1AF]/15 text-[#121212]">
            <span class="w-2 h-2 rounded-full bg-[#ACE1AF] animate-pulse"></span>
            Cronjob Tiap Jam Aktif
          </span>
          <span class="text-xs text-[var(--color-text-muted)] font-mono hidden xl:inline">
            Jabodetabek & BSD / Alsut
          </span>
        </div>
      </div>

      <!-- Action Controls -->
      <div class="flex items-center gap-2">
        <button
          onclick={markAllSeen}
          class="control-pill px-3 py-1.5 text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text-heading)] flex items-center gap-1.5 cursor-pointer"
          title="Tandai semua lowongan sebagai sudah dilihat"
        >
          <Icon name="checkCircle" size={13} />
          <span>Tandai Dilihat</span>
        </button>

        <button
          onclick={() => (showAddSearch = true)}
          class="control-pill px-3 py-1.5 text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text-heading)] flex items-center gap-1.5 cursor-pointer"
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
            <span class="w-3 h-3 border-2 border-[#121212]/30 border-t-[#121212] rounded-full animate-spin"></span>
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
  <!-- Ratio: 1:5 (when no card selected), 1:4:1 (when card clicked) -->
  <div class="max-w-[1800px] w-full mx-auto px-4 sm:px-6 py-4 flex-1">
    <div class="grid grid-cols-1 lg:grid-cols-6 gap-5 items-start">

      <!-- ========================================== -->
      <!-- COLUMN 1: SIDEBAR FILTER (1 part)          -->
      <!-- ========================================== -->
      <aside class="lg:col-span-1 space-y-5 bg-[var(--color-surface)] p-4 rounded-2xl border border-[var(--color-border-subtle)]">
        <div class="flex items-center justify-between pb-2 border-b border-[var(--color-border-subtle)]">
          <div class="flex items-center gap-1.5 text-xs font-semibold text-[var(--color-text-heading)]">
            <Icon name="filter" size={14} />
            <span>Filter Pencarian</span>
          </div>
          {#if selectedRole !== 'all' || selectedExperience !== 'all' || selectedArea !== 'all' || selectedSource !== 'all' || onlyNew || searchQuery}
            <button
              onclick={resetAllFilters}
              class="text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-text-heading)] cursor-pointer flex items-center gap-0.5"
            >
              Reset
            </button>
          {/if}
        </div>

        <!-- Filter: Role Category -->
        <div class="space-y-1.5">
          <span class="block text-[11px] font-mono uppercase tracking-wider text-[var(--color-text-muted)]">
            Kategori Role
          </span>
          <div class="space-y-1">
            {#each roleCategories as r}
              <button
                onclick={() => { selectedRole = r.id; loadJobs(); }}
                class="w-full text-left px-2.5 py-1.5 rounded-full text-xs transition flex items-center justify-between cursor-pointer {selectedRole === r.id ? 'bg-[var(--color-accent)] text-[#121212] font-semibold shadow-2xs' : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]'}"
              >
                <span>{r.label}</span>
                {#if selectedRole === r.id}
                  <Icon name="check" size={12} />
                {/if}
              </button>
            {/each}
          </div>
        </div>

        <!-- Filter: Experience Bracket -->
        <div class="space-y-1.5 pt-2 border-t border-[var(--color-border-subtle)]">
          <span class="block text-[11px] font-mono uppercase tracking-wider text-[var(--color-text-muted)]">
            Pengalaman
          </span>
          <div class="space-y-1">
            {#each experienceLevels as exp}
              <button
                onclick={() => { selectedExperience = exp.id; loadJobs(); }}
                class="w-full text-left px-2.5 py-1.5 rounded-full text-xs transition flex items-center justify-between cursor-pointer {selectedExperience === exp.id ? 'bg-[var(--color-accent)] text-[#121212] font-semibold shadow-2xs' : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]'}"
              >
                <span>{exp.label}</span>
                {#if selectedExperience === exp.id}
                  <Icon name="check" size={12} />
                {/if}
              </button>
            {/each}
          </div>
        </div>

        <!-- Filter: Area -->
        <div class="space-y-1.5 pt-2 border-t border-[var(--color-border-subtle)]">
          <label for="filter-area-select" class="block text-[11px] font-mono uppercase tracking-wider text-[var(--color-text-muted)]">
            Area Lokasi
          </label>
          <select
            id="filter-area-select"
            bind:value={selectedArea}
            onchange={loadJobs}
            class="w-full text-xs px-2.5 py-2 rounded-xl bg-[var(--color-page)] border border-[var(--color-border)] text-[var(--color-text-heading)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)] cursor-pointer"
          >
            {#each areas as a}
              <option value={a.id}>{a.label}</option>
            {/each}
          </select>
        </div>

        <!-- Filter: Source Platform -->
        <div class="space-y-1.5 pt-2 border-t border-[var(--color-border-subtle)]">
          <label for="filter-source-select" class="block text-[11px] font-mono uppercase tracking-wider text-[var(--color-text-muted)]">
            Platform Portal
          </label>
          <select
            id="filter-source-select"
            bind:value={selectedSource}
            onchange={loadJobs}
            class="w-full text-xs px-2.5 py-2 rounded-xl bg-[var(--color-page)] border border-[var(--color-border)] text-[var(--color-text-heading)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)] cursor-pointer"
          >
            {#each platforms as p}
              <option value={p.id}>{p.label}</option>
            {/each}
          </select>
        </div>

        <!-- Filter: Only NEW -->
        <div class="pt-2 border-t border-[var(--color-border-subtle)]">
          <button
            onclick={() => { onlyNew = !onlyNew; loadJobs(); }}
            class="w-full ui-chip justify-between {onlyNew ? 'ui-chip-active' : ''}"
          >
            <span class="flex items-center gap-1.5">
              <span class="w-2 h-2 rounded-full {onlyNew ? 'bg-[#121212]' : 'bg-[#ACE1AF]'}"></span>
              <span>Hanya Baru (NEW)</span>
            </span>
            {#if onlyNew}
              <Icon name="check" size={12} />
            {/if}
          </button>
        </div>

        <!-- Saved Searches Widget -->
        <div class="pt-3 border-t border-[var(--color-border-subtle)] space-y-2">
          <div class="flex items-center justify-between">
            <span class="text-[11px] font-mono uppercase tracking-wider text-[var(--color-text-muted)]">
              Auto-Search ({searches.length})
            </span>
            <button
              onclick={() => (showAddSearch = true)}
              class="text-[11px] text-[var(--color-text-secondary)] hover:text-[var(--color-text-heading)] cursor-pointer"
              title="Tambah Posisi"
            >
              <Icon name="plus" size={12} />
            </button>
          </div>

          {#if searches.length === 0}
            <p class="text-[11px] text-[var(--color-text-muted)] leading-relaxed">
              Belum ada posisi tersimpan untuk cronjob tiap jam.
            </p>
          {:else}
            <div class="space-y-1.5 max-h-48 overflow-y-auto pr-1">
              {#each searches as s}
                <div class="flex items-center justify-between gap-1 text-xs px-2.5 py-1.5 rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-page)] {s.is_active ? '' : 'opacity-50'}">
                  <button
                    onclick={() => toggleSearch(s.id)}
                    class="flex items-center gap-1.5 truncate text-left cursor-pointer flex-1"
                    title={s.is_active ? 'Status aktif. Klik untuk jeda' : 'Status dijeda. Klik untuk aktifkan'}
                  >
                    <span class="w-1.5 h-1.5 rounded-full shrink-0 {s.is_active ? 'bg-[#ACE1AF]' : 'bg-[var(--color-border-strong)]'}"></span>
                    <span class="font-medium text-[var(--color-text-heading)] truncate text-[11px]">{s.keyword}</span>
                  </button>
                  <button
                    onclick={() => deleteSearch(s.id)}
                    class="text-[var(--color-text-muted)] hover:text-red-600 cursor-pointer p-0.5 shrink-0"
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
      <!-- ======================================================== -->
      <main class="{activeJob ? 'lg:col-span-4' : 'lg:col-span-5'} space-y-4">
        <!-- Top Search Bar & Counter -->
        <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-[var(--color-surface)] p-2.5 rounded-2xl border border-[var(--color-border-subtle)]">
          <div class="relative flex-1">
            <span class="absolute left-3 top-2.5 text-[var(--color-text-muted)]">
              <Icon name="search" size={14} />
            </span>
            <input
              type="text"
              placeholder="Cari judul posisi, keahlian, atau nama perusahaan..."
              bind:value={searchQuery}
              oninput={loadJobs}
              class="w-full text-xs pl-8 pr-8 py-2 rounded-xl bg-[var(--color-page)] border border-[var(--color-border-subtle)] text-[var(--color-text-heading)] placeholder-[var(--color-text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
            />
            {#if searchQuery}
              <button
                onclick={() => { searchQuery = ''; loadJobs(); }}
                class="absolute right-2.5 top-2.5 text-[var(--color-text-muted)] hover:text-[var(--color-text-heading)] cursor-pointer"
              >
                <Icon name="x" size={12} />
              </button>
            {/if}
          </div>

          <div class="flex items-center gap-2 px-2 text-xs text-[var(--color-text-secondary)]">
            {#if loading}
              <span class="flex items-center gap-1.5 text-[var(--color-text-muted)]">
                <span class="w-3 h-3 border-2 border-[var(--color-border-strong)] border-t-[var(--color-text-heading)] rounded-full animate-spin"></span>
                Memperbarui...
              </span>
            {:else}
              <span class="font-mono text-[11px]">
                <strong>{jobs.length}</strong> lowongan ditemukan
              </span>
            {/if}
          </div>
        </div>

        <!-- Active Filter Pills Bar (if any) -->
        {#if selectedRole !== 'all' || selectedExperience !== 'all' || selectedArea !== 'all' || selectedSource !== 'all' || onlyNew}
          <div class="flex flex-wrap items-center gap-1.5 text-xs">
            <span class="text-[11px] font-mono text-[var(--color-text-muted)]">Aktif:</span>
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
          <div class="text-center py-16 px-4 bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border-subtle)] space-y-2">
            <div class="w-10 h-10 rounded-full bg-[var(--color-page)] border border-[var(--color-border)] mx-auto flex items-center justify-center text-[var(--color-text-muted)]">
              <Icon name="search" size={18} />
            </div>
            <p class="text-sm font-semibold text-[var(--color-text-heading)]">Tidak ada lowongan yang sesuai kriteria.</p>
            <p class="text-xs text-[var(--color-text-secondary)] max-w-sm mx-auto">
              Coba perluas filter role atau level pengalaman, atau klik "Scrape Sekarang" untuk mengambil data terbaru.
            </p>
          </div>
        {:else}
          <!-- Card Feed Grid -->
          <!-- In 5-column mode: 3 cols; In 4-column mode: 2 cols -->
          <div class="grid grid-cols-1 md:grid-cols-2 {activeJob ? 'xl:grid-cols-2' : 'xl:grid-cols-3'} gap-3">
            {#each jobs as j}
              <div
                role="button"
                tabindex="0"
                onclick={() => selectJob(j)}
                onkeydown={(e) => e.key === 'Enter' && selectJob(j)}
                class="text-left bg-[var(--color-page)] rounded-2xl p-4 border transition duration-150 flex flex-col justify-between cursor-pointer group hover:border-[var(--color-border-strong)] hover:shadow-xs {activeJob && activeJob.id === j.id ? 'border-[var(--color-accent)] ring-2 ring-[var(--color-accent)]/40 bg-[var(--color-accent-soft)]/20' : (j.is_new ? 'border-[#FAFF7E] bg-[var(--color-surface)]/60' : 'border-[var(--color-border-subtle)]')}"
              >
                <div class="space-y-2.5">
                  <!-- Header badges -->
                  <div class="flex flex-wrap items-center gap-1.5 text-[10px] font-mono">
                    {#if j.is_new}
                      <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[var(--color-highlight)] text-[#121212] font-semibold border border-[var(--color-border)]">
                        <span class="w-1.5 h-1.5 rounded-full bg-[#121212]"></span>
                        NEW
                      </span>
                    {/if}

                    <!-- Source badge -->
                    {#if j.sources && j.sources.length > 1}
                      <span class="px-2 py-0.5 rounded-full bg-[var(--color-surface)] text-[var(--color-text-heading)] border border-[var(--color-border)] font-semibold">
                        {j.sources.length} SITUS
                      </span>
                    {:else}
                      <span class="px-2 py-0.5 rounded-full bg-[var(--color-surface)] text-[var(--color-text-secondary)] border border-[var(--color-border-subtle)] uppercase">
                        {j.source || 'PORTAL'}
                      </span>
                    {/if}

                    <!-- Role Category badge -->
                    <span class="px-2 py-0.5 rounded-full bg-[var(--color-surface-muted)] text-[var(--color-text-secondary)] border border-[var(--color-border-subtle)]">
                      {formatRole(j.role_category)}
                    </span>

                    <!-- Experience Bracket badge -->
                    {#if j.experience_level && j.experience_level !== 'unspecified'}
                      <span class="px-2 py-0.5 rounded-full bg-[var(--color-accent-soft)] text-[var(--color-on-accent)] border border-[var(--color-accent)]">
                        {j.experience_level.toUpperCase()}
                      </span>
                    {/if}
                  </div>

                  <!-- Title & Company -->
                  <div>
                    <h3 class="text-sm font-semibold text-[var(--color-text-heading)] group-hover:text-[#121212] line-clamp-2 leading-snug">
                      {j.title}
                    </h3>
                    <p class="text-xs text-[var(--color-text-secondary)] mt-1 flex items-center gap-1.5">
                      <Icon name="building" size={12} class="text-[var(--color-text-muted)] shrink-0" />
                      <span class="truncate">{j.company}</span>
                    </p>
                  </div>

                  <!-- Experience requirement snippet -->
                  <div class="pt-1 flex items-center gap-1.5 text-[11px] text-[var(--color-text-secondary)] font-mono">
                    <Icon name="briefcase" size={12} class="text-[var(--color-text-muted)] shrink-0" />
                    <span class="truncate">{formatExp(j)}</span>
                  </div>

                  <!-- Location & Salary -->
                  <div class="flex items-center justify-between text-[11px] text-[var(--color-text-muted)] pt-1">
                    <span class="flex items-center gap-1 truncate max-w-[65%]">
                      <Icon name="mapPin" size={11} class="shrink-0" />
                      <span class="truncate">{formatArea(j.area)}</span>
                    </span>

                    {#if j.salary}
                      <span class="text-[#202020] font-medium font-mono text-[10px] truncate">
                        {j.salary}
                      </span>
                    {/if}
                  </div>
                </div>

                <!-- Footer Card -->
                <div class="mt-3 pt-2.5 border-t border-[var(--color-border-subtle)] flex items-center justify-between text-[11px] text-[var(--color-text-muted)]">
                  <span class="font-mono flex items-center gap-1">
                    <Icon name="clock" size={11} />
                    {formatTime(j.posted_at || j.first_seen_at)}
                  </span>

                  <span class="text-xs font-semibold text-[var(--color-text-secondary)] group-hover:text-[var(--color-text-heading)] flex items-center gap-1">
                    <span>Lihat</span>
                    <Icon name="arrowDownRight" size={12} />
                  </span>
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </main>

      <!-- ========================================================= -->
      <!-- COLUMN 3: SIDEBAR DETAIL (1 part, visible when card clicked) -->
      <!-- ========================================================= -->
      {#if activeJob}
        <aside class="lg:col-span-1 bg-[var(--color-surface)] p-4 rounded-2xl border border-[var(--color-border)] space-y-4 max-h-[calc(100vh-6rem)] overflow-y-auto sticky top-16 shadow-sm">
          <!-- Top Close & Action header -->
          <div class="flex items-center justify-between pb-3 border-b border-[var(--color-border-subtle)]">
            <span class="text-xs font-mono uppercase tracking-wider text-[var(--color-text-muted)]">
              Detail Loker
            </span>
            <div class="flex items-center gap-1.5">
              <a
                href={activeJob.url}
                target="_blank"
                rel="noopener noreferrer"
                class="control-pill px-2.5 py-1 text-[11px] font-mono flex items-center gap-1 text-[var(--color-text-heading)]"
                title="Buka Halaman Loker Asli"
              >
                <span>Buka</span>
                <Icon name="arrowUpRight" size={11} />
              </a>

              <button
                onclick={() => (activeJob = null)}
                class="p-1 rounded-full text-[var(--color-text-muted)] hover:text-[var(--color-text-heading)] hover:bg-[var(--color-surface-hover)] cursor-pointer"
                title="Tutup Detail"
              >
                <Icon name="x" size={15} />
              </button>
            </div>
          </div>

          <!-- Title & Company -->
          <div class="space-y-1.5">
            <h2 class="text-sm font-semibold text-[var(--color-text-heading)] leading-snug">
              {activeJob.title}
            </h2>
            <div class="text-xs text-[var(--color-text-secondary)] space-y-1">
              <p class="flex items-center gap-1.5 font-medium">
                <Icon name="building" size={13} class="text-[var(--color-text-muted)] shrink-0" />
                <span>{activeJob.company}</span>
              </p>
              <p class="flex items-center gap-1.5">
                <Icon name="mapPin" size={13} class="text-[var(--color-text-muted)] shrink-0" />
                <span>{activeJob.location_raw || formatArea(activeJob.area)}</span>
              </p>
              {#if activeJob.salary}
                <p class="flex items-center gap-1.5 font-mono text-[var(--color-text-heading)]">
                  <Icon name="banknote" size={13} class="text-[var(--color-text-muted)] shrink-0" />
                  <span>{activeJob.salary}</span>
                </p>
              {/if}
            </div>
          </div>

          <!-- Role & Experience Spec -->
          <div class="p-3 bg-[var(--color-page)] rounded-xl border border-[var(--color-border-subtle)] space-y-2">
            <div class="text-[11px] font-mono uppercase tracking-wider text-[var(--color-text-muted)]">
              Klasifikasi Sistem
            </div>
            <div class="space-y-1 text-xs">
              <div class="flex items-center justify-between">
                <span class="text-[var(--color-text-secondary)]">Kategori:</span>
                <span class="font-semibold text-[var(--color-text-heading)]">{formatRole(activeJob.role_category)}</span>
              </div>
              <div class="flex items-center justify-between">
                <span class="text-[var(--color-text-secondary)]">Level:</span>
                <span class="font-semibold text-[var(--color-text-heading)]">{activeJob.experience_level ? activeJob.experience_level.toUpperCase() : 'FLEKSIBEL'}</span>
              </div>
              {#if activeJob.min_years !== null || activeJob.max_years !== null}
                <div class="flex items-center justify-between text-[11px] font-mono">
                  <span class="text-[var(--color-text-secondary)]">Rentang:</span>
                  <span class="text-[var(--color-text-heading)]">
                    {activeJob.min_years !== null ? activeJob.min_years : 0} - {activeJob.max_years !== null ? activeJob.max_years : '+'} th
                  </span>
                </div>
              {/if}
              {#if activeJob.experience_raw}
                <div class="pt-1 border-t border-[var(--color-border-subtle)] text-[10px] font-mono text-[var(--color-text-muted)]">
                  Kutipan: "{activeJob.experience_raw}"
                </div>
              {/if}
            </div>
          </div>

          <!-- Visual Timeline Section -->
          <div class="space-y-2 pt-1 border-t border-[var(--color-border-subtle)]">
            <div class="text-[11px] font-mono uppercase tracking-wider text-[var(--color-text-muted)]">
              Timeline Loker
            </div>
            <Timeline job={activeJob} />
          </div>

          <!-- Description Section -->
          <div class="space-y-2 pt-2 border-t border-[var(--color-border-subtle)]">
            <div class="text-[11px] font-mono uppercase tracking-wider text-[var(--color-text-muted)]">
              Deskripsi Pekerjaan
            </div>
            {#if activeJob.description && activeJob.description.trim()}
              <div class="text-xs text-[var(--color-text-secondary)] whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto pr-1 border border-[var(--color-border-subtle)] bg-[var(--color-page)] p-2.5 rounded-xl font-sans">
                {activeJob.description}
              </div>
            {:else}
              <p class="text-xs text-[var(--color-text-muted)] italic bg-[var(--color-page)] p-3 rounded-xl border border-[var(--color-border-subtle)]">
                Deskripsi lengkap tersedia langsung di portal perekrut. Klik tombol di bawah untuk membacanya.
              </p>
            {/if}
          </div>

          <!-- Direct Apply / Platform Links -->
          <div class="pt-2 border-t border-[var(--color-border-subtle)] space-y-2">
            {#if activeJob.sources && activeJob.sources.length > 1 && activeJob.urls}
              <div class="space-y-1">
                <span class="text-[11px] font-mono text-[var(--color-text-muted)]">Tersedia di {activeJob.sources.length} portal:</span>
                <div class="grid grid-cols-2 gap-1.5 pt-1">
                  {#each activeJob.sources as src}
                    <a
                      href={activeJob.urls[src]}
                      target="_blank"
                      rel="noopener noreferrer"
                      class="control-pill px-2 py-1.5 text-xs text-center truncate capitalize text-[var(--color-text-heading)] font-medium"
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
                class="control-pill control-pill-active w-full py-2 text-xs font-semibold flex items-center justify-center gap-1.5 cursor-pointer text-decoration-none"
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

  <!-- Add Saved Search Modal -->
  {#if showAddSearch}
    <div class="fixed inset-0 bg-[#121212]/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
      <div class="bg-[var(--color-page)] rounded-2xl max-w-md w-full p-6 shadow-xl border border-[var(--color-border)] space-y-4">
        <div class="flex items-center justify-between pb-3 border-b border-[var(--color-border-subtle)]">
          <div class="flex items-center gap-2">
            <span class="w-6 h-6 rounded-full bg-[var(--color-accent)] text-[#121212] flex items-center justify-center">
              <Icon name="plus" size={13} />
            </span>
            <h3 class="text-sm font-semibold text-[var(--color-text-heading)]">
              Simpan Pencarian Otomatis
            </h3>
          </div>
          <button
            onclick={() => (showAddSearch = false)}
            class="text-[var(--color-text-muted)] hover:text-[var(--color-text-heading)] cursor-pointer p-1"
          >
            <Icon name="x" size={15} />
          </button>
        </div>

        <form onsubmit={submitNewSearch} class="space-y-4">
          <div>
            <label for="kw-input" class="block text-xs font-mono uppercase tracking-wider text-[var(--color-text-secondary)] mb-1">
              Kata Kunci Posisi / Skill
            </label>
            <input
              id="kw-input"
              type="text"
              required
              placeholder="e.g. Junior Backend Engineer, Golang, React"
              bind:value={newKeyword}
              class="w-full text-xs px-3 py-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-heading)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
            />
          </div>

          <div>
            <label for="area-select" class="block text-xs font-mono uppercase tracking-wider text-[var(--color-text-secondary)] mb-1">
              Target Area
            </label>
            <select
              id="area-select"
              bind:value={newArea}
              class="w-full text-xs px-3 py-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-heading)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
            >
              {#each areas as a}
                <option value={a.id}>{a.label}</option>
              {/each}
            </select>
          </div>

          <div>
            <span class="block text-xs font-mono uppercase tracking-wider text-[var(--color-text-secondary)] mb-2">
              Sumber Platform Tiap Jam
            </span>
            <div class="grid grid-cols-2 gap-2 text-xs font-mono">
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" bind:checked={newSources.jobstreet} class="accent-[var(--color-accent)] rounded" />
                JobStreet
              </label>
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" bind:checked={newSources.kalibrr} class="accent-[var(--color-accent)] rounded" />
                Kalibrr
              </label>
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" bind:checked={newSources.linkedin} class="accent-[var(--color-accent)] rounded" />
                LinkedIn
              </label>
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" bind:checked={newSources.glints} class="accent-[var(--color-accent)] rounded" />
                Glints
              </label>
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" bind:checked={newSources.dealls} class="accent-[var(--color-accent)] rounded" />
                Dealls
              </label>
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" bind:checked={newSources.karir} class="accent-[var(--color-accent)] rounded" />
                Karir.com
              </label>
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" bind:checked={newSources.techinasia} class="accent-[var(--color-accent)] rounded" />
                Tech in Asia
              </label>
            </div>
          </div>

          <div class="pt-3 border-t border-[var(--color-border-subtle)] flex justify-end gap-2">
            <button
              type="button"
              onclick={() => (showAddSearch = false)}
              class="control-pill px-3 py-1.5 text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text-heading)] cursor-pointer"
            >
              Batal
            </button>
            <button
              type="submit"
              class="control-pill control-pill-active px-4 py-1.5 text-xs font-semibold cursor-pointer"
            >
              Simpan Pencarian
            </button>
          </div>
        </form>
      </div>
    </div>
  {/if}
</div>
