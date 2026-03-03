import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { fetchInventory } from '../../api/inventory'
import DataTable from '../../components/shared/DataTable'
import PageHeader from '../../components/shared/PageHeader'
import Button from '../../components/shared/Button'
import StatusBadge from '../../components/shared/StatusBadge'
import StockAdjustmentModal from './StockAdjustmentModal'

const formatCurrency = (v) => {
  const n = Number(v) || 0
  return new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(n)
}

export default function InventoryList() {
  const navigate = useNavigate()
  const { data: products, loading, refetch } = useApi(fetchInventory)
  const [filter, setFilter] = useState('all')
  const [showAdjust, setShowAdjust] = useState(false)

  const filtered = (products || []).filter((p) => {
    if (filter === 'low') return p.quantity_on_hand <= p.reorder_point
    if (filter === 'in-stock') return p.quantity_on_hand > p.reorder_point
    return true
  })

  const columns = [
    { key: 'sku', label: 'SKU' },
    { key: 'name', label: 'Product' },
    {
      key: 'quantity_on_hand',
      label: 'On Hand',
      render: (v) => Number(v).toFixed(0),
    },
    {
      key: 'average_cost',
      label: 'Avg Cost',
      render: (v) => formatCurrency(v),
    },
    {
      key: '_value',
      label: 'Value',
      render: (_, row) => formatCurrency(row.quantity_on_hand * row.average_cost),
    },
    {
      key: 'reorder_point',
      label: 'Reorder Pt',
      render: (v) => Number(v).toFixed(0),
    },
    {
      key: '_status',
      label: 'Status',
      render: (_, row) =>
        row.quantity_on_hand <= row.reorder_point ? (
          <StatusBadge status="Low Stock" />
        ) : (
          <StatusBadge status="In Stock" />
        ),
    },
  ]

  const filters = [
    { key: 'all', label: 'All' },
    { key: 'in-stock', label: 'In Stock' },
    { key: 'low', label: 'Low Stock' },
  ]

  if (loading) return <div className="p-6 text-gray-500">Loading...</div>

  return (
    <div className="p-6">
      <PageHeader title="Inventory">
        <Button variant="secondary" onClick={() => setShowAdjust(true)}>
          Adjust Stock
        </Button>
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
        onRowClick={(row) => navigate(`/inventory/${row.id}`)}
        emptyMessage="No inventory products found. Enable inventory tracking on a product in Settings."
      />

      {showAdjust && (
        <StockAdjustmentModal
          onClose={() => setShowAdjust(false)}
          onSaved={() => {
            setShowAdjust(false)
            refetch()
          }}
        />
      )}
    </div>
  )
}
