export const STAGES = ['Understand', 'Confirm', 'Explain', 'Part 1', 'Part 2', 'Part 3']

export const EXAMPLES = [
  'My broker deducted ₹2,000 and I do not know why',
  'Shares missing after transfer to my demat account',
  'Broker is not responding to my complaint',
]

// Report sections. A section is complete when an entry with title === key exists.
// Rename / add sections here once your team finalises the report format.
export const SECTIONS = [
  { label: 'Problem details', key: 'Prior action' },
  { label: 'Confirmed summary', key: 'Confirmed summary' },
  { label: 'Technical basis', key: 'Technical basis' },
  { label: 'Solution flow', key: 'Solution flow' },
  { label: 'Part 1 – Evidence', key: 'Part 1 – Evidence' },
  { label: 'Part 2 – Complaint', key: 'Part 2 – Complaint' },
  { label: 'Part 3 – Escalation', key: 'Part 3 – Escalation' },
]

const finished = (o) => o.includes('finished')

// Scripted conversation for the demo (broker-deduction case). Later this comes from your backend / AI.
// stage = index in STAGES; entry = report entry added when the step is answered.
export const FLOW = [
  { stage: 0, ai: 'I am sorry about that. On which date and for what amount was the money deducted?',
    options: ['20 Sept, ₹2,000'], entry: { title: 'When & amount', text: '20 Sept · ₹2,000 deducted by broker' } },
  { stage: 0, ai: 'Did you receive any contract note, SMS or email explaining the charge? And have you already contacted the broker?',
    options: ['No explanation, and I have not contacted them'], entry: { title: 'Prior action', text: 'No explanation received; broker not yet contacted' } },
  { stage: 1, ai: 'Here is what I understood: your broker deducted ₹2,000 from your account on 20 September, you received no explanation, and you have not contacted them yet. Is this correct?',
    options: ['Yes, correct', 'I want to change something'],
    entry: { title: 'Confirmed summary', text: 'Understanding verified by user' },
    entryIf: (o) => o.startsWith('Yes'), next: (o) => (o.startsWith('Yes') ? 3 : 0) },
  { stage: 2, ai: 'What this means: any charge should normally trace back to terms you agreed to, such as your account-opening documents, and be itemised in a contract note or ledger. Right now we know there is a debit, but we do not yet know whether this charge was disclosed. So your claim is unverified, and the current assessment is: insufficient information. This is guidance, not legal advice.',
    options: ['Show me the solution flow'], entry: { title: 'Technical basis', text: 'Charge must trace to disclosed terms; disclosure not yet verified' } },
  { stage: 2, ai: 'Here is your full flow:\n1. Part 1 – Collect evidence (ledger/statement, contract note, fee schedule)\n2. Part 2 – Written complaint to your broker\n3. Part 3 – Escalate if unresolved',
    options: ['Start Part 1'], entry: { title: 'Solution flow', text: '3 parts: Evidence → Broker complaint → Escalation' } },
  { stage: 3, ai: 'Part 1: Collect evidence. Download the ledger or account statement showing the ₹2,000 debit, any contract note for that date, and the fee schedule from your account-opening documents. Ask me why any document matters.',
    options: ['Why do I need the contract note?', "I've finished Part 1"],
    entry: { title: 'Part 1 – Evidence', text: 'Statement, contract note and fee schedule collected ✔' },
    entryIf: finished, next: (o) => (finished(o) ? 7 : 6) },
  { stage: 3, ai: 'A contract note itemises charges for a trade, so it helps show whether this ₹2,000 was disclosed. If no contract note exists for that date, say so in your complaint and ask the broker for the basis of the charge.',
    options: ["I've finished Part 1"], entry: { title: 'Part 1 – Evidence', text: 'Statement, contract note and fee schedule collected ✔' } },
  { stage: 4, ai: '✅ Part 1 complete. Part 2: Complain to your broker in writing. I can draft it from your report.',
    options: ['Show draft complaint'] },
  { stage: 4, ai: "Draft complaint:\n\nSubject: Unexplained deduction of ₹2,000 on 20 September\nDear Sir/Madam, ₹2,000 was deducted from my account on 20 September and I could not identify the reason. Please share the basis of this charge and the disclosure or contract note supporting it, and reverse it if it is not applicable. Account statement attached.\nRegards, [Your name]",
    options: ["I've sent the complaint"], entry: { title: 'Part 2 – Complaint', text: 'Written complaint sent to broker with statement attached ✔' } },
  { stage: 5, ai: "✅ Part 2 complete. Part 3: Escalate. If the broker does not reply in the time it states, or the reply does not resolve this, you can escalate through SEBI's SCORES complaint portal. Please check the current process and time limits on the official site before filing.",
    options: ['Prepare escalation'] },
  { stage: 5, ai: 'Escalation summary: problem, amount, date, your complaint to the broker with its date and reference, and the broker reply (or no reply). Attach the same evidence from Part 1. File it on the portal, then mark it done.',
    options: ["I've filed the escalation"], entry: { title: 'Part 3 – Escalation', text: 'Escalation filed on the grievance portal ✔' } },
]

export const DONE_MESSAGE = '🎉 All parts are complete and your report is 100% ready. Open Current Report to see and download it.'
