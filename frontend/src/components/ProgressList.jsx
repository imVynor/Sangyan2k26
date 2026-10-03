import { SECTIONS } from './data/flow'

// Progress bar + list of report sections (tick when the section has an entry)
export default function ProgressList({ entries, progress }) {
  return (
    <div className="t">
      <div className="bar"><div style={{ width: progress.percent + '%' }} /></div>
      <div className="mu" style={{ margin: '4px 8px 8px' }}>
        {progress.done} of {progress.total} report sections complete
      </div>
      <div className="tl">
        {SECTIONS.map((s) => {
          const ok = entries.some((e) => e.title === s.key)
          return <div key={s.key} className={`st ${ok ? 'done' : ''}`}>{ok ? '✓ ' : ''}{s.label}</div>
        })}
      </div>
    </div>
  )
}
