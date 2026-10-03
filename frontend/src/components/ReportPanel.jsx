import { useNavigate, useParams } from 'react-router-dom'
import { SAMPLE_REPORTS } from './data/flow'
import ReportPanel from '../components/ReportPanel'

export default function ReportsPage() {
  const { id } = useParams() // from the URL /reports/:id
  const nav = useNavigate()
  const report = SAMPLE_REPORTS.find((r) => r.id === id)

  return (
    <>
      <main className="main">
        <div className="info">
          <h1>How reports are generated</h1>
          <ol>
            <li><b>You explain the problem.</b> Every answer you give in the chat becomes an entry.</li>
            <li><b>Entries are tagged to a stage:</b> Understand, Confirm, Explain, then each solution Part.</li>
            <li><b>The report grows live</b> while you complete each Part.</li>
            <li><b>When all Parts are done,</b> the report is ready to download and attach to your complaint.</li>
          </ol>
          <p className="mu">Select a report from the list on the left to open it here on the right.</p>
        </div>
      </main>
      {report && (
        <ReportPanel title={report.title} subtitle={`${report.date} · ${report.status}`}
          entries={report.entries} onClose={() => nav('/reports')} />
      )}
    </>
  )
}
