<script>
  let { header, filters, results, inspector, filterOpen = false, detailOpen = false, onDismiss = () => {} } = $props();
</script>
<div class="workspace" class:filters-open={filterOpen} class:details-open={detailOpen}>
  <header class="workspace-header">{@render header()}</header>
  <div class="workspace-body">
    <aside class="workspace-filter" aria-label="Filter lowongan">{@render filters()}</aside>
    <main class="workspace-results" aria-label="Hasil pencarian lowongan">{@render results()}</main>
    <aside class="workspace-inspector" aria-label="Detail lowongan">{@render inspector()}</aside>
  </div>
  {#if filterOpen || detailOpen}
    <button class="workspace-overlay" onclick={onDismiss} aria-label="Tutup panel"></button>
  {/if}
</div>
<style>
.workspace{height:100dvh;min-height:440px;width:100%;display:flex;flex-direction:column;overflow:hidden;background:var(--color-page)}
.workspace-header{height:var(--workspace-header-height);min-height:var(--workspace-header-height);border-bottom:var(--workspace-rule);display:flex;align-items:center;padding:0 var(--space-4);gap:var(--space-3)}
.workspace-body{display:grid;grid-template-columns:var(--workspace-sidebar-width) minmax(0,1fr) var(--workspace-inspector-width);flex:1;min-height:0;overflow:hidden}
.workspace-filter,.workspace-inspector{min-width:0;min-height:0;display:flex;flex-direction:column;background:var(--color-page)}
.workspace-filter{border-right:var(--workspace-rule)}
.workspace-inspector{border-left:var(--workspace-rule)}
.workspace-results{display:flex;flex-direction:column;min-width:0;min-height:0;overflow:hidden}
.workspace-overlay{display:none}
@media(min-width:1500px){.workspace{--workspace-sidebar-width:230px;--workspace-inspector-width:320px}}
@media(max-width:1150px){.workspace{--workspace-sidebar-width:205px;--workspace-inspector-width:275px}}
@media(max-width:900px){
  .workspace-body{grid-template-columns:205px minmax(0,1fr)}
  .workspace-inspector{position:absolute;top:var(--workspace-header-height);right:0;bottom:0;width:min(360px,86vw);z-index:25;transform:translateX(101%);transition:transform var(--duration-standard) var(--ease-standard);box-shadow:0 15px 38px transparent}
  .details-open .workspace-inspector{transform:translateX(0);box-shadow:0 15px 38px rgba(0,0,0,.15)}
  .workspace-overlay{display:block;position:absolute;inset:var(--workspace-header-height) 0 0;background:rgba(0,0,0,.23);border:0;z-index:20}
}
@media(max-width:620px){
  .workspace-body{grid-template-columns:minmax(0,1fr)}
  .workspace-header{padding:0 var(--space-3)}
  .workspace-filter{position:absolute;z-index:26;top:var(--workspace-header-height);bottom:0;left:0;width:min(265px,86vw);transform:translateX(-101%);transition:transform var(--duration-standard) var(--ease-standard);box-shadow:0 15px 38px transparent}
  .filters-open .workspace-filter{transform:translateX(0);box-shadow:0 15px 38px rgba(0,0,0,.15)}
}
@media(prefers-reduced-motion:reduce){.workspace-filter,.workspace-inspector{transition:none}}
</style>
