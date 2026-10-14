<script>
  let { job } = $props();
  function fullDate(value){
    if(!value)return 'Waktu tidak tersedia';
    const d=new Date(value);
    if(Number.isNaN(d.getTime()))return value;
    return d.toLocaleDateString('id-ID',{day:'numeric',month:'short',year:'numeric'})+' '+d.toLocaleTimeString('id-ID',{hour:'2-digit',minute:'2-digit'});
  }
</script>
<ol class="timeline">
  <li><strong>Diposting perekrut</strong><time>{fullDate(job.posted_at || job.first_seen_at)}</time><p>Platform {job.source || 'tidak diketahui'}</p></li>
  <li><strong>Ditemukan scraper</strong><time>{fullDate(job.first_seen_at)}</time><p>Posisi berhasil terindeks</p></li>
  <li class="timeline-current"><strong>Status dalam Kerjo</strong><time>{job.is_new ? 'Belum dilihat' : 'Sudah dilihat'}</time><p>Status live di portal sumber belum diverifikasi</p></li>
</ol>
<style>
.timeline{padding:0 0 0 24px;margin:0;list-style:none}
.timeline li{position:relative;padding-bottom:20px}
.timeline li:last-child{padding-bottom:0}
.timeline li:not(:last-child)::before{content:"";position:absolute;top:12px;bottom:0;left:-19px;border-left:1px solid var(--color-border)}
.timeline li::after{content:"";position:absolute;left:-23px;top:5px;width:9px;height:9px;border:2px solid var(--color-border-strong);background:var(--color-page);border-radius:50%}
.timeline li.timeline-current::after{background:var(--color-success);border-color:var(--color-positive-text)}
.timeline strong{display:block;font-size:12px;font-weight:600;color:var(--color-text-heading)}
.timeline time{display:block;margin-top:4px;font:400 11px/16px var(--font-mono);color:var(--color-text-muted)}
.timeline p{font-size:11px;line-height:16px;color:var(--color-text-secondary);margin-top:4px}
</style>
