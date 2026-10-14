<script>
  let { company = '', logo = null, size = 32 } = $props();
  let failed = $state(false);
  const letter = $derived((company.replace(/^PT\.?\s+/i, '').trim() || 'J').charAt(0).toUpperCase());
</script>
<span class="company-avatar" style:width={size + 'px'} style:height={size + 'px'}>
  {#if logo && !failed}
    <img src={logo} alt="" loading="lazy" onerror={() => (failed = true)} />
  {:else}
    <span aria-hidden="true">{letter}</span>
  {/if}
</span>
<style>
.company-avatar{display:grid;place-items:center;flex:none;overflow:hidden;border:1px solid var(--color-divider);border-radius:var(--radius-md);background:var(--color-surface);color:var(--color-text-secondary);font-size:13px;font-weight:600}
.company-avatar img{width:100%;height:100%;object-fit:contain;padding:2px}
</style>
