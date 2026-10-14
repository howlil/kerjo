<script>
  import Icon from '../Icon.svelte';
  import Timeline from '../Timeline.svelte';
  import CompanyAvatar from '../ui/CompanyAvatar.svelte';
  import Button from '../ui/Button.svelte';
  let { job = null, saved = false, onClose, onCompany, onSeen, onSave, formatRole, formatArea } = $props();
</script>

<div class="panel-heading">
  <span class="ui-eyebrow">POSITION DETAILS</span>
  <div style="display:flex;gap:3px;align-items:center">
    {#if job}
      <button type="button" class="ui-icon-button" class:is-active={saved} onclick={() => onSave(job)} aria-label={saved ? 'Hapus simpanan lokal' : 'Simpan posisi'} title="Simpan posisi">
        <Icon name="bookmark" size={15}/>
      </button>
    {/if}
    <button type="button" class="ui-icon-button" onclick={onClose} aria-label="Tutup detail"><Icon name="x" size={16}/></button>
  </div>
</div>
{#if job}
  <div class="panel-scroll">
    <section class="inspector-title">
      <CompanyAvatar company={job.company} logo={job.company_logo} size={40}/>
      <h2>{job.title}</h2>
      <button type="button" class="inspector-company" onclick={() => onCompany(job.company)} title="Filter perusahaan ini">{job.company}</button>
      <div class="inspector-location"><Icon name="mapPin" size={14}/><span>{job.location_raw || formatArea(job.area)}</span></div>
    </section>
    <section class="panel-section">
      <h3>CLASSIFICATION</h3>
      <dl class="inspector-facts">
        <div><dt>Category</dt><dd>{formatRole(job.role_category)}</dd></div>
        <div><dt>Seniority</dt><dd>{(job.experience_level || 'unspecified').toUpperCase()}</dd></div>
        <div><dt>Platform</dt><dd>{job.sources?.length > 1 ? job.sources.length + ' platform' : (job.source || '—')}</dd></div>
        <div><dt>Salary</dt><dd>{job.salary || 'Not disclosed'}</dd></div>
      </dl>
      {#if job.experience_raw}<p class="inspector-note">Persyaratan: {job.experience_raw}</p>{/if}
    </section>
    <section class="panel-section">
      <h3>ACTIVITY</h3>
      <Timeline {job}/>
    </section>
    <section class="panel-section">
      <h3>DESCRIPTION</h3>
      {#if job.description?.trim()}
        <p class="inspector-description">{job.description}</p>
      {:else}
        <p class="inspector-description">Deskripsi lengkap tidak tersedia pada data saat ini. Lihat halaman sumber untuk informasi perekrut.</p>
      {/if}
      {#if job.sources?.length > 1 && job.urls}
        <nav class="inspector-links" aria-label="Sumber lowongan">
          {#each job.sources as src}
            {#if job.urls[src]}
              <a class="inspector-source" href={job.urls[src]} target="_blank" rel="noopener noreferrer">{src.toUpperCase()} <Icon name="arrowUpRight" size={12}/></a>
            {/if}
          {/each}
        </nav>
      {/if}
    </section>
  </div>
  <div class="inspector-footer">
    <Button onclick={() => onSeen(job)} disabled={!job.is_new}><Icon name="checkCircle" size={14}/>{job.is_new ? 'Tandai dilihat' : 'Sudah dilihat'}</Button>
    {#if job.url}
      <a class="inspector-open" href={job.url} target="_blank" rel="noopener noreferrer">Buka sumber <Icon name="arrowUpRight" size={14}/></a>
    {:else}
      <span class="inspector-open is-disabled">Tautan tidak ada</span>
    {/if}
  </div>
{:else}
  <div class="panel-scroll inspector-placeholder"><Icon name="briefcase" size={23}/><strong>Pilih lowongan</strong><span>Detail posisi akan ditampilkan di sini.</span></div>
{/if}
