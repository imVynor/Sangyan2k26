import { useNavigate, useParams } from 'react-router-dom'
import { useGrievance } from '../../context/GrievanceContext'
import ReportPanel from '../ReportPanel'
import { FLOW } from '../data/flow'

function dateLabel(value) {
  return value ? new Date(value).toLocaleDateString() : 'Saved report'
}

export default function ReportsPage() {
  const { id } = useParams()
  const nav = useNavigate()
  const { grievances, loading, error } = useGrievance()
  const report = grievances.find((item) => String(item.id) === id)

  return (
    <>
      <main className="main">
        <div className="info">
          <h1>Your grievance reports</h1>
          <p className="mu">Reports and progress are saved to your account and can be reopened after signing in again.</p>
          {loading && <p className="mu">Loading your saved reports…</p>}
          {error && <p role="alert" className="error">{error}</p>}
          {!loading && grievances.length === 0 && !error && (
            <p className="mu">You have no saved reports yet. Start a new grievance from Home.</p>
          )}
          {report && (
            <p className="mu">{dateLabel(report.updated_at || report.created_at)} · {report.messages.length} conversation messages</p>
          )}
        </div>
      </main>
      {report && (
        <ReportPanel
          title={report.title}
          subtitle={dateLabel(report.updated_at || report.created_at)}
          entries={report.entries}
          complete={report.step >= FLOW.length}
          onClose={() => nav('/reports')}
        />
      )}
    </>
  )
}
