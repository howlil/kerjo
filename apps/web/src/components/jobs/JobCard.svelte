<script>
  import Icon from '../Icon.svelte';
  import Badge from '../ui/Badge.svelte';
  import CompanyAvatar from '../ui/CompanyAvatar.svelte';

  let { job, selected = false, saved = false, onSelect, onSave, formatArea, formatRole, formatTime } = $props();
</script>

<article class="job-record" class:is-selected={selected} class:is-seen={!job.is_new}>
  <button type="button" class="job-record-main" onclick={() => onSelect(job)} aria-label={'Lihat detail ' + job.title} aria-current={selected ? 'true' : undefined}>
    <div class="job-record-top">
      <CompanyAvatar company={job.company} logo={job.company_logo} />
      <div class="job-record-heading">
        <h3>{job.title}</h3>
        <p title={job.company}>{job.company}</p>
      </div>
      {#if job.is_new}<span class="job-record-new">NEW</span>{/if}
    </div>
    <div class="job-record-tags">
      <Badge>{job.sources?.length > 1 ? job.sources.length + ' SITUS' : (job.source || 'PORTAL').toUpperCase()}</Badge>
      <Badge>{formatRole(job.role_category)}</Badge>
      {#if job.experience_level && job.experience_level !== 'unspecified'}
        <Badge tone="accent">{job.experience_level.toUpperCase()}</Badge>
      {/if}
    </div>
  </button>
  <div class="job-record-bottom">
    <Icon name="mapPin" size={12}/>
    <span class="job-record-location" title={job.location_raw || formatArea(job.area)}>{job.location_raw || formatArea(job.area)}</span>
    {#if job.salary}<span class="job-record-salary" title={job.salary}>{job.salary}</span>{/if}
    <span class="job-record-date">{formatTime(job.posted_at || job.first_seen_at)}</span>
  </div>
  <button type="button" class="ui-icon-button save-button" class:is-active={saved} onclick={() => onSave(job)} title={saved ? 'Hapus dari simpanan lokal' : 'Simpan posisi secara lokal'} aria-label={saved ? 'Hapus simpanan' : 'Simpan posisi'} aria-pressed={saved}>
    <Icon name="bookmark" size={15}/>
  </button>
</article>
