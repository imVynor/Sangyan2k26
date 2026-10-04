import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useGrievance } from '../context/GrievanceContext'
import { FLOW, STAGES } from './data/flow'
import ProgressList from './ProgressList'
import { checkBackendHealth } from '../services/api'

function Item({ icon, label, onClick, active, extra }) {
  return (
    <button className={`nav ${active ? 'on' : ''}`} onClick={onClick} type="button">
      <i>{icon}</i>
      <span className="t">{label}{extra}</span>
    </button>
  )
}

function recordStatus(record) {
  if (record.step >= FLOW.length) return 'Complete'
  return STAGES[FLOW[Math.min(record.step, FLOW.length - 1)].stage]
}

export default function Sidebar() {
  const { user, logout } = useAuth()
  const g = useGrievance()
  const nav = useNavigate()
  const { pathname } = useLocation()
  const [min, setMin] = useState(window.innerWidth < 820)
  const [query, setQuery] = useState('')
  const [online, setOnline] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    checkBackendHealth().then((health) => {
      if (active) setOnline(health.connected)
    })
    return () => {
      active = false
    }
  }, [])

  const mode = pathname.startsWith('/chat') ? 'chat' : pathname.startsWith('/reports') ? 'reports' : 'home'
  const openId = pathname.split('/')[2]
  const filtered = g.grievances.filter((record) => record.title.toLowerCase().includes(query.toLowerCase()))
  const displayName = user.name || user.username || user.email

  const openReport = (record) => {
    g.open(record)
    nav(`/reports/${record.id}`)
  }

  const signOut = async () => {
    setError('')
    try {
      await logout()
      nav('/login', { replace: true })
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  return (
    <aside className={`rail ${min ? 'min' : ''}`}>
      <div className="hd">
        <div className="av">{displayName[0].toUpperCase()}</div>
        <b className="t">{displayName}</b>
        <button className="mz" onClick={() => setMin(!min)} title="Minimise sidebar" type="button">
          {min ? '»' : '«'}
        </button>
      </div>

      {mode === 'home' && (
        <>
          <input
            className="t"
            placeholder="🔍 Search grievances"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            style={{ margin: '0 0 8px' }}
          />
          <Item icon="＋" label="New Grievance" active onClick={() => nav('/')} />
          <Item icon="📄" label="Reports" onClick={() => nav('/reports')} />
          <div className="lbl t">Recent</div>
          <div className="t">
            {filtered.slice(0, 5).map((record) => (
              <button key={record.id} className="rc report-link" onClick={() => openReport(record)} type="button">
                {record.title}<small>{recordStatus(record)}</small>
              </button>
            ))}
            {!g.loading && filtered.length === 0 && <div className="rc mu">No saved grievances</div>}
          </div>
        </>
      )}

      {mode === 'reports' && (
        <>
          <Item icon="🏠" label="Home" onClick={() => nav('/')} />
          <Item icon="＋" label="New Grievance" onClick={() => nav('/')} />
          <div className="lbl t">Reports</div>
          <div className="t">
            {g.grievances.map((record) => (
              <button
                key={record.id}
                className={`rc report-link ${String(record.id) === openId ? 'on' : ''}`}
                onClick={() => openReport(record)}
                type="button"
              >
                {record.title}<small>{recordStatus(record)}</small>
              </button>
            ))}
            {!g.loading && g.grievances.length === 0 && <div className="rc mu">No saved reports</div>}
          </div>
        </>
      )}

      {mode === 'chat' && (
        <>
          <Item icon="🏠" label="Home" onClick={() => nav('/')} />
          <Item icon="＋" label="New Grievance" onClick={() => nav('/')} />
          <Item icon="↩" label="Back to Query" active={!g.reportOpen} onClick={() => g.setReportOpen(false)} />
          <Item
            icon="📄"
            label="Current Report"
            active={g.reportOpen}
            onClick={() => g.setReportOpen(true)}
            extra={<span className="mu"> {g.progress.percent}%</span>}
          />
          <div className="lbl t">Report progress</div>
          <ProgressList entries={g.entries} progress={g.progress} />
          {g.grievances.length > 1 && (
            <>
              <div className="lbl t">Saved grievances</div>
              {g.grievances.filter((record) => record.id !== g.currentId).slice(0, 5).map((record) => (
                <button
                  key={record.id}
                  className="rc report-link"
                  onClick={() => {
                    g.open(record)
                    nav('/chat')
                  }}
                  type="button"
                >
                  {record.title}<small>{recordStatus(record)}</small>
                </button>
              ))}
            </>
          )}
        </>
      )}

      <div className="t sidebar-footer">
        {error && <div role="alert" className="error">{error}</div>}
        <Item icon="↪" label="Log out" onClick={() => void signOut()} />
      </div>
      <div className="sbfoot t">
        <span className={`dot ${online ? 'on' : ''}`} /> Backend {online ? 'connected' : 'offline'}
      </div>
    </aside>
  )
}
