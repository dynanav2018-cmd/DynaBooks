import { apiFetch } from './client'

export const fetchContacts = (type) =>
  apiFetch(`/contacts${type ? `?type=${type}` : ''}`)

export const createContact = (data) =>
  apiFetch('/contacts', { method: 'POST', body: data })

export const updateContact = async (id, data) => {
  // Update contact fields (without addresses)
  const { addresses, ...contactData } = data
  const result = await apiFetch(`/contacts/${id}`, { method: 'PUT', body: contactData })

  // Sync addresses: fetch existing, diff, create/update/delete
  if (addresses) {
    const existing = await apiFetch(`/contacts/${id}/addresses`)
    const existingIds = new Set(existing.map(a => a.id))
    const sentIds = new Set()

    for (const addr of addresses) {
      if (addr.id && existingIds.has(addr.id)) {
        // Update existing
        await apiFetch(`/contacts/${id}/addresses/${addr.id}`, { method: 'PUT', body: addr })
        sentIds.add(addr.id)
      } else {
        // Create new
        await apiFetch(`/contacts/${id}/addresses`, { method: 'POST', body: addr })
      }
    }

    // Delete removed addresses
    for (const ex of existing) {
      if (!sentIds.has(ex.id)) {
        await apiFetch(`/contacts/${id}/addresses/${ex.id}`, { method: 'DELETE' })
      }
    }
  }

  return result
}

export const deleteContact = (id) =>
  apiFetch(`/contacts/${id}`, { method: 'DELETE' })

export const fetchContactAddresses = (contactId) =>
  apiFetch(`/contacts/${contactId}/addresses`)
