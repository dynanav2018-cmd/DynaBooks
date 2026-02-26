import { apiFetch } from './client'

export const fetchInvoices = () => apiFetch('/invoices')

export const fetchInvoice = (id) => apiFetch(`/invoices/${id}`)

export const createInvoice = (data) =>
  apiFetch('/invoices', { method: 'POST', body: data })

export const updateInvoice = (id, data) =>
  apiFetch(`/invoices/${id}`, { method: 'PUT', body: data })

export const deleteInvoice = (id) =>
  apiFetch(`/invoices/${id}`, { method: 'DELETE' })

export const postInvoice = (id) =>
  apiFetch(`/invoices/${id}/post`, { method: 'POST' })

export const downloadInvoicePdf = (id) =>
  apiFetch(`/invoices/${id}/pdf`, { responseType: 'blob' })
