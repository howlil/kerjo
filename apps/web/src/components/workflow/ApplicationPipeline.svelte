<script>
  let { applications = [], onStatusChange, formatTime } = $props();
  const stages = [
    ["applied","Applied"],["screening","Screening"],["interview","Interview"],
    ["offer","Offer"],["rejected","Rejected"],["withdrawn","Withdrawn"]
  ];
</script>

<section class="pipeline-page">
  <div class="pipeline-header">
    <div><h1>Application pipeline</h1><p>Pelacakan manual. Kerjo tidak otomatis mengirim lamaran.</p></div>
    <span class="pipeline-count">{applications.length} applications</span>
  </div>
  {#if applications.length === 0}
    <div class="pipeline-empty"><strong>Belum ada aplikasi</strong><p>Buka lowongan di Discover, lalu gunakan tombol Kelola lamaran.</p></div>
  {:else}
    <div class="pipeline-grid">
      {#each applications as app (app.job_id)}
        <article class="pipeline-card">
          <header>
            <div><h2>{app.title}</h2><p>{app.company} · {app.sources?.join(', ') || app.source}</p></div>
            <a href={app.url} target="_blank" rel="noopener noreferrer">Buka ↗</a>
          </header>
          <label class="pipeline-field">
            <span>Application status</span>
            <select value={app.status} onchange={e => onStatusChange(app,e.currentTarget.value)}>
              {#each stages as [key, label]}
                <option value={key}>{label}</option>
              {/each}
            </select>
          </label>
          {#if app.applied_at}<p class="pipeline-meta">Dilamar: {formatTime(app.applied_at)}</p>{/if}
          {#if app.follow_up_at}<p class="pipeline-meta">Follow-up: {formatTime(app.follow_up_at)}</p>{/if}
          {#if app.notes}<p class="pipeline-notes">{app.notes}</p>{/if}
        </article>
      {/each}
    </div>
  {/if}
</section>
<style>
.pipeline-page{padding:var(--space-5);max-width:1100px;margin:0 auto;width:100%}
.pipeline-header{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:20px;border-bottom:1px solid var(--color-border);padding-bottom:16px}
.pipeline-header h1{font-size:19px;font-weight:700;color:var(--color-text-heading)}
.pipeline-header p,.pipeline-meta,.pipeline-notes,.pipeline-empty p{font-size:12px;color:var(--color-text-muted)}
.pipeline-count{font:12px var(--font-mono);color:var(--color-text-secondary)}
.pipeline-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:12px}
.pipeline-card,.pipeline-empty{border:1px solid var(--color-border);border-radius:var(--radius-lg);background:var(--color-surface);padding:17px}
.pipeline-card header{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;margin-bottom:14px}
.pipeline-card h2{font-size:13px;font-weight:700;color:var(--color-text-heading)}
.pipeline-card header p{font-size:12px;color:var(--color-text-secondary)}
.pipeline-card header a{font-size:11px;text-decoration:underline;color:var(--color-text-secondary);white-space:nowrap}
.pipeline-field{display:grid;gap:6px;font-size:12px;color:var(--color-text-secondary)}
.pipeline-field select{width:100%;padding:8px;background:var(--color-page);border:1px solid var(--color-border);border-radius:var(--radius-md);color:var(--color-text-heading)}
.pipeline-meta{margin-top:8px}
.pipeline-notes{white-space:pre-wrap;border-top:1px solid var(--color-border);margin-top:11px;padding-top:11px;line-height:1.55}
.pipeline-empty{text-align:center;padding:60px 15px}.pipeline-empty strong{display:block;color:var(--color-text-heading);margin-bottom:6px}
</style>
