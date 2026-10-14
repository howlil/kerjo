<script>
  let { tone = 'neutral', children } = $props();
</script>
<span class="ui-badge" class:accent={tone === 'accent'} class:positive={tone === 'positive'}>{@render children?.()}</span>
<style>
.ui-badge{display:inline-flex;align-items:center;min-height:20px;border-radius:4px;padding:2px 6px;background:var(--color-surface-muted);color:var(--color-text-secondary);font:400 10px/16px var(--font-mono)}
.accent{background:var(--color-selected);color:var(--color-text-heading)}
.positive{background:var(--color-positive-surface);color:var(--color-positive-text)}
</style>
