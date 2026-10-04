import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { useAuth } from './AuthContext'
import { listGrievances, startAiGrievance, submitAiTurn } from '../services/api'
import { SECTIONS } from '../components/data/flow'

const Ctx = createContext(null)
export const useGrievance = () => useContext(Ctx)

export function GrievanceProvider({ children }) {
  const { user, loading: authLoading } = useAuth()
  const [loadedUserId, setLoadedUserId] = useState(null)
  const [storedGrievances, setStoredGrievances] = useState([])
  const [storedCurrent, setStoredCurrent] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [reportOpen, setReportOpen] = useState(false)

  useEffect(() => {
    let active = true
    if (authLoading || !user?.id) return () => { active = false }
    listGrievances()
      .then((records) => {
        if (!active) return
        setLoadedUserId(user.id)
        setStoredGrievances(records)
        setStoredCurrent(records[0] || null)
        setError('')
      })
      .catch((requestError) => {
        if (active) {
          setLoadedUserId(user.id)
          setError(requestError.message)
          setStoredGrievances([])
          setStoredCurrent(null)
        }
      })

    return () => {
      active = false
    }
  }, [authLoading, user])

  const loading = authLoading || Boolean(user?.id && loadedUserId !== user.id)
  const grievances = user?.id === loadedUserId ? storedGrievances : []
  const current = user?.id === loadedUserId ? storedCurrent : null

  const start = useCallback(async (text) => {
    setSaving(true)
    setError('')
    try {
      const saved = await startAiGrievance(text)
      setLoadedUserId(user.id)
      setStoredCurrent(saved)
      setStoredGrievances((records) => [saved, ...records])
      setReportOpen(false)
      return saved
    } catch (requestError) {
      setError(requestError.message)
      throw requestError
    } finally {
      setSaving(false)
    }
  }, [user])

  const ask = useCallback(async (text) => {
    if (!current || saving) return
    if (!current.ai_case_id) {
      setError('This saved report predates the AI assistant. Start a new grievance to continue with AI.')
      return false
    }
    setSaving(true)
    setError('')
    try {
      const result = await submitAiTurn(current.id, text)
      const saved = result.grievance
      setStoredCurrent(saved)
      setStoredGrievances((records) => [saved, ...records.filter((record) => record.id !== saved.id)])
      return true
    } catch (requestError) {
      setError(requestError.message)
      return false
    } finally {
      setSaving(false)
    }
  }, [current, saving])

  const open = useCallback((record) => {
    setStoredCurrent(record)
    setReportOpen(false)
  }, [])

  const entries = current?.entries || []
  const stage = 'AI-guided assessment'
  const done = SECTIONS.filter((section) => entries.some((entry) => entry.title === section.key)).length
  const progress = useMemo(
    () => ({ done, total: SECTIONS.length, percent: Math.round((done / SECTIONS.length) * 100) }),
    [done],
  )

  const value = {
    grievances,
    loading,
    saving,
    error,
    currentId: current?.id ?? null,
    started: current !== null,
    title: current?.title || '',
    messages: current?.messages || [],
    entries,
    stage,
    progress,
    canChat: Boolean(current?.ai_case_id),
    reportOpen,
    setReportOpen,
    start,
    ask,
    open,
  }

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
