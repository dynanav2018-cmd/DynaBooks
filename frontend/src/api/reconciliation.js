import { apiFetch } from './client'

export const fetchReconciliations = (accountId) =>
  apiFetch(`/reconciliations${accountId ? `?account_id=${accountId}` : ''}`)

export const createReconciliation = (data) =>
  apiFetch('/reconciliations', { method: 'POST', body: data })

export const fetchReconciliation = (id) =>
  apiFetch(`/reconciliations/${id}`)

export const updateReconciliation = (id, data) =>
  apiFetch(`/reconciliations/${id}`, { method: 'PUT', body: data })

export const deleteReconciliation = (id) =>
  apiFetch(`/reconciliations/${id}`, { method: 'DELETE' })
