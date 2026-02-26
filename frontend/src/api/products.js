import { apiFetch } from './client'

export const fetchProducts = () => apiFetch('/products')

export const createProduct = (data) =>
  apiFetch('/products', { method: 'POST', body: data })

export const updateProduct = (id, data) =>
  apiFetch(`/products/${id}`, { method: 'PUT', body: data })

export const deleteProduct = (id) =>
  apiFetch(`/products/${id}`, { method: 'DELETE' })
