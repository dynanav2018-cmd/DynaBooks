import { apiFetch } from './client'

export const fetchCompany = () => apiFetch('/company')

export const updateCompany = (data) =>
  apiFetch('/company', { method: 'PUT', body: data })

export const uploadLogo = (file) => {
  const formData = new FormData()
  formData.append('logo', file)
  return apiFetch('/company/logo', { method: 'POST', body: formData })
}

export const getLogoUrl = () => '/api/company/logo'
