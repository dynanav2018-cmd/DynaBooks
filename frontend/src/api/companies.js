import { apiFetch } from './client'

export const fetchCompanies = () => apiFetch('/companies')

export const createCompanyApi = (data) =>
  apiFetch('/companies', { method: 'POST', body: data })

export const fetchCompanyBySlug = (slug) => apiFetch(`/companies/${slug}`)
