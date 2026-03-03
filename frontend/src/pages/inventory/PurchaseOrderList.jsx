import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { fetchPurchaseOrders } from '../../api/purchaseOrders'
import DataTable from '../../components/shared/DataTable'
import PageHeader from '../../components/shared/PageHeader'
import Button from '../../components/shared/Button'
import StatusBadge from '../../components/shared/StatusBadge'

const formatCurrency = (v) => {
  const n = Number(v) || 0
  return new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(n)
}

const formatDate = (v) => {
  if (!v) return ''
  return new Date(v).toLocaleDateString('en-CA')
}

export default function PurchaseOrderList() {
  const navigate = useNavigate()
  const { data: pos, loading } = useApi(fetchPurchaseOrders)
  const [filter, setFilter] = useState('all')

  const filtered = (pos || []).filter((po) => {
    if (filter === 'all') return true
    return po.status === filter
  })

  const columns = [
    { key: 'po_number', label: 'PO #' },
    { key: 'supplier_name', label: 'Supplier' },
    { key: 'order_date', label: 'Date', render: formatDate },
    { key: 'expected_date', label: 'Expected', render: formatDate },
    { key: 'total', label: 'Total', render: formatCurrency },
    {
      key: 'status',
      label: 'Status',
      render: (v) => <StatusBadge status={v.charAt(0).toUpperCase() + v.slice(1)} />,
    },
  ]

  const filters = [
    { key: 'all', label: 'All' },
    { key: 'draft', label: 'Draft' },
    { key: 'sent', label: 'Sent' },
    { key: 'partial', label: 'Partial' },
    { key: 'received', label: 'Received' },
  ]

  if (loading) return <div className="p-6 text-gray-500">Loading...</div>

  return (
    <div className="p-6">
      <PageHeader title="Purchase Orders">
        <Button onClick={() => navigate('/purchase-orders/new')}>
          New Purchase Order
        </Button>
      </PageHeader>

      <div className="flex gap-1 mb-4 bg-gray-100 rounded-lg p-1 w-fit">
        {filters.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
              filter === f.key
                ? 'bg-white text-navy font-medium shadow-sm'
                : 'text-gray-600 hover:text-gray-800'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <DataTable
        columns={columns}
        data={filtered}
        onRowClick={(row) => navigate(`/purchase-orders/${row.id}`)}
        emptyMessage="No purchase orders found"
      />
    </div>
  )
}
