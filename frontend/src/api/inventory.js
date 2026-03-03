import { apiFetch } from './client'

export const fetchInventory = () => apiFetch('/inventory')

export const fetchInventoryProduct = (id) => apiFetch(`/inventory/${id}`)

export const fetchStockMovements = (productId) =>
  apiFetch(`/inventory/${productId}/movements`)

export const fetchLowStock = () => apiFetch('/inventory/low-stock')

export const createStockAdjustment = (data) =>
  apiFetch('/inventory/adjustment', { method: 'POST', body: data })

export const fetchInventoryValuation = () => apiFetch('/inventory/valuation')
