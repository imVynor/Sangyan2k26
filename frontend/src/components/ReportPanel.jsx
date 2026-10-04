import { formatAssessmentStatus } from './assessmentStatus'

export default function ReportPanel({ title, subtitle, entries = [], complete = false, onClose }) {
  return (
    <aside className="rp" aria-label={`${title} report`}>
      <div className="rph">
        <div>
          <h3>{title}</h3>
          <div className="mu">{subtitle}</div>
        </div>
        {onClose && (
          <button className="mz" type="button" onClick={onClose} aria-label="Close report">
            ×
          </button>
        )}
      </div>
      {entries.length === 0 && <p className="mu">No report details have been saved yet.</p>}
      {entries.map((entry, index) => (
        <section className="ri" key={`${entry.title}-${index}`}>
          <b>{entry.title}</b>
          {entry.title === 'Assessment' && entry.text.startsWith('Status: ') ? (
            <div className="report-assessment">
              <span className="assessment-status">{formatAssessmentStatus(entry.text.slice('Status: '.length))}</span>
            </div>
          ) : (
            <div>{entry.text}</div>
          )}
        </section>
      ))}
      <p className="mu">{complete ? 'Report complete.' : 'This report updates as you continue the guided workflow.'}</p>
      <button className="btn wide" type="button" onClick={() => window.print()}>
        Print / Save as PDF
      </button>
    </aside>
  )
}
