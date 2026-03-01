import { apiFetch } from './client'

export const fetchJournals = () => apiFetch('/journals')

export const fetchJournal = (id) => apiFetch(`/journals/${id}`)

export const createJournal = (data) =>
  apiFetch('/journals', { method: 'POST', body: data })

export const updateJournal = (id, data) =>
  apiFetch(`/journals/${id}`, { method: 'PUT', body: data })

export const deleteJournal = (id) =>
  apiFetch(`/journals/${id}`, { method: 'DELETE' })

export const postJournal = (id) =>
  apiFetch(`/journals/${id}/post`, { method: 'POST' })
