import { apiFetch } from './client'

export const fetchClosingPreview = () => apiFetch('/closing/preview')

export const performClosing = () =>
  apiFetch('/closing', { method: 'POST' })
