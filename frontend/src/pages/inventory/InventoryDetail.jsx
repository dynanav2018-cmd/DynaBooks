import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { fetchInventoryProduct, fetchStockMovements } from '../../api/inventory'
import PageHeader from '../../components/shared/PageHeader'
import Button from '../../components/shared/Button'
import DataTable from '../../components/shared/DataTable'
import StatusBadge from '../../components/shared/StatusBadge'
import StockAdjustmentModal from './StockAdjustmentModal'

const formatCurrency = (v) => {
  const n = Number(v) || 0
  return new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(n)
}

const formatDate = (v) => {
  if (!v) return ''
  return new Date(v).toLocaleDateString('en-CA')
}

const MOVEMENT_LABELS = {
  purchase: 'Purchase',
  sale: 'Sale',
  adjustment: 'Adjustment',
  write_off: 'Write-Off',
  opening: 'Opening',
}

export default function InventoryDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { data: product, loading: loadingProduct, refetch: refetchProduct } = useApi(
    () => fetchInventoryProduct(id), [id]
  )
  const { data: movements, loading: loadingMovements, refetch: refetchMovements } = useApi(
    () => fetchStockMovements(id), [id]
  )
  const [showAdjust, setShowAdjust] = useState(false)

  if (loadingProduct) return <div className="p-6 text-gray-500">Loading...</div>
  if (!product) return <div className="p-6 text-gray-500">Product not found</div>

  const isLow = product.quantity_on_hand <= product.reorder_point

  const columns = [
    { key: 'created_at', label: 'Date', render: formatDate },
    {
      key: 'movement_type',
      label: 'Type',
      render: (v) => MOVEMENT_LABELS[v] || v,
    },
    {
      key: 'quantity_change',
      label: 'Qty Change',
      render: (v) => {
        const n = Number(v)
        return (
          <span className={n >= 0 ? 'text-green-700' : 'text-red-700'}>
            {n >= 0 ? '+' : ''}{n}
          </span>
        )
      },
    },
    { key: 'unit_cost', label: 'Unit Cost', render: formatCurrency },
    { key: 'total_cost', label: 'Total Cost', render: (v) => formatCurrency(Math.abs(v)) },
    { key: 'quantity_after', label: 'Balance', render: (v) => Number(v).toFixed(0) },
    { key: 'reference', label: 'Reference' },
    { key: 'notes', label: 'Notes' },
  ]

  return (
    <div className="p-6">
      <PageHeader title={product.name}>
        <Button variant="secondary" onClick={() => setShowAdjust(true)}>
          Adjust Stock
        </Button>
        <Button variant="secondary" onClick={() => navigate('/inventory')}>
          Back to Inventory
        </Button>
      </PageHeader>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-xs text-gray-500 uppercase font-medium">SKU</p>
          <p className="text-lg font-semibold text-gray-800 mt-1">{product.sku || '—'}</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-xs text-gray-500 uppercase font-medium">On Hand</p>
          <p className="text-lg font-semibold text-gray-800 mt-1">
            {Number(product.quantity_on_hand).toFixed(0)}
            {isLow && <StatusBadge status="Low Stock" />}
          </p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-xs text-gray-500 uppercase font-medium">Avg Cost</p>
          <p className="text-lg font-semibold text-gray-800 mt-1">{formatCurrency(product.average_cost)}</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-xs text-gray-500 uppercase font-medium">Total Value</p>
          <p className="text-lg font-semibold text-navy mt-1">
            {formatCurrency(product.quantity_on_hand * product.average_cost)}
          </p>
        </div>
      </div>

      <h3 className="text-lg font-semibold text-gray-800 mb-4">Stock Movement History</h3>
      {loadingMovements ? (
        <p className="text-gray-500">Loading movements...</p>
      ) : (
        <DataTable
          columns={columns}
          data={movements || []}
          emptyMessage="No stock movements yet"
        />
      )}

      {showAdjust && (
        <StockAdjustmentModal
          productId={product.id}
          onClose={() => setShowAdjust(false)}
          onSaved={() => {
            setShowAdjust(false)
            refetchProduct()
            refetchMovements()
          }}
        />
      )}
    </div>
  )
}
