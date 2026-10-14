<script>
  import Icon from '../Icon.svelte';
  import Button from '../ui/Button.svelte';

  let { run = null, runs = [], events = [], sources = [], loading = false,
        error = '', onStart = () => {}, onChooseRun = () => {},
        onPreview = () => {}, onAddSearch = () => {} } = $props();

  let selectedSource = $state('all');
  let selectedLevel = $state('all');
  let search = $state('');
  let selectedEventId = $state(null);

  const finished = ['completed', 'partial', 'failed', 'skipped'];
  let isRunning = $derived(Boolean(run && ['queued', 'running'].includes(run.status)));
  let percent = $derived(run?.total_tasks ? Math.min(100, Math.round((run.processed_tasks || 0) / run.total_tasks * 100)) : 0);
  let currentEvents = $derived(events.filter(e =>
    (selectedSource === 'all' || e.source === selectedSource) &&
    (selectedLevel === 'all' || e.level === selectedLevel) &&
    (!search || (e.message + ' ' + e.source + ' ' + e.event_type).toLowerCase().includes(search.toLowerCase()))
  ));
  let selectedEvent = $derived(events.find(e => e.id === selectedEventId) || currentEvents[currentEvents.length - 1] || null);
  let usedSources = $derived(sources.map(([id, name]) => {
    const tasks = events.filter(e => e.source === id && e.event_type === 'source_task_completed');
    return { id, name, tasks: tasks.length, last: tasks[tasks.length - 1] || null };
  }));
  function time(value) {
    if (!value) return '—';
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleTimeString('id-ID', { hour:'2-digit', minute:'2-digit', second:'2-digit' });
  }
  function summaryMetric(field) { return run?.[field] ?? 0; }
</script>

<section class="scrape-workspace" aria-label="Scraping control and activity">
  <header class="page-heading">
    <div><div class="ui-eyebrow">COLLECTION / MANUAL</div><h1>Scraping</h1><p>Jalankan kolektor, pantau progres dan periksa aktivitas setiap sumber.</p></div>
    <div class="heading-actions">
      <Button onclick={onAddSearch}><Icon name="plus" size={13}/>Saved searches</Button>
      <Button variant="primary" onclick={onStart} disabled={isRunning}><Icon name="refresh" size={13}/>{isRunning ? 'Scraping…' : 'Start scraping'}</Button>
    </div>
  </header>

  <div class="run-strip">
    <div class="run-status"><span class:active={isRunning} class:warn={run?.status==='partial' || run?.status==='failed'} class="state-dot"></span>{run ? run.status.replace(/_/g,' ') : 'No runs yet'}</div>
    {#if run}<span class="mono secondary">RUN #{run.id}</span><span class="secondary">Manual · published within 14 days</span>{/if}
    <div class="grow"></div>
    {#if run}<span class="mono">{run.processed_tasks || 0}/{run.total_tasks || 0} tasks</span><div class="progress-track" role="progressbar" aria-valuenow={percent} aria-valuemin="0" aria-valuemax="100" aria-label="Scraping progress"><div class="progress-fill" style:width={percent+'%'}></div></div><span class="mono">{percent}%</span>{/if}
  </div>

  <div class="metrics">
    {#each [
      ['Candidates','jobs_found','Raw source matches'],
      ['Recent','jobs_recent','Verified date'],
      ['New','jobs_new','Inserted records'],
      ['Excluded',null,'Old / undated / future'],
      ['Details','details_enriched','Enrichment attempts'],
      ['Errors','errors','Task failures']
    ] as [label,key,hint]}
      <div class="metric"><span>{label}</span><strong>{key ? summaryMetric(key) : summaryMetric('filtered_old') + summaryMetric('filtered_unknown') + summaryMetric('filtered_future')}</strong><small>{hint}</small></div>
    {/each}
  </div>

  <div class="activity-layout">
    <aside class="source-panel">
      <div class="panel-heading"><strong>Sources</strong><span>{usedSources.filter(s => s.tasks > 0).length}/{sources.length}</span></div>
      <div class="scroll-panel">
        <button class="source-row" class:selected={selectedSource === 'all'} onclick={() => selectedSource = 'all'}><span class="source-initial">∑</span><span class="source-name">All sources</span><span class="source-count">{events.length}</span></button>
        {#each usedSources as source (source.id)}
          <button class="source-row" class:selected={selectedSource === source.id} onclick={() => selectedSource = source.id}>
            <span class="source-initial">{source.name.slice(0,2).toUpperCase()}</span><span class="source-name">{source.name}<small>{source.tasks ? (source.last?.metrics?.status || 'processed') : 'No tasks reported'}</small></span>
            <span class="source-count">{source.tasks}</span>
          </button>
        {/each}
      </div>
      <div class="foot-note">No automatic schedule · Max 4 concurrent source workers</div>
    </aside>

    <div class="log-panel">
      <div class="panel-heading"><strong>Activity log</strong><span class="mono">{currentEvents.length} events</span></div>
      <div class="log-toolbar">
        <div class="level-filters">
          {#each [['all','All'],['success','Success'],['warning','Warning'],['error','Error']] as [key,label]}
            <button class:chosen={selectedLevel===key} onclick={() => selectedLevel=key}>{label}</button>
          {/each}
        </div>
        <input aria-label="Search activity log" type="search" placeholder="Find event…" bind:value={search}/>
      </div>
      <div class="scroll-panel event-list" role="log" aria-label="Run activity events">
        {#if error}<div class="ui-empty" role="alert"><strong>Could not load activity</strong>{error}</div>
        {:else if !run}<div class="ui-empty"><strong>No scraping activity yet</strong>Mulai manual scraping untuk membuat riwayat run.</div>
        {:else if loading && events.length===0}<div class="ui-empty">Loading events…</div>
        {:else if currentEvents.length === 0}<div class="ui-empty"><strong>No matching events</strong>Ubah source atau filter level. Event lama sebelum fitur ini dibuat tidak memiliki log terperinci.</div>
        {:else}
          {#each currentEvents as event (event.id)}
            <button class="event-row" class:selected={selectedEvent?.id===event.id} onclick={() => selectedEventId=event.id}>
              <span class="event-time mono">{time(event.created_at)}</span><span class="event-dot" class:ok={event.level==='success'} class:warning={event.level==='warning'} class:error={event.level==='error'}></span>
              <span class="event-copy"><strong>{event.source==='system'?'Worker':sources.find(s=>s[0]===event.source)?.[1] || event.source}</strong> · {event.message}<small>{event.event_type.replace(/_/g,' ')}{#if event.metrics?.keyword} · {event.metrics.keyword}{/if}</small></span>
            </button>
          {/each}
        {/if}
      </div>
      <div class="panel-footer"><span>Event log tersimpan per run · polling 2.5s saat aktif</span></div>
    </div>

    <aside class="inspector-panel">
      <div class="panel-heading"><strong>Inspector</strong><span class="mono">{selectedEvent ? '#'+selectedEvent.id : '—'}</span></div>
      <div class="scroll-panel inspector-content">
        {#if selectedEvent}
          <div class="ui-eyebrow">{selectedEvent.level} / {selectedEvent.event_type}</div>
          <h2>{selectedEvent.source}</h2><p>{selectedEvent.message}</p>
          <dl>
            <div><dt>Time</dt><dd>{time(selectedEvent.created_at)}</dd></div>
            {#each Object.entries(selectedEvent.metrics || {}).filter(([_,value]) => value !== null && value !== '') as [key,value]}
              <div><dt>{key.replace(/_/g,' ')}</dt><dd>{String(value)}</dd></div>
            {/each}
          </dl>
        {:else}
          <div class="inspector-empty">Pilih event untuk melihat detail task, durasi, dan alasan filtering.</div>
        {/if}
      </div>
    </aside>
  </div>
  <footer class="run-footer">
    <div class="history"><span class="ui-eyebrow">RUN HISTORY</span>
      {#each runs.slice(0,8) as item (item.id)}
        <button class:chosen={run?.id===item.id} onclick={() => {selectedEventId=null;onChooseRun(item.id);}} title={item.status}>#{item.id} <span>{item.status}</span></button>
      {/each}
      {#if runs.length===0}<span class="secondary">No previous runs</span>{/if}
    </div>
    <Button onclick={onPreview} disabled={!run}><Icon name="chevronRight" size={13}/>Preview results</Button>
  </footer>
</section>

<style>
.scrape-workspace{height:100%;min-height:0;display:flex;flex-direction:column;background:var(--color-page);color:var(--color-text-heading)}
.page-heading{padding:17px var(--space-4);display:flex;justify-content:space-between;gap:16px;align-items:center;border-bottom:var(--workspace-rule)}
h1{font-size:20px;font-weight:650;letter-spacing:-.04em;margin:3px 0 5px}.page-heading p{color:var(--color-text-secondary);font-size:12px;margin:0}
.heading-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.run-strip{height:44px;min-height:44px;padding:0 var(--space-4);display:flex;align-items:center;gap:12px;border-bottom:var(--workspace-rule);font-size:11px}
.run-status{text-transform:capitalize;font-weight:650;display:flex;align-items:center;gap:7px;white-space:nowrap}
.state-dot{height:7px;width:7px;border-radius:50%;background:var(--color-border-strong)}.state-dot.active{background:var(--color-positive-text)}.state-dot.warn{background:#b9893e}
.secondary{color:var(--color-text-muted)}.mono{font-family:var(--font-mono);font-size:11px}.grow{flex:1}
.progress-track{background:var(--color-surface-muted);height:4px;min-width:80px;width:12%;border-radius:5px;overflow:hidden}
.progress-fill{background:var(--color-accent);height:100%;transition:width .2s}
.metrics{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));border-bottom:var(--workspace-rule)}
.metric{padding:12px var(--space-4);border-right:var(--workspace-rule);display:flex;flex-direction:column;gap:2px;min-width:0}
.metric:last-child{border-right:0}.metric span,.metric small{font-size:10px;color:var(--color-text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.metric strong{font-size:23px;font-weight:630;letter-spacing:-.04em;font-variant-numeric:tabular-nums}
.activity-layout{display:grid;grid-template-columns:185px minmax(0,1fr) 250px;min-height:0;flex:1}
.source-panel,.log-panel,.inspector-panel{display:flex;flex-direction:column;min-height:0;min-width:0}
.source-panel{border-right:var(--workspace-rule)}.inspector-panel{border-left:var(--workspace-rule)}
.panel-heading{height:43px;min-height:43px;border-bottom:var(--workspace-rule);padding:0 var(--space-3);display:flex;align-items:center;justify-content:space-between;gap:8px}
.panel-heading strong{font-size:12px;font-weight:600}.panel-heading span{color:var(--color-text-muted);font-size:10px}
.scroll-panel{flex:1;min-height:0;overflow:auto;overscroll-behavior:contain}
.source-row{width:100%;display:flex;align-items:center;text-align:left;gap:8px;border:0;background:transparent;padding:10px var(--space-3);border-left:2px solid transparent}
.source-row:hover,.event-row:hover{background:var(--color-surface-hover)}.source-row.selected,.event-row.selected{background:var(--color-selected);border-left-color:var(--color-accent)}
.source-initial{width:24px;height:24px;flex:none;background:var(--color-surface-muted);border-radius:5px;display:grid;place-items:center;font-size:10px;font-weight:650}
.source-name{font-size:11px;min-width:0;flex:1;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
.source-name small{display:block;font-size:10px;color:var(--color-text-muted);margin-top:3px}
.source-count{font:10px var(--font-mono);color:var(--color-text-muted)}
.foot-note{padding:12px;font-size:10px;line-height:16px;color:var(--color-text-muted);border-top:var(--workspace-rule)}
.log-toolbar{display:flex;gap:8px;align-items:center;justify-content:space-between;padding:7px 10px;border-bottom:var(--workspace-rule)}
.level-filters{display:flex;gap:2px}.level-filters button{background:transparent;border:0;border-radius:4px;font-size:10px;padding:5px 7px;color:var(--color-text-secondary)}.level-filters button.chosen{background:var(--color-surface-muted);color:var(--color-text-heading);font-weight:600}
.log-toolbar input{width:104px;min-width:65px;border:0;background:transparent;color:var(--color-text-body);font-size:11px;outline-offset:2px}
.event-row{width:100%;display:grid;grid-template-columns:61px 7px minmax(0,1fr);gap:10px;padding:11px var(--space-3);border:0;border-bottom:var(--workspace-rule);border-left:2px solid transparent;background:transparent;text-align:left;color:var(--color-text-body)}
.event-time{color:var(--color-text-muted);font-size:10px}.event-dot{width:7px;height:7px;border-radius:50%;margin-top:4px;background:var(--color-accent)}.event-dot.ok{background:var(--color-positive-text)}.event-dot.warning{background:#c49a4f}.event-dot.error{background:#bc6565}
.event-copy{font-size:11px;line-height:17px;overflow-wrap:anywhere}.event-copy strong{font-weight:650}.event-copy small{display:block;color:var(--color-text-muted);margin-top:3px;font-size:10px}
.panel-footer{padding:10px var(--space-3);border-top:var(--workspace-rule);font-size:10px;color:var(--color-text-muted)}
.inspector-content{padding:var(--space-4)}.inspector-content h2{font-size:16px;margin:9px 0}.inspector-content p{font-size:12px;line-height:1.6;color:var(--color-text-secondary);overflow-wrap:anywhere}
.inspector-content dl{margin-top:14px}.inspector-content dl div{padding:9px 0;border-top:var(--workspace-rule)}dt{font-size:10px;color:var(--color-text-muted);text-transform:capitalize;margin-bottom:5px}dd{margin:0;font-size:11px;overflow-wrap:anywhere}.inspector-empty{color:var(--color-text-muted);font-size:12px;line-height:1.6}
.run-footer{border-top:var(--workspace-rule);min-height:52px;display:flex;align-items:center;justify-content:space-between;padding:7px var(--space-3);gap:10px}
.history{display:flex;align-items:center;flex-wrap:wrap;gap:5px}.history .ui-eyebrow{margin-right:8px}.history button{border:1px solid var(--color-divider);border-radius:5px;background:transparent;padding:6px 8px;font-size:10px;color:var(--color-text-secondary)}.history button.chosen{background:var(--color-selected);color:var(--color-text-heading)}
.history button span{color:var(--color-text-muted);text-transform:capitalize}
@media(max-width:960px){.activity-layout{grid-template-columns:158px minmax(0,1fr)}.inspector-panel{display:none}.metric{padding:10px}.history button span{display:none}}
@media(max-width:620px){.page-heading{align-items:flex-start;flex-direction:column}.activity-layout{display:flex;flex-direction:column}.source-panel{flex:none;border-right:0;border-bottom:var(--workspace-rule)}.source-panel>.scroll-panel{display:flex;overflow-x:auto;max-height:64px}.source-row{width:124px;flex:none}.source-panel .foot-note{display:none}.log-panel{flex:1;min-height:250px}.metrics{grid-template-columns:repeat(3,1fr)}.metric:nth-child(3){border-right:0}.metric:nth-child(-n+3){border-bottom:var(--workspace-rule)}.secondary:not(.mono){display:none}.run-strip{gap:7px;padding:0 10px}.run-footer{align-items:flex-start;flex-direction:column}}
</style>