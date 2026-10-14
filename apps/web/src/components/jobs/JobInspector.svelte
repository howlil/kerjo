<script>
  import Icon from '../Icon.svelte';
  import Timeline from '../Timeline.svelte';
  import CompanyAvatar from '../ui/CompanyAvatar.svelte';
  import Button from '../ui/Button.svelte';
  let { job = null, saved = false, onClose, onCompany, onSeen, onSave, onApply, formatRole, formatArea } = $props();
  let editing = $state(false);
  let lastJobId = $state(null);
  let draftStatus = $state('not_applied');
  let draftNotes = $state('');
  let draftFollowUp = $state('');
  $effect(() => {
    const id = job?.id ?? null;
    if (id !== lastJobId) {
      lastJobId = id;
      editing = false;
      draftStatus = job?.application_status || 'not_applied';
      draftNotes = job?.application_notes || '';
      draftFollowUp = job?.follow_up_at?.slice(0,10) || '';
    }
  });
  async function submitApplication() {
    if (!job || !onApply) return;
    const success = await onApply(job,{status:draftStatus,notes:draftNotes,follow_up_at:draftFollowUp || null});
    if (success) editing = false;
  }
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
        <div><dt>Posted</dt><dd>{job.posted_at || 'Tanggal tidak tersedia'}</dd></div>
        <div><dt>Salary</dt><dd>{job.salary || 'Not disclosed'}</dd></div>
      </dl>
      {#if job.experience_raw}<p class="inspector-note">Persyaratan: {job.experience_raw}</p>{/if}
    </section>
    <section class="panel-section">
      <h3>MATCH & ELIGIBILITY</h3>
      {#if job.match}
        <p class="inspector-note"><strong>{job.match.score}/100</strong> · {job.match.eligibility}</p>
        {#each job.match.reasons as reason}<p class="inspector-note">✓ {reason}</p>{/each}
        {#each job.match.blockers as reason}<p class="inspector-note">Mismatch: {reason}</p>{/each}
        {#each job.match.unknowns as reason}<p class="inspector-note">Belum pasti: {reason}</p>{/each}
      {/if}
      <div style="display:flex;gap:8px;align-items:center;margin-top:10px">
        <Button onclick={() => editing = !editing} variant="primary">{editing ? 'Tutup' : 'Kelola lamaran'}</Button>
        {#if job.application_status && job.application_status !== 'not_applied'}
          <span class="inspector-note">{job.application_status}</span>
        {/if}
      </div>
      {#if editing}
        <div class="inspector-application-form">
          <label>Status
            <select class="ui-input" bind:value={draftStatus}>
              {#each [['not_applied','Belum melamar'],['applied','Applied'],['screening','Screening'],['interview','Interview'],['offer','Offer'],['rejected','Rejected'],['withdrawn','Withdrawn']] as [id,label]}
                <option value={id}>{label}</option>
              {/each}
            </select>
          </label>
          <label>Catatan
            <textarea class="ui-input" rows="3" bind:value={draftNotes} placeholder="Catatan atau langkah berikutnya…"></textarea>
          </label>
          <label>Follow-up
            <input class="ui-input" type="date" bind:value={draftFollowUp}/>
          </label>
          <Button onclick={submitApplication} variant="primary">Simpan status</Button>
        </div>
      {/if}
    </section>
    <section class="panel-section">
      <h3>ACTIVITY</h3>
      <Timeline {job}/>
    </section>
    <section class="panel-section">
      <h3>DESCRIPTION</h3>
      <p class="inspector-note">
        {job.description_status === 'complete' ? 'Deskripsi lengkap tersedia'
          : job.description_status === 'partial' ? 'Ringkasan / belum lengkap'
          : 'Deskripsi belum ditemukan'}
        {#if job.description_source} · {job.description_source}{/if}
      </p>
      {#if job.application_evidence === 'careers-link-unverified'}
        <p class="inspector-note">Link karier ditemukan di posting HR, tetapi lowongan belum diverifikasi langsung.</p>
      {/if}
      {#if job.origin_url}
        <p class="inspector-note"><a href={job.origin_url} target="_blank" rel="noopener noreferrer">Lihat posting recruiter <Icon name="arrowUpRight" size={12}/></a></p>
      {/if}
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
      <a class="inspector-open" href={job.application_url || job.url} target="_blank" rel="noopener noreferrer">Buka lamaran <Icon name="arrowUpRight" size={14}/></a>
    {:else}
      <span class="inspector-open is-disabled">Tautan tidak ada</span>
    {/if}
  </div>
{:else}
  <div class="panel-scroll inspector-placeholder"><Icon name="briefcase" size={23}/><strong>Pilih lowongan</strong><span>Detail posisi akan ditampilkan di sini.</span></div>
{/if}

<style>
.inspector-application-form{display:grid;gap:10px;margin-top:12px}
.inspector-application-form label{display:grid;gap:5px;font-size:11px;color:var(--color-text-secondary)}
.inspector-application-form .ui-input{padding:8px;font-size:12px;color:var(--color-text-heading);background:var(--color-surface)}
.inspector-application-form textarea{resize:vertical}
</style>
