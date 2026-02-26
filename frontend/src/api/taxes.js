import { apiFetch } from './client'

export const fetchTaxes = () => apiFetch('/taxes')

export const createTax = (data) =>
  apiFetch('/taxes', { method: 'POST', body: data })

export const updateTax = (id, data) =>
  apiFetch(`/taxes/${id}`, { method: 'PUT', body: data })

export const deleteTax = (id) =>
  apiFetch(`/taxes/${id}`, { method: 'DELETE' })
