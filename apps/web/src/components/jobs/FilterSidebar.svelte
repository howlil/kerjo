<script>
  import Icon from '../Icon.svelte';
  let { roles, levels, areas, platforms, companies, searches,
    selectedRole, selectedExperience, selectedArea, selectedSource, selectedCompany, onlyNew,
    onFilter, onReset, onAddSearch, onToggleSearch, onDeleteSearch } = $props();
</script>
<div class="panel-heading">
  <div style="display:flex;align-items:center;gap:8px"><Icon name="filter" size={15}/><strong>Filters</strong></div>
  <button type="button" class="panel-reset" onclick={onReset}>Reset all</button>
</div>
<div class="panel-scroll">
  <section class="panel-section">
    <h3>Category / Role</h3>
    {#each roles as role}
      <button type="button" class="filter-option" aria-pressed={selectedRole === role.id} onclick={() => onFilter('role',role.id)}>{role.label}</button>
    {/each}
  </section>
  <section class="panel-section">
    <h3>Seniority</h3>
    <div class="filter-levels">
      {#each levels as level}
        <button type="button" class="filter-level" aria-pressed={selectedExperience === level.id} onclick={() => onFilter('experience',level.id)}>{level.id === 'all' ? 'Any' : level.id === 'entry' ? 'Entry' : level.id === 'mid' ? 'Mid' : 'Senior'}</button>
      {/each}
    </div>
  </section>
  <section class="panel-section">
    <h3>Preferences</h3>
    <div class="filter-field">
      <label for="filter-company">Perusahaan ({companies.length})</label>
      <select class="ui-input" id="filter-company" value={selectedCompany} onchange={(e) => onFilter('company',e.currentTarget.value)}>
        <option value="all">Semua perusahaan</option>
        {#each companies as c}<option value={c.company}>{c.company} ({c.job_count})</option>{/each}
      </select>
    </div>
    <div class="filter-field">
      <label for="filter-area">Area</label>
      <select class="ui-input" id="filter-area" value={selectedArea} onchange={(e) => onFilter('area',e.currentTarget.value)}>
        {#each areas as a}<option value={a.id}>{a.label}</option>{/each}
      </select>
    </div>
    <div class="filter-field">
      <label for="filter-platform">Platform</label>
      <select class="ui-input" id="filter-platform" value={selectedSource} onchange={(e) => onFilter('source',e.currentTarget.value)}>
        {#each platforms as p}<option value={p.id}>{p.label}</option>{/each}
      </select>
    </div>
  </section>
  <section class="panel-section">
    <h3>Quick filters</h3>
    <label class="filter-checkbox"><input type="checkbox" checked={onlyNew} onchange={(e)=>onFilter('new',e.currentTarget.checked)}/> Hanya lowongan baru</label>
  </section>
  <section class="panel-section">
    <div class="filter-section-heading"><h3 style="margin-bottom:0">AUTO-SEARCH ({searches.length})</h3><button type="button" class="ui-icon-button" onclick={onAddSearch} title="Tambah pencarian otomatis" aria-label="Tambah pencarian otomatis"><Icon name="plus" size={14}/></button></div>
    {#if searches.length === 0}
      <p class="filter-hint">Belum ada pencarian terjadwal.</p>
    {:else}
      {#each searches as search}
        <div class="filter-search" style:opacity={search.is_active ? 1 : .55}>
          <span class="state-dot" class:is-on={search.is_active}></span>
          <button class="search-name" title={search.is_active ? 'Jeda pencarian' : 'Aktifkan pencarian'} onclick={() => onToggleSearch(search.id)}>{search.keyword}</button>
          <button title="Hapus pencarian" aria-label={'Hapus '+search.keyword} onclick={() => onDeleteSearch(search.id)}><Icon name="trash" size={13}/></button>
        </div>
      {/each}
    {/if}
  </section>
</div>
<div class="filter-footer"><span class="status-dot"></span> SAVED SEARCHES · JADWAL BELUM DIVERIFIKASI</div>
