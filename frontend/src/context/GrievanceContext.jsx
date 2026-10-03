import { createContext, useContext, useState } from 'react'
import { FLOW, SECTIONS, DONE_MESSAGE } from '../components/data/flow'

const Ctx = createContext(null)
export const useGrievance = () => useContext(Ctx)

// Holds the CURRENT grievance: chat messages, report entries, which step we are on.
// Every component reads from here, so chat, sidebar progress and report panel stay in sync.
export function GrievanceProvider({ children }) {
  const [started, setStarted] = useState(false)
  const [title, setTitle] = useState('')
  const [messages, setMessages] = useState([]) // { from: 'ai' | 'user', text }
  const [entries, setEntries] = useState([]) // report entries { title, text }
  const [step, setStep] = useState(0) // index into FLOW
  const [reportOpen, setReportOpen] = useState(false)

  const isDone = step >= FLOW.length
  const stage = FLOW[Math.min(step, FLOW.length - 1)].stage
  const options = isDone ? [] : FLOW[step].options

  const done = SECTIONS.filter((s) => entries.some((e) => e.title === s.key)).length
  const progress = { done, total: SECTIONS.length, percent: Math.round((done / SECTIONS.length) * 100) }

  // Called from the home page when the user explains the problem
  const start = (text) => {
    setTitle(text)
    setMessages([{ from: 'user', text }, { from: 'ai', text: FLOW[0].ai }])
    setEntries([{ title: 'What happened', text }])
    setStep(0)
    setReportOpen(false)
    setStarted(true)
  }

  // Called when the user taps one of the quick-reply options
  const pick = (option) => {
    const cur = FLOW[step]
    const next = cur.next ? cur.next(option) : step + 1
    const reply = next < FLOW.length ? FLOW[next].ai : DONE_MESSAGE
    setMessages((m) => [...m, { from: 'user', text: option }, { from: 'ai', text: reply }])
    if (cur.entry && (!cur.entryIf || cur.entryIf(option))) setEntries((list) => [...list, cur.entry])
    setStep(next)
  }

  // Free-text doubts. TODO: send `text` + current step to your backend / AI and show its answer.
  const ask = (text) =>
    setMessages((m) => [
      ...m,
      { from: 'user', text },
      { from: 'ai', text: 'Good question. (Placeholder) The real answer will use your current step and report.' },
    ])

  return (
    <Ctx.Provider
      value={{ started, title, messages, entries, stage, options, progress, reportOpen, setReportOpen, start, pick, ask }}
    >
      {children}
    </Ctx.Provider>
  )
}