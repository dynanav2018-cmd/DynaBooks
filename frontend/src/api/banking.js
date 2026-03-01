import { apiFetch } from './client'

export const fetchReceipts = () => apiFetch('/receipts')

export const createReceipt = (data) =>
  apiFetch('/receipts', { method: 'POST', body: data })

export const deleteReceipt = (id) =>
  apiFetch(`/receipts/${id}`, { method: 'DELETE' })

export const voidReceipt = (id) =>
  apiFetch(`/receipts/${id}/void`, { method: 'POST' })

export const fetchPayments = () => apiFetch('/payments')

export const createPayment = (data) =>
  apiFetch('/payments', { method: 'POST', body: data })

export const deletePayment = (id) =>
  apiFetch(`/payments/${id}`, { method: 'DELETE' })

export const voidPayment = (id) =>
  apiFetch(`/payments/${id}/void`, { method: 'POST' })

export const createAssignment = (data) =>
  apiFetch('/assignments', { method: 'POST', body: data })
