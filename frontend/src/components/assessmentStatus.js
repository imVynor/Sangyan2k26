const STATUS_LABELS = {
  EVIDENCE_INSUFFICIENT: 'Evidence insufficient',
  VIOLATION_CONFIRMED: 'Violation confirmed',
  COMPLIANT_WITH_REGULATION: 'Compliant with regulation',
  REGULATORY_COVERAGE_UNRESOLVED: 'Regulatory coverage unresolved',
  TEMPORALITY_UNRESOLVED: 'Applicable date unresolved',
  ORGANISATION_POLICY_DEVIATION: 'Organisation policy deviation',
}

export function formatAssessmentStatus(status) {
  return STATUS_LABELS[status] || status.replaceAll('_', ' ').toLowerCase()
}
