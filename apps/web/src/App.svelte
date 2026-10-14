<script>
  import { onMount } from 'svelte';
  import Icon from './components/Icon.svelte';
  import Button from './components/ui/Button.svelte';
  import WorkspaceShell from './components/layout/WorkspaceShell.svelte';
  import FilterSidebar from './components/jobs/FilterSidebar.svelte';
  import JobCard from './components/jobs/JobCard.svelte';
  import JobInspector from './components/jobs/JobInspector.svelte';

  // Core State
  let jobs = $state([]);
  let searches = $state([]);
  let latestRuns = $state([]);
  let companies = $state([]);
  let loading = $state(false);
  let runningScraper = $state(false);
  let activeJob = $state(null);

  // UI state is kept separate from the existing server-side API filters.
  let displayMode = $state('grid');
  let theme = $state('light');
  let mobileFilterOpen = $state(false);
  let mobileDetailOpen = $state(false);
  let showSavedOnly = $state(false);
  let savedIds = $state([]);
  let jobsError = $state('');
  let searchTimer;
  let latestRequest = 0;
  let visibleJobs = $derived.by(() => {
    const filtered = showSavedOnly ? jobs.filter(job => savedIds.includes(job.id)) : [...jobs];
    if (displayMode === 'list') return filtered;
    return filtered;
  });

  const sourceLabels = [
    ['jobstreet','JobStreet'],['kalibrr','Kalibrr'],['linkedin','LinkedIn'],
    ['glints','Glints'],['dealls','Dealls'],['karir','Karir.com'],['techinasia','Tech in Asia']
  ];

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
    const requestId = ++latestRequest;
    loading = true;
    jobsError = '';
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
      if (!res.ok) throw new Error('Gagal mengambil lowongan: HTTP ' + res.status);
      const data = await res.json();
      if (requestId !== latestRequest) return;
      jobs = data.jobs || [];
      if (!activeJob && jobs.length) activeJob = jobs[0];

      // Update activeJob reference if still in list
      if (activeJob) {
        const found = jobs.find(j => j.id === activeJob.id);
        if (found) activeJob = found;
      }
    } catch (e) {
      if (requestId === latestRequest) {
        jobsError = e?.message || 'Tidak dapat memuat lowongan.';
        console.error('Error loading jobs:', e);
      }
    } finally {
      if (requestId === latestRequest) loading = false;
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

  function changeFilter(type, value) {
    switch (type) {
      case 'role': selectedRole = value; break;
      case 'experience': selectedExperience = value; break;
      case 'company': selectedCompany = value; break;
      case 'area': selectedArea = value; break;
      case 'source': selectedSource = value; break;
      case 'new': onlyNew = value; break;
      default: return;
    }
    loadJobs();
  }

  function scheduleLoadJobs() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadJobs, 280);
  }

  function toggleSaved(job) {
    savedIds = savedIds.includes(job.id) ? savedIds.filter(id => id !== job.id) : [...savedIds, job.id];
    try { localStorage.setItem('kerjo:saved-job-ids', JSON.stringify(savedIds)); } catch {}
  }

  function toggleTheme() {
    theme = theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('kerjo:theme', theme); } catch {}
  }

  function chooseJob(job) {
    selectJob(job);
    mobileFilterOpen = false;
    mobileDetailOpen = true;
  }

  onMount(() => {
    try {
      const storedIds = JSON.parse(localStorage.getItem('kerjo:saved-job-ids') || '[]');
      if (Array.isArray(storedIds)) savedIds = storedIds;
      theme = localStorage.getItem('kerjo:theme') === 'dark' ? 'dark' : 'light';
      document.documentElement.dataset.theme = theme;
    } catch {}
    loadJobs();
    loadCompanies();
    loadSearches();
    loadRuns();
    return () => clearTimeout(searchTimer);
  });
</script>

<WorkspaceShell filterOpen={mobileFilterOpen} detailOpen={mobileDetailOpen} onDismiss={() => { mobileFilterOpen = false; mobileDetailOpen = false; }}>
  {#snippet header()}
    <a class="app-brand" href="/" aria-label="Kerjo home">
      <span class="app-brand-mark"><Icon name="briefcase" size={17}/></span>
      <span class="app-brand-name">kerjo</span>
    </a>
    <span class="app-divider"></span>
    <span class="app-context">JOB DISCOVERY / JAKARTA</span>
    <div class="app-actions">
      <span class="app-status">{searches.length} auto-search tersimpan</span>
      <button class="ui-icon-button" type="button" onclick={toggleTheme} title={theme === 'dark' ? 'Light mode' : 'Dark mode'} aria-label="Ganti tema">
        <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={16}/>
      </button>
      <span class="desktop-action"><Button onclick={markAllSeen}><Icon name="checkCircle" size={14}/>Tandai dilihat</Button></span>
      <Button onclick={() => showAddSearch = true}><Icon name="plus" size={14}/><span class="desktop-action">Tambah pencarian</span></Button>
      <Button variant="primary" disabled={runningScraper} onclick={triggerRun}><Icon name="refresh" size={14}/><span>{runningScraper ? 'Scraping…' : 'Scrape sekarang'}</span></Button>
    </div>
  {/snippet}

  {#snippet filters()}
    <FilterSidebar
      roles={roleCategories}
      levels={experienceLevels}
      {areas}
      {platforms}
      {companies}
      {searches}
      {selectedRole}
      {selectedExperience}
      {selectedArea}
      {selectedSource}
      {selectedCompany}
      {onlyNew}
      onFilter={changeFilter}
      onReset={resetAllFilters}
      onAddSearch={() => showAddSearch = true}
      onToggleSearch={toggleSearch}
      onDeleteSearch={deleteSearch}
    />
  {/snippet}

  {#snippet results()}
    <div class="results-search">
      <button class="ui-icon-button mobile-filter-toggle" onclick={() => { mobileFilterOpen = true; mobileDetailOpen = false; }} title="Buka filter" aria-label="Buka filter"><Icon name="filter" size={16}/></button>
      <Icon name="search" size={16} class="text-[var(--color-text-muted)]"/>
      <input
        type="search"
        placeholder="Cari posisi, perusahaan, atau teknologi…"
        aria-label="Cari lowongan"
        bind:value={searchQuery}
        oninput={scheduleLoadJobs}
      />
      {#if searchQuery}
        <button class="ui-icon-button" onclick={() => { searchQuery = ''; loadJobs(); }} aria-label="Kosongkan pencarian"><Icon name="x" size={14}/></button>
      {/if}
    </div>
    <div class="results-toolbar">
      <strong>{showSavedOnly ? 'Saved positions' : selectedRole === 'all' ? 'All positions' : roleCategories.find(r => r.id === selectedRole)?.label}</strong>
      <span class="results-count">{loading ? 'Memuat…' : visibleJobs.length + ' ditampilkan'}</span>
      <div class="results-actions">
        <button type="button" class="ui-icon-button" class:is-active={showSavedOnly} onclick={() => showSavedOnly = !showSavedOnly} aria-pressed={showSavedOnly} title="Hanya simpanan lokal" aria-label="Tampilkan posisi tersimpan"><Icon name="bookmark" size={16}/></button>
        <div class="view-segments" aria-label="Mode tampilan">
          <button type="button" aria-label="Grid view" aria-pressed={displayMode === 'grid'} onclick={() => displayMode = 'grid'}><Icon name="grid" size={14}/></button>
          <button type="button" aria-label="List view" aria-pressed={displayMode === 'list'} onclick={() => displayMode = 'list'}><Icon name="list" size={14}/></button>
        </div>
      </div>
    </div>
    <div class="results-content">
      {#if jobsError}
        <div class="ui-empty" role="alert"><strong>Gagal memuat lowongan</strong>{jobsError}<div style="margin-top:12px"><Button onclick={loadJobs}>Coba lagi</Button></div></div>
      {:else if !loading && visibleJobs.length === 0}
        <div class="ui-empty"><strong>Tidak ada posisi yang cocok</strong>{showSavedOnly ? 'Belum ada lowongan yang disimpan secara lokal.' : 'Ubah filter atau pencarian untuk memperluas hasil.'}<div style="margin-top:12px"><Button onclick={() => { showSavedOnly = false; resetAllFilters(); }}>Reset filter</Button></div></div>
      {:else}
        <div class="job-board" class:is-list={displayMode === 'list'}>
          {#each visibleJobs as job (job.id)}
            <JobCard
              {job}
              selected={activeJob?.id === job.id}
              saved={savedIds.includes(job.id)}
              onSelect={chooseJob}
              onSave={toggleSaved}
              {formatRole}
              {formatArea}
              {formatTime}
            />
          {/each}
        </div>
      {/if}
    </div>
  {/snippet}

  {#snippet inspector()}
    <JobInspector
      job={activeJob}
      saved={activeJob ? savedIds.includes(activeJob.id) : false}
      onClose={() => { activeJob = null; mobileDetailOpen = false; }}
      onCompany={filterByCompany}
      onSeen={markJobSeen}
      onSave={toggleSaved}
      {formatRole}
      {formatArea}
    />
  {/snippet}
</WorkspaceShell>

{#if showAddSearch}
  <div class="ui-modal-backdrop" role="presentation">
    <section class="ui-modal" role="dialog" aria-modal="true" aria-labelledby="add-search-title">
      <div class="ui-modal-header">
        <h2 id="add-search-title">Tambah pencarian otomatis</h2>
        <button type="button" class="ui-icon-button" onclick={() => showAddSearch = false} aria-label="Tutup dialog"><Icon name="x" size={16}/></button>
      </div>
      <form onsubmit={submitNewSearch}>
        <div class="ui-modal-field">
          <label for="search-keyword">Kata kunci posisi / skill</label>
          <input id="search-keyword" class="ui-input" required placeholder="Junior Backend Engineer, Golang, React…" bind:value={newKeyword}/>
        </div>
        <div class="ui-modal-field">
          <label for="search-area">Target area</label>
          <select id="search-area" class="ui-input" bind:value={newArea}>
            {#each areas as a}<option value={a.id}>{a.label}</option>{/each}
          </select>
        </div>
        <fieldset class="ui-platforms">
          <legend class="ui-eyebrow">Sumber portal</legend>
          {#each sourceLabels as [sourceId, sourceName]}
            <label><input type="checkbox" checked={newSources[sourceId]} onchange={(e) => newSources[sourceId] = e.currentTarget.checked}/>{sourceName}</label>
          {/each}
        </fieldset>
        <div class="ui-modal-actions">
          <Button onclick={() => showAddSearch = false}>Batal</Button>
          <Button type="submit" variant="primary">Simpan pencarian</Button>
        </div>
      </form>
    </section>
  </div>
{/if}
