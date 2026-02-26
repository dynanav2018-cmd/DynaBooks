import { apiFetch } from './client'

export const fetchIncomeStatement = (from, to) => {
  const params = new URLSearchParams()
  if (from) params.set('from', from)
  if (to) params.set('to', to)
  return apiFetch(`/reports/income-statement?${params}`)
}

export const fetchBalanceSheet = (asOf) => {
  const params = new URLSearchParams()
  if (asOf) params.set('as_of', asOf)
  return apiFetch(`/reports/balance-sheet?${params}`)
}

export const fetchAgingReceivables = (asOf) => {
  const params = new URLSearchParams()
  if (asOf) params.set('as_of', asOf)
  return apiFetch(`/reports/aging-receivables?${params}`)
}

export const fetchAgingPayables = (asOf) => {
  const params = new URLSearchParams()
  if (asOf) params.set('as_of', asOf)
  return apiFetch(`/reports/aging-payables?${params}`)
}

export const downloadReportPdf = (type, params = {}) => {
  const qs = new URLSearchParams(params)
  return apiFetch(`/reports/${type}/pdf?${qs}`, { responseType: 'blob' })
}
