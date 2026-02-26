import { apiFetch } from './client'

export const fetchAccounts = (type) =>
  apiFetch(`/accounts${type ? `?type=${encodeURIComponent(type)}` : ''}`)

export const createAccount = (data) =>
  apiFetch('/accounts', { method: 'POST', body: data })

export const updateAccount = (id, data) =>
  apiFetch(`/accounts/${id}`, { method: 'PUT', body: data })

export const deleteAccount = (id) =>
  apiFetch(`/accounts/${id}`, { method: 'DELETE' })
