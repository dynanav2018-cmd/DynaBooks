import { apiFetch } from './client'

export const fetchContacts = (type) =>
  apiFetch(`/contacts${type ? `?type=${type}` : ''}`)

export const createContact = (data) =>
  apiFetch('/contacts', { method: 'POST', body: data })

export const updateContact = (id, data) =>
  apiFetch(`/contacts/${id}`, { method: 'PUT', body: data })

export const deleteContact = (id) =>
  apiFetch(`/contacts/${id}`, { method: 'DELETE' })
