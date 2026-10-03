import { useState } from 'react'

// Reusable input box (used on Home and inside Chat). Controlled input = value + onChange.
export default function Composer({ placeholder, onSend }) {
  const [text, setText] = useState('')
  const send = () => {
    const t = text.trim()
    if (!t) return
    onSend(t)
    setText('')
  }
  return (
    <div className="ib">
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && send()}
        placeholder={placeholder}
      />
      <button className="btn" onClick={send}>➤</button>
    </div>
  )
}