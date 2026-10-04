import { useEffect, useRef } from 'react'
import { Navigate } from 'react-router-dom'
import { useGrievance } from '../../context/GrievanceContext'
import Composer from '../Composer'
import AssistantMessage from '../AssistantMessage'
import ReportPanel from '../ReportPanel'

export default function ChatPage() {
  const g = useGrievance()
  const bottom = useRef(null)

  // scroll to the newest message whenever messages change
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth' })
  }, [g.messages])

  if (g.loading) return <main className="main"><p className="mu">Loading your saved grievance…</p></main>
  if (!g.started) return <Navigate to="/" replace />

  return (
    <>
      <main className="main">
        <div className="vc">
          <div className="ph">
            <span>
              <b>{g.title.length > 34 ? g.title.slice(0, 34) + '…' : g.title}</b>
              <span className="mu"> · {g.stage}</span>
            </span>
            <button className="btn g mob" onClick={() => g.setReportOpen(true)}>📄 Report</button>
          </div>

          <div className="chat">
            {g.messages.map((m, i) => m.from === 'user'
              ? <div key={i} className="m u">{m.text}</div>
              : <AssistantMessage key={i} text={m.text} />)}
            <div ref={bottom} />
          </div>

          <div className="comp">
            {!g.canChat && <p className="mu">This is a legacy saved report. Start a new grievance to continue with the AI assistant.</p>}
            {g.error && <p role="alert" className="error">{g.error}</p>}
            <Composer placeholder="Ask a question or add details…" onSend={g.ask} disabled={g.saving || !g.canChat} maxLength={10000} />
          </div>
        </div>
      </main>

      {g.reportOpen && (
        <ReportPanel title="Current Report" subtitle="Updating live as you answer" entries={g.entries}
          complete={g.progress.percent === 100} onClose={() => g.setReportOpen(false)} />
      )}
    </>
  )
}