<script>
  import { onMount } from 'svelte';
  import Icon from './components/Icon.svelte';
  import Button from './components/ui/Button.svelte';
  import WorkspaceShell from './components/layout/WorkspaceShell.svelte';
  import FilterSidebar from './components/jobs/FilterSidebar.svelte';
  import JobCard from './components/jobs/JobCard.svelte';
  import JobInspector from './components/jobs/JobInspector.svelte';
  import ApplicationPipeline from './components/workflow/ApplicationPipeline.svelte';
  import PreferencePanel from './components/workflow/PreferencePanel.svelte';

  // Core State
  let jobs = $state([]);
  let searches = $state([]);
  let latestRuns = $state([]);
  let companies = $state([]);
  let loading = $state(false);
  let runningScraper = $state(false);
  let activeJob = $state(null);
  let jobsTotal = $state(0);
  let currentView = $state('discovery');
  let notice = $state('');
  let applications = $state([]);
  let sourceHealth = $state([]);
  let preferences = $state({role_categories:[], areas:[],work_modes:[],keywords:[],max_required_years:null});
  let currentRun = $state(null);
  let sortMode = $state('recent');
  const PAGE_SIZE = 60;
  let currentPage = $state(0);

  // UI state is kept separate from the existing server-side API filters.
  let displayMode = $state('grid');
  let theme = $state('light');
  let mobileFilterOpen = $state(false);
  let mobileDetailOpen = $state(false);
  let showSavedOnly = $state(false);

  let jobsError = $state('');
  let searchTimer;
  let latestRequest = 0;
  let visibleJobs = $derived(jobs);

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

  async function api(url, options={}) {
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || ('HTTP ' + response.status));
    return data;
  }
  function jsonOptions(method,payload) {
    return {method,headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)};
  }
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
      if (showSavedOnly) params.set('saved','1');
      params.set('sort',sortMode);
      params.set('limit', String(PAGE_SIZE));
      params.set('offset', String(currentPage * PAGE_SIZE));

      const res = await fetch(`/api/jobs?${params.toString()}`);
      if (!res.ok) throw new Error('Gagal mengambil lowongan: HTTP ' + res.status);
      const data = await res.json();
      if (requestId !== latestRequest) return;
      if (!data.jobs?.length && currentPage > 0 && data.total > 0) {
        currentPage = Math.floor((data.total - 1) / PAGE_SIZE);
        await loadJobs();
        return;
      }
      jobs = data.jobs || [];
      jobsTotal = data.total ?? jobs.length;
      if (!activeJob && jobs.length) activeJob = jobs[0];

      // Update activeJob reference if still in list
      if (activeJob) {
        const found = jobs.find(j => j.id === activeJob.id || j.ids?.includes(activeJob.id));
        activeJob = found || null;
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

  async function loadApplications() {
    try { applications = (await api('/api/applications')).applications || []; }
    catch(e) { notice = 'Gagal memuat pipeline: ' + e.message; }
  }
  async function loadPreferences() {
    try { preferences = (await api('/api/preferences')).preferences; }
    catch(e) { notice = 'Gagal memuat preferensi: ' + e.message; }
  }
  async function savePreferences() {
    try {
      preferences = (await api('/api/preferences',jsonOptions('PUT',preferences))).preferences;
      notice = 'Preferensi tersimpan.';
      await loadJobs();
    } catch(e) { notice = 'Gagal menyimpan preferensi: ' + e.message; }
  }
  async function loadSourceHealth() {
    try { sourceHealth = (await api('/api/source-health')).sources || []; }
    catch(e) { notice = 'Gagal memuat source health: ' + e.message; }
  }
  async function recoverRun() {
    try {
      const run = (await api('/api/run/latest')).run;
      if (run && ['queued','running'].includes(run.status)) {
        currentRun = run;
        runningScraper = true;
      }
    } catch(e) { console.warn('Unable to restore run',e); }
  }
  async function pollRun() {
    if (!currentRun || !runningScraper) return;
    try {
      const run = (await api('/api/run/' + currentRun.id)).run;
      currentRun = run;
      if (['completed','partial','failed','skipped'].includes(run.status)) {
        runningScraper = false;
        notice = run.status === 'completed'
          ? ('Scraping selesai: ' + run.jobs_new + ' lowongan baru')
          : run.status === 'skipped'
            ? 'Tidak ada saved search aktif; scraper tidak dijalankan.'
            : ('Scraping ' + run.status + ' — ' + run.errors + ' sumber mengalami error');
        await Promise.all([loadJobs(),loadRuns(),loadCompanies(),loadSourceHealth()]);
      }
    } catch(e) { runningScraper=false; notice = 'Error saat memantau worker: '+e.message; }
  }
  async function triggerRun() {
    if (runningScraper) return;
    runningScraper = true;
    try {
      const result = await api('/api/run',jsonOptions('POST',{}));
      currentRun = {id:result.run_id,status:'queued',processed_tasks:0,total_tasks:0,jobs_new:0};
      notice = 'Scraping berjalan di worker. Dashboard tetap responsif.';
    } catch(e) { runningScraper=false; notice='Gagal menjalankan scraper: '+e.message; }
  }

  function selectJob(job) {
    activeJob = job;
  }

  function filterByCompany(compName) {
    if (!compName) return;
    selectedCompany = compName;
    currentPage = 0;
    loadJobs();
  }

  async function markJobSeen(job) {
    if (!job?.is_new) return;
    try {
      const ids = job.ids?.length ? job.ids : [job.id];
      await api('/api/jobs/seen-all',jsonOptions('POST',{ids}));
      job.is_new = 0;
      if (onlyNew) { currentPage = 0; await loadJobs(); }
    } catch(e) { notice = 'Gagal menandai dilihat: '+e.message; }
  }

  async function markAllSeen() {
    if (!jobs.length || !confirm('Tandai hanya lowongan yang sedang ditampilkan sebagai sudah dilihat?')) return;
    try {
      const ids = [...new Set(jobs.flatMap(j=>j.ids?.length?j.ids:[j.id]))];
      await api('/api/jobs/seen-all',jsonOptions('POST',{ids}));
      for (const j of jobs) j.is_new = 0;
      if (onlyNew) await loadJobs();
    } catch(e) { notice='Gagal menandai dilihat: '+e.message; }
  }

  async function updateApplication(job,payload) {
    try {
      const ids = job.ids?.length ? job.ids : [job.id];
      await api('/api/jobs/'+job.id+'/application',jsonOptions('PUT',{...payload,ids}));
      notice = 'Status lamaran diperbarui.';
      await Promise.all([loadJobs(),loadApplications()]);
      return true;
    } catch(e) { notice='Gagal memperbarui lamaran: '+e.message; return false; }
  }

  async function updatePipelineStatus(app,status) {
    try {
      await api('/api/jobs/'+app.job_id+'/application',jsonOptions('PUT',{
        ids:app.ids||[app.job_id],status,notes:app.notes,follow_up_at:app.follow_up_at
      }));
      await Promise.all([loadApplications(),loadJobs()]);
    } catch(e) {
      notice = 'Transisi ditolak: '+e.message;
      await loadApplications();
    }
  }

  async function toggleSearch(searchId) {
    try {
      await api('/api/searches/' + searchId + '/toggle',{method:'PUT'});
      await loadSearches();
    } catch(e) { notice = 'Gagal mengubah saved search: ' + e.message; }
  }

  async function deleteSearch(searchId) {
    if (!confirm('Hapus pencarian tersimpan ini?')) return;
    try {
      await api('/api/searches/' + searchId,{method:'DELETE'});
      await loadSearches();
    } catch(e) { notice = 'Gagal menghapus saved search: ' + e.message; }
  }

  async function submitNewSearch(e) {
    e.preventDefault();
    const sources = Object.keys(newSources).filter(k=>newSources[k]);
    if (!sources.length) { notice = 'Pilih minimal satu sumber lowongan.'; return; }
    try {
      await api('/api/searches',jsonOptions('POST',{
        keyword:newKeyword, area:newArea, sources
      }));
      newKeyword = '';
      showAddSearch = false;
      await Promise.all([loadSearches(),loadJobs(),loadCompanies()]);
      notice = 'Saved search ditambahkan.';
    } catch(e) { notice = 'Gagal menyimpan pencarian: ' + e.message; }
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
    if (!areaStr || areaStr === 'unspecified') return 'Lokasi belum pasti';
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
    return 'Syarat pengalaman belum diketahui';
  }

  function resetAllFilters() {
    selectedArea = 'all';
    selectedRole = 'all';
    selectedExperience = 'all';
    selectedSource = 'all';
    selectedCompany = 'all';
    onlyNew = false;
    searchQuery = '';
    currentPage = 0;
    showSavedOnly = false;
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
    currentPage = 0;
    loadJobs();
  }

  function scheduleLoadJobs() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { currentPage = 0; loadJobs(); }, 280);
  }

  async function toggleSaved(job) {
    try {
      const ids = job.ids?.length ? job.ids : [job.id];
      const saved = !Boolean(job.is_saved);
      await api('/api/jobs/'+job.id+'/save',jsonOptions('POST',{ids,saved}));
      job.is_saved = Number(saved);
      if (activeJob?.id === job.id) activeJob.is_saved = Number(saved);
      if (showSavedOnly) await loadJobs();
    } catch(e) { notice = 'Gagal menyimpan lowongan: '+e.message; }
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
      theme = localStorage.getItem('kerjo:theme') === 'dark' ? 'dark' : 'light';
      document.documentElement.dataset.theme = theme;
    } catch {}
    loadJobs();
    loadCompanies();
    loadSearches();
    loadRuns();
    loadPreferences();
    loadApplications();
    loadSourceHealth();
    recoverRun();
    const interval = setInterval(()=>{if(runningScraper && currentRun) pollRun();},2500);
    return () => {clearTimeout(searchTimer);clearInterval(interval);};
  });
</script>

<WorkspaceShell mode={currentView} filterOpen={mobileFilterOpen} detailOpen={mobileDetailOpen} onDismiss={() => { mobileFilterOpen = false; mobileDetailOpen = false; }}>
  {#snippet header()}
    <a class="app-brand" href="/" aria-label="Kerjo home">
      <span class="app-brand-mark"><Icon name="briefcase" size={17}/></span>
      <span class="app-brand-name">kerjo</span>
    </a>
    <span class="app-divider"></span>
    <span class="app-context">JOB DISCOVERY / JAKARTA</span>
    <nav class="app-view-tabs" aria-label="Kerjo views">
      {#each [{id:'discovery',title:'Discover'},{id:'applications',title:'Applications'},{id:'preferences',title:'Preferences'}] as view}
        <button type="button" class:is-active={currentView===view.id}
          onclick={()=>{currentView=view.id;mobileFilterOpen=false;mobileDetailOpen=false;
            if(view.id==='applications')loadApplications();
            if(view.id==='preferences')loadSourceHealth();}}
          aria-current={currentView===view.id?'page':undefined}>{view.title}</button>
      {/each}
    </nav>
    <div class="app-actions">
      <span class="app-status">{runningScraper && currentRun ? 'Worker '+(currentRun.processed_tasks||0)+'/'+(currentRun.total_tasks||'?') : searches.length+' auto-search'}</span>
      <button class="ui-icon-button" type="button" onclick={toggleTheme} title={theme === 'dark' ? 'Light mode' : 'Dark mode'} aria-label="Ganti tema">
        <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={16}/>
      </button>
      {#if currentView==='discovery'}
      <span class="desktop-action"><Button onclick={markAllSeen}><Icon name="checkCircle" size={14}/>Tandai dilihat</Button></span>
      <Button onclick={() => showAddSearch = true}><Icon name="plus" size={14}/><span class="desktop-action">Tambah pencarian</span></Button>
      {/if}
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
      <span class="results-count">{loading ? 'Memuat…' : jobsTotal ? (currentPage * PAGE_SIZE + 1) + '–' + (currentPage * PAGE_SIZE + visibleJobs.length) + ' dari ' + jobsTotal : '0 lowongan'}</span>
      <div class="results-actions">
        <label for="results-sort" class="results-sort-label">Sort</label>
        <select id="results-sort" class="ui-input results-sort" bind:value={sortMode} onchange={()=>{currentPage=0;loadJobs();}}>
          <option value="recent">Recent</option>
          <option value="match">Best match</option>
        </select>
        <button type="button" class="ui-icon-button" class:is-active={showSavedOnly} onclick={() => {showSavedOnly = !showSavedOnly;currentPage=0;loadJobs();}} aria-pressed={showSavedOnly} title="Hanya lowongan tersimpan" aria-label="Tampilkan posisi tersimpan"><Icon name="bookmark" size={16}/></button>
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
              saved={Boolean(job.is_saved)}
              onSelect={chooseJob}
              onSave={toggleSaved}
              {formatRole}
              {formatArea}
              {formatTime}
            />
          {/each}
        </div>
      {/if}
      {#if jobsTotal > PAGE_SIZE}
        <nav class="results-pagination" aria-label="Navigasi halaman lowongan">
          <button type="button" disabled={currentPage===0 || loading} onclick={()=>{currentPage--;loadJobs();}}>← Sebelumnya</button>
          <span>Halaman {currentPage + 1} / {Math.ceil(jobsTotal / PAGE_SIZE)}</span>
          <button type="button" disabled={(currentPage+1)*PAGE_SIZE>=jobsTotal || loading} onclick={()=>{currentPage++;loadJobs();}}>Berikutnya →</button>
        </nav>
      {/if}
    </div>
  {/snippet}

  {#snippet inspector()}
    <JobInspector
      job={activeJob}
      saved={Boolean(activeJob?.is_saved)}
      onClose={() => { activeJob = null; mobileDetailOpen = false; }}
      onCompany={filterByCompany}
      onSeen={markJobSeen}
      onSave={toggleSaved}
      onApply={updateApplication}
      {formatRole}
      {formatArea}
    />
  {/snippet}
  {#snippet full()}
    {#if currentView === 'applications'}
      <ApplicationPipeline {applications} onStatusChange={updatePipelineStatus} {formatTime}/>
    {:else if currentView === 'preferences'}
      <PreferencePanel {preferences} roles={roleCategories} {areas} sources={sourceHealth}
        onChange={(next)=>preferences=next} onSave={savePreferences} {formatTime}/>
    {/if}
  {/snippet}
</WorkspaceShell>
{#if notice}
  <div class="app-notice" role="status">
    <span>{notice}</span>
    <button type="button" onclick={()=>notice=''} aria-label="Tutup notifikasi"><Icon name="x" size={14}/></button>
  </div>
{/if}

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

<style>
.app-view-tabs{display:flex;align-items:center;gap:3px;margin-left:auto;flex-shrink:0}
.app-view-tabs button{padding:6px 9px;border-radius:var(--radius-md);color:var(--color-text-secondary);font-size:11px;font-weight:650;cursor:pointer;white-space:nowrap}
.app-view-tabs button:hover{background:var(--color-surface-hover)}
.app-view-tabs button.is-active{background:var(--color-text-heading);color:var(--color-page)}
.results-sort{font-size:11px;min-width:100px;max-width:130px;padding:5px 8px}
.results-sort-label{font-size:11px;color:var(--color-text-muted)}
.app-notice{position:fixed;right:16px;bottom:16px;z-index:100;padding:12px 15px;border:1px solid var(--color-border-strong);border-radius:var(--radius-md);background:var(--color-surface);box-shadow:0 4px 18px rgba(0,0,0,.12);max-width:350px;color:var(--color-text-heading);font-size:12px;display:flex;align-items:center;gap:12px}
.app-notice button{background:none;border:0;color:var(--color-text-secondary);cursor:pointer}
@media(max-width:1020px){.app-context,.app-divider{display:none}.app-view-tabs button{font-size:10px;padding:6px}}
@media(max-width:680px){.app-view-tabs{gap:0}.app-view-tabs button{font-size:9px;padding:5px}.app-status,.results-sort-label{display:none}.results-sort{min-width:73px;width:75px}.app-brand-name{display:none}}

.results-pagination{display:flex;gap:14px;align-items:center;justify-content:center;flex-shrink:0;padding:10px;border-top:1px solid var(--color-border);font-size:11px;color:var(--color-text-secondary)}
.results-pagination button{cursor:pointer;color:var(--color-text-heading);font-size:11px;padding:5px 9px;border:1px solid var(--color-border);border-radius:var(--radius-md);background:var(--color-surface)}
.results-pagination button:disabled{opacity:.35;cursor:not-allowed}
</style>
