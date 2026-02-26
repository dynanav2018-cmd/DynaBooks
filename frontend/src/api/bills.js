import { apiFetch } from './client'

export const fetchBills = () => apiFetch('/bills')

export const fetchBill = (id) => apiFetch(`/bills/${id}`)

export const createBill = (data) =>
  apiFetch('/bills', { method: 'POST', body: data })

export const updateBill = (id, data) =>
  apiFetch(`/bills/${id}`, { method: 'PUT', body: data })

export const deleteBill = (id) =>
  apiFetch(`/bills/${id}`, { method: 'DELETE' })

export const postBill = (id) =>
  apiFetch(`/bills/${id}/post`, { method: 'POST' })

export const downloadBillPdf = (id) =>
  apiFetch(`/bills/${id}/pdf`, { responseType: 'blob' })
