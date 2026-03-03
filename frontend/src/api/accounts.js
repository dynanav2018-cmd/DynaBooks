import { apiFetch } from './client'

export const fetchAccounts = (type, category) => {
  const params = new URLSearchParams()
  if (type) params.set('type', type)
  if (category) params.set('category', category)
  const qs = params.toString()
  return apiFetch(`/accounts${qs ? `?${qs}` : ''}`)
}

export const createAccount = (data) =>
  apiFetch('/accounts', { method: 'POST', body: data })

export const updateAccount = (id, data) =>
  apiFetch(`/accounts/${id}`, { method: 'PUT', body: data })

export const deleteAccount = (id) =>
  apiFetch(`/accounts/${id}`, { method: 'DELETE' })

export const fetchAccountLedger = (id) =>
  apiFetch(`/accounts/${id}/ledger`)
