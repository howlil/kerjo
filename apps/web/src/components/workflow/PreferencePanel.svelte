<script>
  let { preferences, roles, areas, sources = [], onChange, onSave, formatTime } = $props();
  const arrangements = ["onsite","hybrid","remote"];
  function toggle(field,value) {
    const previous = preferences[field] || [];
    onChange({...preferences,[field]:previous.includes(value) ?
      previous.filter(x=>x!==value):[...previous,value]});
  }
  function setYears(value) {
    onChange({...preferences,max_required_years:value===""?null:Number(value)});
  }
  function setKeywords(value) {
    onChange({...preferences,keywords:value.split(",").map(x=>x.trim()).filter(Boolean)});
  }
</script>
<div class="preferences-page">
  <header><h1>Preferences & sources</h1><p>Atur target pencarian manual. Discover hanya menampilkan lowongan yang dipublikasikan dalam 14 hari terakhir.</p></header>
  <section class="preferences-section">
    <h2>Target role</h2>
    <div class="preference-options">
      {#each roles.filter(r=>r.id!=="all") as role}
        <button type="button" class:active={preferences.role_categories?.includes(role.id)} onclick={()=>toggle("role_categories",role.id)}>{role.label}</button>
      {/each}
    </div>
  </section>
  <section class="preferences-section">
    <h2>Area yang diinginkan</h2>
    <div class="preference-options">
      {#each areas.filter(a=>a.id!=="all") as area}
        <button type="button" class:active={preferences.areas?.includes(area.id)} onclick={()=>toggle("areas",area.id)}>{area.label}</button>
      {/each}
    </div>
  </section>
  <section class="preferences-section">
    <h2>Work arrangement</h2>
    <div class="preference-options">
      {#each arrangements as mode}
        <button type="button" class:active={preferences.work_modes?.includes(mode)} onclick={()=>toggle("work_modes",mode)}>{mode}</button>
      {/each}
    </div>
  </section>
  <section class="preferences-section preference-fields">
    <label>Max. minimum experience (years)
      <input type="number" min="0" max="50" step="0.5" value={preferences.max_required_years ?? ""}
        oninput={e=>setYears(e.currentTarget.value)}/>
    </label>
    <label>Relevant skills (comma-separated)
      <input type="text" placeholder="Go, SQL, Java" value={(preferences.keywords||[]).join(", ")}
        onchange={e=>setKeywords(e.currentTarget.value)}/>
    </label>
  </section>
  <button type="button" class="preferences-save" onclick={onSave}>Simpan preferensi</button>
  <section class="preferences-section source-list">
    <h2>Provider health</h2>
    <p>Riwayat hasil scraping manual. Dihitung dari tanggal publikasi, bukan waktu pertama ditemukan.</p>
    {#if !sources.length}<p>Belum ada riwayat scraping.</p>{/if}
    {#each sources as source}
      <div class="source-row"><strong>{source.source}</strong><span>{source.status} · {source.jobs_recent || 0} dalam 14 hari · {source.filtered_old || 0} lama · {source.filtered_unknown || 0} tanpa tanggal · {formatTime(source.ran_at)}</span></div>
    {/each}
  </section>
</div>
<style>
.preferences-page{max-width:920px;width:100%;margin:0 auto;padding:var(--space-5);color:var(--color-text-heading)}
.preferences-page header{margin-bottom:22px}.preferences-page h1{font-size:19px;font-weight:700}
.preferences-page header p,.source-list p{font-size:12px;color:var(--color-text-muted);margin-top:4px}
.preferences-section{border-top:1px solid var(--color-border);padding:17px 0}
.preferences-section h2{font-weight:700;font-size:12px;margin-bottom:10px}
.preference-options{display:flex;gap:8px;flex-wrap:wrap}
.preference-options button,.preferences-save{font-size:12px;border:1px solid var(--color-border-strong);background:var(--color-surface);border-radius:var(--radius-md);color:var(--color-text-heading);padding:7px 11px;cursor:pointer}
.preference-options button.active,.preferences-save{background:var(--color-text-heading);color:var(--color-page)}
.preference-fields{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.preference-fields label{font-size:12px;font-weight:600;display:grid;gap:7px}
.preference-fields input{padding:9px;border:1px solid var(--color-border);border-radius:var(--radius-md);background:var(--color-surface);color:var(--color-text-heading)}
.source-list{margin-top:30px}.source-row{display:flex;justify-content:space-between;gap:15px;padding:11px 0;border-bottom:1px solid var(--color-border);font-size:12px}
.source-row span{color:var(--color-text-secondary)}
@media(max-width:620px){.preference-fields{grid-template-columns:1fr}.preferences-page{padding:15px}}
</style>
