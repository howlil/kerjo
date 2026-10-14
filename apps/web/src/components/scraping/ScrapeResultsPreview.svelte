<script>
  import Icon from '../Icon.svelte';
  import Button from '../ui/Button.svelte';

  let { run = null, jobs = [], total = 0, loading = false, error = '',
        page = 0, pageSize = 60, source = 'all', query = '', sources = [],
        onSource = () => {}, onSearch = () => {}, onPage = () => {},
        onBack = () => {}, onDiscover = () => {}, onSave = () => {} } = $props();

  let chosenId = $state(null);
  let draftQuery = $state('');
  let selected = $derived(jobs.find(job => job.id === chosenId) || jobs[0] || null);
  let pages = $derived(Math.max(1, Math.ceil(total / pageSize)));
  let complete = $derived(jobs.filter(job => job.description_status === 'complete').length);
  let missing = $derived(jobs.filter(job => !job.description).length);

  function published(date) {
    if (!date) return 'Unknown';
    const parsed = new Date(date);
    return Number.isNaN(parsed.getTime()) ? 'Unknown' : parsed.toLocaleDateString('id-ID',{day:'numeric',month:'short',year:'numeric'});
  }
  function urlSafe(url) {
    try { const parsed = new URL(url); return ['https:', 'http:'].includes(parsed.protocol) ? url : null; } catch { return null; }
  }
  function submitSearch(event) { event.preventDefault(); onSearch(draftQuery.trim()); }
</script>

<section class="preview-workspace" aria-label="Scraping results preview">
  <header class="page-heading">
    <div><div class="ui-eyebrow">SCRAPING / RUN-SCOPED RESULTS</div><h1>Results preview</h1><p>Tinjau data terverifikasi dari satu scraping. Ini bukan daftar seluruh Discover.</p></div>
    <div class="heading-actions">
      <Button onclick={onBack}><Icon name="activity" size={14}/>Activity</Button>
      <Button variant="primary" onclick={onDiscover}><Icon name="briefcase" size={14}/>Open Discover</Button>
    </div>
  </header>

  <div class="context-strip">
    <div class="context-title"><span class="run-dot" class:running={run?.status==='running'}></span><strong>{run ? 'RUN #'+run.id : 'No run selected'}</strong><span class="meta">{run?.status || '—'}</span></div>
    <span class="meta">Verified publication date · 14-day rolling window</span>
    <span class="meta" style="margin-left:auto">Read-only run preview · Save to shortlist available</span>
  </div>

  <div class="summary">
    <div><span>Run matches</span><strong>{total}</strong><small>Saved to SQLite & linked to this run</small></div>
    <div><span>New inserts</span><strong>{run?.jobs_new || 0}</strong><small>Across all completed tasks</small></div>
    <div><span>Complete descriptions</span><strong>{complete}</strong><small>On this visible page</small></div>
    <div><span>Missing descriptions</span><strong>{missing}</strong><small>On this visible page</small></div>
  </div>

  <div class="preview-toolbar">
    <form onsubmit={submitSearch} class="search-form"><Icon name="search" size={14}/><input aria-label="Search previewed vacancies" type="search" placeholder="Title, company, or description…" bind:value={draftQuery}/><button type="submit">Search</button></form>
    <label class="source-filter"><span>Source</span><select aria-label="Filter preview source" value={source} onchange={event=>onSource(event.currentTarget.value)}>
      <option value="all">All sources</option>
      {#each sources as [id,name]}<option value={id}>{name}</option>{/each}
    </select></label>
    <span class="count">{total} jobs</span>
  </div>

  <div class="preview-body">
    <div class="results-list">
      {#if error}<div class="ui-empty" role="alert"><strong>Preview unavailable</strong>{error}</div>
      {:else if loading && jobs.length===0}<div class="ui-empty">Loading results…</div>
      {:else if !run}<div class="ui-empty"><strong>No run selected</strong>Jalankan scraping melalui halaman Scraping.</div>
      {:else if jobs.length===0}<div class="ui-empty"><strong>No verified vacancies for this run</strong>Source mungkin diblokir, data lama, tanggal posting tidak diketahui, atau tidak lolos klasifikasi. Lihat Activity untuk alasannya.</div>
      {:else}
        {#each jobs as job (job.id)}
          <button class="job-row" class:selected={selected?.id===job.id} onclick={() => chosenId=job.id}>
            <div class="job-top"><span class="job-title">{job.title}</span>{#if job.is_new}<span class="new-mark">NEW</span>{/if}</div>
            <div class="job-company">{job.company}</div>
            <div class="job-meta"><span>{job.source}</span><span>{job.area?.replace(/_/g,' ')}</span><span>{published(job.posted_at)}</span></div>
            <div class="job-foot">
              <span class:complete={job.description_status==='complete'} class:missing={!job.description} class="description-state">{job.description_status==='complete'?'Full description':job.description?'Partial description':'Description missing'}</span>
              {#if job.is_saved}<span class="saved-mark">Saved</span>{/if}
            </div>
          </button>
        {/each}
      {/if}
    </div>
    <aside class="job-inspector">
      {#if selected}
        <div class="inspector-scroll">
          <div class="ui-eyebrow">EXTRACTED RECORD · #{selected.id}</div>
          <h2>{selected.title}</h2>
          <p class="company">{selected.company}</p>
          <div class="tags">
            <span>{selected.source}</span><span>{selected.experience_level || 'unspecified'}</span><span>{selected.role_category?.replace(/_/g,' ') || 'uncategorized'}</span>
          </div>
          <dl>
            <div><dt>Location</dt><dd>{selected.location_raw || selected.area || 'Unknown'}</dd></div>
            <div><dt>Published</dt><dd>{published(selected.posted_at)}</dd></div>
            <div><dt>Description quality</dt><dd>{selected.description_status || (selected.description ? 'partial' : 'missing')}{#if selected.description_source} · {selected.description_source}{/if}</dd></div>
            {#if selected.salary}<div><dt>Salary</dt><dd>{selected.salary}</dd></div>{/if}
          </dl>
          <div class="description-heading">Job description</div>
          {#if selected.description}
            <div class="description">{selected.description}</div>
          {:else}
            <p class="empty-description">Sumber belum menyediakan deskripsi yang bisa diekstrak secara tepercaya. Kerjo tidak mengarang job description.</p>
          {/if}
        </div>
        <div class="inspector-actions">
          <Button onclick={() => onSave(selected)}>{selected.is_saved ? 'Remove saved' : 'Save job'}</Button>
          {#if urlSafe(selected.application_url || selected.url)}
            <a class="source-link" href={urlSafe(selected.application_url || selected.url)} target="_blank" rel="noopener noreferrer">Open source <Icon name="externalLink" size={13}/></a>
          {/if}
        </div>
      {:else}
        <div class="ui-empty">Select a job to inspect its extraction.</div>
      {/if}
    </aside>
  </div>
  <footer class="preview-footer">
    <span>Page {page + 1} of {pages} · {total} unique vacancies</span>
    <div><button disabled={page===0 || loading} onclick={() => {chosenId=null;onPage(page-1);}}>← Previous</button><button disabled={(page+1)*pageSize>=total || loading} onclick={() => {chosenId=null;onPage(page+1);}}>Next →</button></div>
  </footer>
</section>

<style>
.preview-workspace{height:100%;min-height:0;display:flex;flex-direction:column;background:var(--color-page)}
.page-heading{padding:17px var(--space-4);display:flex;justify-content:space-between;align-items:center;gap:16px;border-bottom:var(--workspace-rule)}
h1{font-size:20px;font-weight:650;letter-spacing:-.04em;margin:3px 0 5px}.page-heading p{font-size:12px;color:var(--color-text-secondary);margin:0}
.heading-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.context-strip{display:flex;align-items:center;gap:15px;min-height:41px;padding:0 var(--space-4);background:var(--color-surface);border-bottom:var(--workspace-rule);font-size:11px}
.context-title{display:flex;align-items:center;gap:8px}.run-dot{width:7px;height:7px;background:var(--color-border-strong);border-radius:50%}.run-dot.running{background:var(--color-positive-text)}
.meta{color:var(--color-text-muted);font-size:10px}
.summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-bottom:var(--workspace-rule)}
.summary>div{padding:12px var(--space-4);display:flex;flex-direction:column;gap:3px;border-right:var(--workspace-rule);min-width:0}
.summary>div:last-child{border-right:0}.summary span,.summary small{font-size:10px;color:var(--color-text-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.summary strong{font-size:22px;font-weight:640;letter-spacing:-.03em;font-variant-numeric:tabular-nums}
.preview-toolbar{display:flex;align-items:center;gap:15px;padding:8px var(--space-4);min-height:49px;border-bottom:var(--workspace-rule)}
.search-form{flex:1;min-width:110px;display:flex;align-items:center;gap:9px;color:var(--color-text-muted)}
.search-form input{width:100%;background:transparent;border:0;outline-offset:2px;color:var(--color-text-heading);font-size:12px}.search-form button{border:0;background:var(--color-surface-muted);border-radius:5px;padding:6px 9px;color:var(--color-text-heading);font-size:11px}
.source-filter{display:flex;align-items:center;gap:8px;color:var(--color-text-muted);font-size:11px}.source-filter select{background:transparent;color:var(--color-text-heading);border:0;max-width:146px;font-size:11px}.count{font:11px var(--font-mono);color:var(--color-text-muted)}
.preview-body{min-height:0;flex:1;display:grid;grid-template-columns:minmax(260px,45%) minmax(0,1fr)}
.results-list{min-height:0;overflow:auto;border-right:var(--workspace-rule)}
.job-row{width:100%;padding:14px var(--space-4);text-align:left;background:transparent;border:0;border-bottom:var(--workspace-rule);border-left:3px solid transparent;color:var(--color-text-heading)}
.job-row:hover{background:var(--color-surface-hover)}.job-row.selected{border-left-color:var(--color-accent);background:var(--color-selected)}
.job-top{display:flex;align-items:flex-start;justify-content:space-between;gap:9px}.job-title{font-size:13px;line-height:19px;font-weight:650;letter-spacing:-.01em}
.new-mark{font:600 10px var(--font-mono);color:var(--color-positive-text)}
.job-company{color:var(--color-text-secondary);font-size:12px;margin-top:4px}
.job-meta{display:flex;gap:10px;flex-wrap:wrap;margin-top:11px;font-size:10px;color:var(--color-text-muted);text-transform:capitalize}
.job-foot{display:flex;gap:9px;margin-top:10px;align-items:center}.description-state{font-size:10px;color:var(--color-text-secondary)}.description-state.complete{color:var(--color-positive-text)}.description-state.missing{color:#b28848}.saved-mark{font-size:10px;color:var(--color-text-heading);background:var(--color-surface-muted);padding:2px 6px;border-radius:4px}
.job-inspector{min-width:0;min-height:0;display:flex;flex-direction:column}
.inspector-scroll{padding:var(--space-5);overflow:auto;min-height:0;flex:1}
.inspector-scroll h2{font-size:21px;letter-spacing:-.04em;line-height:27px;margin:13px 0 4px}.company{font-size:13px;color:var(--color-text-secondary);margin:0}
.tags{display:flex;gap:5px;flex-wrap:wrap;margin:16px 0}.tags span{padding:4px 7px;background:var(--color-surface-muted);border-radius:4px;text-transform:capitalize;font-size:10px;color:var(--color-text-secondary)}
.inspector-scroll dl{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:16px 0 22px}.inspector-scroll dt{font-size:10px;color:var(--color-text-muted);margin-bottom:5px}.inspector-scroll dd{margin:0;font-size:12px;line-height:18px;overflow-wrap:anywhere}
.description-heading{font-size:11px;font-weight:650;border-bottom:var(--workspace-rule);padding-bottom:12px;margin-bottom:13px}.description{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.7;font-size:12px;color:var(--color-text-secondary)}.empty-description{font-size:12px;color:var(--color-text-muted);line-height:1.6}
.inspector-actions{border-top:var(--workspace-rule);padding:10px var(--space-4);display:flex;align-items:center;gap:8px}.inspector-actions>*{flex:1}.source-link{background:var(--color-text-heading);color:var(--color-page);display:inline-flex;align-items:center;justify-content:center;gap:6px;border-radius:var(--radius-pill);padding:9px 10px;font-size:12px;text-decoration:none}
.preview-footer{min-height:49px;border-top:var(--workspace-rule);padding:8px var(--space-4);display:flex;justify-content:space-between;align-items:center;gap:8px;color:var(--color-text-muted);font-size:11px}
.preview-footer>div{display:flex;gap:8px}.preview-footer button{background:var(--color-surface-muted);border:1px solid var(--color-divider);border-radius:5px;padding:7px 10px;font-size:11px;color:var(--color-text-heading)}.preview-footer button:disabled{opacity:.4}
@media(max-width:720px){.page-heading{flex-direction:column;align-items:flex-start}.context-strip .meta:last-child{display:none}.preview-body{grid-template-columns:1fr;overflow:auto}.results-list{min-height:200px;max-height:40vh;border-right:0;border-bottom:var(--workspace-rule)}.job-inspector{min-height:300px}.inspector-scroll{overflow:visible}.summary>div{padding:10px}.summary strong{font-size:20px}.source-filter span,.count{display:none}}
</style>