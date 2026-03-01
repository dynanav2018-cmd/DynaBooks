import { apiFetch } from './client'

export const fetchRecurringJournals = () =>
  apiFetch('/recurring-journals')

export const createRecurringJournal = (data) =>
  apiFetch('/recurring-journals', { method: 'POST', body: data })

export const updateRecurringJournal = (id, data) =>
  apiFetch(`/recurring-journals/${id}`, { method: 'PUT', body: data })

export const deleteRecurringJournal = (id) =>
  apiFetch(`/recurring-journals/${id}`, { method: 'DELETE' })
