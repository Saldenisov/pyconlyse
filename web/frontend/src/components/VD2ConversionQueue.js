export default function VD2ConversionQueue({jobs=[]}) {
  if(!jobs.length)return null;
  const pending=jobs.filter(job=>['queued','processing'].includes(job.status));
  const failed=jobs.filter(job=>job.status==='failed');
  const processing=pending.find(job=>job.status==='processing');
  return <section className="vd2-conversion-queue" aria-label="H5 conversion queue">
    <details><summary>H5 · {processing?`${processing.sample_name} · ${processing.phase_label||processing.phase} converting`:pending.length?'Queued':'Complete'}
      {pending.length>1?` · ${pending.length-1} queued`:''}{failed.length?` · ${failed.length} failed`:''}</summary>
      {jobs.map(job=><div key={job.job_id} className={`is-${job.status}`}>
        <span>{job.sample_name} · {job.phase_label||job.phase}</span><strong>{job.status}</strong>
        {job.frame_count!=null&&<span>{job.frame_count} frames</span>}
      </div>)}
    </details>
    {failed.map(job=><p key={job.job_id} role="alert">{job.sample_name} · {job.phase_label||job.phase}: {job.error}</p>)}
  </section>;
}
