import { apiFetch } from './client'

export const fetchReceipts = () => apiFetch('/receipts')

export const createReceipt = (data) =>
  apiFetch('/receipts', { method: 'POST', body: data })

export const fetchPayments = () => apiFetch('/payments')

export const createPayment = (data) =>
  apiFetch('/payments', { method: 'POST', body: data })

export const createAssignment = (data) =>
  apiFetch('/assignments', { method: 'POST', body: data })
