<script>
  let { variant = 'neutral', type = 'button', disabled = false, title = undefined, onclick = undefined, children, class: className = '' } = $props();
</script>

<button {type} {disabled} {title} {onclick} class="ui-button {variant === 'primary' ? 'is-primary' : ''} {className}">
  {@render children?.()}
</button>

<style>
  .ui-button{display:inline-flex;align-items:center;justify-content:center;gap:7px;min-height:34px;white-space:nowrap;border:0;border-radius:var(--radius-pill);padding:7px 12px;background:var(--control-surface);color:var(--color-text-body);font-size:12px;font-weight:500;transition:filter var(--duration-fast),transform var(--duration-fast)}
  .ui-button:hover{filter:brightness(.985)}
  .ui-button:active{transform:scale(.985)}
  .ui-button.is-primary{background:var(--control-primary);color:var(--control-primary-ink)}
</style>
