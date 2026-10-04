import { formatAssessmentStatus } from './assessmentStatus'

const ASSESSMENT_MESSAGE = /^(?<finding>[\s\S]*?)\n\nStatus:\s*(?<status>[A-Z_]+)(?:\n\nTo assess this accurately, please clarify:\n(?<questions>[\s\S]*))?$/

export default function AssistantMessage({ text }) {
  const match = ASSESSMENT_MESSAGE.exec(text)
  if (!match?.groups) return <div className="m">{text}</div>

  const finding = match.groups.finding.replace(/^Current finding:\s*/, '')
  const questions = match.groups.questions
    ?.split('\n')
    .map((line) => line.replace(/^\s*-\s*/, '').trim())
    .filter(Boolean)

  return (
    <article className="m ai-message">
      <div className="ai-message-head">
        <strong>Assessment</strong>
        <span className="assessment-status">{formatAssessmentStatus(match.groups.status)}</span>
      </div>
      <p className="ai-finding">{finding}</p>
      {questions?.length > 0 && (
        <div className="ai-questions">
          <strong>To assess this accurately, please clarify:</strong>
          <ul>
            {questions.map((question, index) => <li key={`${question}-${index}`}>{question}</li>)}
          </ul>
        </div>
      )}
    </article>
  )
}
