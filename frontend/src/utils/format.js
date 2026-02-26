export function formatCurrency(amount) {
  if (amount == null) return '$0.00'
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
  }).format(amount)
}

export function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-CA', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function formatAccountType(type) {
  if (!type) return ''
  return type
}

export function toISODate(date) {
  if (!date) return ''
  if (typeof date === 'string') return date.split('T')[0]
  return date.toISOString().split('T')[0]
}

export function todayISO() {
  return new Date().toISOString().split('T')[0]
}
