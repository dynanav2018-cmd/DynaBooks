import { apiFetch } from './client'

export const fetchPurchaseOrders = () => apiFetch('/purchase-orders')

export const fetchPurchaseOrder = (id) => apiFetch(`/purchase-orders/${id}`)

export const createPurchaseOrder = (data) =>
  apiFetch('/purchase-orders', { method: 'POST', body: data })

export const updatePurchaseOrder = (id, data) =>
  apiFetch(`/purchase-orders/${id}`, { method: 'PUT', body: data })

export const deletePurchaseOrder = (id) =>
  apiFetch(`/purchase-orders/${id}`, { method: 'DELETE' })

export const sendPurchaseOrder = (id) =>
  apiFetch(`/purchase-orders/${id}/send`, { method: 'POST' })

export const receivePurchaseOrder = (id, data) =>
  apiFetch(`/purchase-orders/${id}/receive`, { method: 'POST', body: data })

export const cancelPurchaseOrder = (id) =>
  apiFetch(`/purchase-orders/${id}/cancel`, { method: 'POST' })
