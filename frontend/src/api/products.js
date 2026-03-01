import { apiFetch } from './client'

export const fetchProducts = (type) =>
  apiFetch(`/products${type ? `?type=${encodeURIComponent(type)}` : ''}`)

export const createProduct = (data) =>
  apiFetch('/products', { method: 'POST', body: data })

export const updateProduct = (id, data) =>
  apiFetch(`/products/${id}`, { method: 'PUT', body: data })

export const deleteProduct = (id) =>
  apiFetch(`/products/${id}`, { method: 'DELETE' })
