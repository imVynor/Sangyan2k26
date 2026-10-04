import { useState } from 'react'

// Reusable input box (used on Home and inside Chat). Controlled input = value + onChange.
export default function Composer({ placeholder, onSend, disabled = false, maxLength }) {
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const send = async () => {
    const t = text.trim()
    if (!t || disabled || sending) return
    setSending(true)
    try {
      const sent = await onSend(t)
      if (sent === false) return
      setText('')
    } finally {
      setSending(false)
    }
  }
  return (
    <div className="ib">
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            void send()
          }
        }}
        placeholder={placeholder}
        disabled={disabled || sending}
        maxLength={maxLength}
      />
      <button className="btn" type="button" onClick={() => void send()} disabled={disabled || sending}>➤</button>
    </div>
  )
}