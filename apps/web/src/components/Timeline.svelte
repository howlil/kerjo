<script>
  import Icon from './Icon.svelte';

  let { job } = $props();

  function formatDateTime(isoStr) {
    if (!isoStr) return 'Tidak disebutkan';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString('id-ID', {
        day: 'numeric',
        month: 'short',
        year: 'numeric'
      }) + ' ' + d.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' });
    } catch {
      return isoStr;
    }
  }

  function getRelativeTime(isoStr) {
    if (!isoStr) return null;
    try {
      const d = new Date(isoStr);
      const diffMs = Date.now() - d.getTime();
      const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
      if (diffHours < 1) return 'Kurang dari 1 jam lalu';
      if (diffHours < 24) return `${diffHours} jam lalu`;
      const diffDays = Math.floor(diffHours / 24);
      if (diffDays === 1) return 'Kemarin';
      return `${diffDays} hari lalu`;
    } catch {
      return null;
    }
  }
</script>

<div class="relative pl-6 space-y-6 before:absolute before:left-[11px] before:top-2 before:bottom-2 before:w-[2px] before:bg-[var(--color-border)]">
  <!-- Step 1: Posting Date -->
  <div class="relative group">
    <div class="absolute -left-6 top-0.5 w-[22px] height-[22px] rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] flex items-center justify-center text-[var(--color-text-secondary)]">
      <Icon name="calendar" size={11} />
    </div>
    <div class="space-y-0.5">
      <div class="flex items-center gap-2">
        <span class="text-xs font-semibold text-[var(--color-text-heading)]">Diposting Perekrut</span>
        {#if getRelativeTime(job.posted_at)}
          <span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[var(--color-surface-muted)] text-[var(--color-text-muted)] border border-[var(--color-border)]">
            {getRelativeTime(job.posted_at)}
          </span>
        {/if}
      </div>
      <p class="text-[11px] font-mono text-[var(--color-text-secondary)]">
        {formatDateTime(job.posted_at || job.first_seen_at)}
      </p>
      <p class="text-[11px] text-[var(--color-text-muted)]">
        Terbit di platform {job.source || 'Portal Karir'}
      </p>
    </div>
  </div>

  <!-- Step 2: Discovered / Indexed -->
  <div class="relative group">
    <div class="absolute -left-6 top-0.5 w-[22px] height-[22px] rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] flex items-center justify-center text-[var(--color-text-secondary)]">
      <Icon name="clock" size={11} />
    </div>
    <div class="space-y-0.5">
      <div class="flex items-center gap-2">
        <span class="text-xs font-semibold text-[var(--color-text-heading)]">Ditemukan Scraper</span>
        {#if job.is_new}
          <span class="text-[10px] font-semibold px-2 py-0.2 rounded-full bg-[var(--color-highlight)] text-[#121212] border border-[var(--color-border-strong)]">
            NEW
          </span>
        {/if}
      </div>
      <p class="text-[11px] font-mono text-[var(--color-text-secondary)]">
        {formatDateTime(job.first_seen_at)}
      </p>
      <p class="text-[11px] text-[var(--color-text-muted)]">
        Otomatis di-indeks & diekstrak pengalamannya
      </p>
    </div>
  </div>

  <!-- Step 3: Current Status & Verification -->
  <div class="relative group">
    <div class="absolute -left-6 top-0.5 w-[22px] height-[22px] rounded-full border border-[var(--color-border-strong)] bg-[#ACE1AF]/20 flex items-center justify-center text-[#121212]">
      <span class="w-2 h-2 rounded-full bg-[#ACE1AF] animate-pulse"></span>
    </div>
    <div class="space-y-0.5">
      <div class="flex items-center gap-2">
        <span class="text-xs font-semibold text-[var(--color-text-heading)]">Status Loker</span>
        <span class="text-[10px] font-mono font-medium px-2 py-0.5 rounded-full bg-[#ACE1AF]/30 text-[#121212] border border-[#ACE1AF]">
          Aktif
        </span>
      </div>
      {#if job.experience_level && job.experience_level !== 'unspecified'}
        <div class="pt-1 flex flex-wrap gap-1.5 items-center">
          <span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[var(--color-accent-soft)] text-[var(--color-on-accent)] border border-[var(--color-accent)]">
            Level: {job.experience_level.toUpperCase()}
          </span>
          {#if job.experience_raw}
            <span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[var(--color-surface-muted)] text-[var(--color-text-secondary)] border border-[var(--color-border)]">
              Syarat: {job.experience_raw}
            </span>
          {/if}
        </div>
      {/if}
    </div>
  </div>
</div>
