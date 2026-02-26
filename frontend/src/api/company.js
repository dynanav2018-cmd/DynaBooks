import { apiFetch } from './client'

export const fetchCompany = () => apiFetch('/company')

export const updateCompany = (data) =>
  apiFetch('/company', { method: 'PUT', body: data })
