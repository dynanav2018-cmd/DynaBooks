import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import { fetchInventoryProduct, fetchStockMovements } from '../../api/inventory'
import { updateProduct } from '../../api/products'
import { fetchAccounts } from '../../api/accounts'
import { fetchTaxes } from '../../api/taxes'
import { fetchContacts } from '../../api/contacts'
import PageHeader from '../../components/shared/PageHeader'
import Button from '../../components/shared/Button'
import DataTable from '../../components/shared/DataTable'
import StatusBadge from '../../components/shared/StatusBadge'
import Modal from '../../components/shared/Modal'
import FormField, { Input, Select } from '../../components/shared/FormField'
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
  const toast = useToast()
  const { data: product, loading: loadingProduct, refetch: refetchProduct } = useApi(
    () => fetchInventoryProduct(id), [id]
  )
  const { data: movements, loading: loadingMovements, refetch: refetchMovements } = useApi(
    () => fetchStockMovements(id), [id]
  )
  const { data: suppliers } = useApi(() => fetchContacts('supplier'), [])
  const [showAdjust, setShowAdjust] = useState(false)
  const [showEdit, setShowEdit] = useState(false)
  const [form, setForm] = useState({})
  const [saving, setSaving] = useState(false)

  const { data: revenueAccounts } = useApi(() => fetchAccounts('Operating Revenue'), [])
  const { data: inventoryAccounts } = useApi(() => fetchAccounts('Inventory'), [])
  const { data: cogsAccounts } = useApi(() => fetchAccounts('Direct Expense'), [])
  const { data: taxes } = useApi(fetchTaxes, [])

  const openEdit = () => {
    if (!product) return
    setForm({
      name: product.name || '',
      description: product.description || '',
      default_price: product.default_price?.toString() || '',
      sku: product.sku || '',
      revenue_account_id: product.revenue_account_id?.toString() || '',
      tax_id: product.tax_id?.toString() || '',
      reorder_point: product.reorder_point?.toString() || '',
      inventory_account_id: product.inventory_account_id?.toString() || '',
      cogs_account_id: product.cogs_account_id?.toString() || '',
      preferred_supplier_id: product.preferred_supplier_id?.toString() || '',
    })
    setShowEdit(true)
  }

  const handleEditSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const payload = {
        name: form.name,
        description: form.description,
        default_price: parseFloat(form.default_price) || 0,
        revenue_account_id: parseInt(form.revenue_account_id),
        tax_id: form.tax_id ? parseInt(form.tax_id) : null,
        sku: form.sku || null,
        track_inventory: true,
        reorder_point: parseFloat(form.reorder_point) || 0,
        inventory_account_id: form.inventory_account_id ? parseInt(form.inventory_account_id) : null,
        cogs_account_id: form.cogs_account_id ? parseInt(form.cogs_account_id) : null,
        preferred_supplier_id: form.preferred_supplier_id ? parseInt(form.preferred_supplier_id) : null,
      }
      await updateProduct(id, payload)
      toast.success('Inventory item updated')
      setShowEdit(false)
      refetchProduct()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (loadingProduct) return <div className="p-6 text-gray-500">Loading...</div>
  if (!product) return <div className="p-6 text-gray-500">Product not found</div>

  const isLow = product.quantity_on_hand <= product.reorder_point
  const supplierName = suppliers?.find((s) => s.id === product.preferred_supplier_id)?.name

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
        <Button variant="secondary" onClick={openEdit}>
          Edit Item
        </Button>
        <Button variant="secondary" onClick={() => setShowAdjust(true)}>
          Adjust Stock
        </Button>
        <Button variant="secondary" onClick={() => navigate('/inventory')}>
          Back to Inventory
        </Button>
      </PageHeader>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
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
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-xs text-gray-500 uppercase font-medium">Preferred Supplier</p>
          <p className="text-lg font-semibold text-gray-800 mt-1">{supplierName || '—'}</p>
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

      {showEdit && (
        <Modal open={showEdit} onClose={() => setShowEdit(false)} title="Edit Inventory Item">
          <form onSubmit={handleEditSubmit}>
            <FormField label="Name" required>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            </FormField>
            <FormField label="Description">
              <Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </FormField>
            <FormField label="SKU">
              <Input value={form.sku} onChange={(e) => setForm({ ...form, sku: e.target.value })} />
            </FormField>
            <FormField label="Default Price">
              <Input type="number" step="0.01" value={form.default_price} onChange={(e) => setForm({ ...form, default_price: e.target.value })} />
            </FormField>
            <FormField label="Revenue Account" required>
              <Select value={form.revenue_account_id} onChange={(e) => setForm({ ...form, revenue_account_id: e.target.value })} required>
                <option value="">Select account...</option>
                {revenueAccounts?.map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </Select>
            </FormField>
            <FormField label="Tax">
              <Select value={form.tax_id} onChange={(e) => setForm({ ...form, tax_id: e.target.value })}>
                <option value="">No tax</option>
                {taxes?.map((t) => (
                  <option key={t.id} value={t.id}>{t.name} ({t.rate}%)</option>
                ))}
              </Select>
            </FormField>
            <FormField label="Preferred Supplier">
              <Select value={form.preferred_supplier_id} onChange={(e) => setForm({ ...form, preferred_supplier_id: e.target.value })}>
                <option value="">None</option>
                {suppliers?.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}{s.company ? ` (${s.company})` : ''}</option>
                ))}
              </Select>
            </FormField>

            <h4 className="text-sm font-semibold text-gray-700 mt-4 mb-2">Inventory Tracking</h4>
            <FormField label="Reorder Point">
              <Input type="number" min="0" step="any" value={form.reorder_point} onChange={(e) => setForm({ ...form, reorder_point: e.target.value })} />
            </FormField>
            <FormField label="Inventory Account">
              <Select value={form.inventory_account_id} onChange={(e) => setForm({ ...form, inventory_account_id: e.target.value })}>
                <option value="">Select account...</option>
                {inventoryAccounts?.map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </Select>
            </FormField>
            <FormField label="COGS Account">
              <Select value={form.cogs_account_id} onChange={(e) => setForm({ ...form, cogs_account_id: e.target.value })}>
                <option value="">Select account...</option>
                {cogsAccounts?.map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </Select>
            </FormField>

            <div className="flex justify-end gap-3 mt-6">
              <Button variant="secondary" type="button" onClick={() => setShowEdit(false)}>Cancel</Button>
              <Button type="submit" disabled={saving}>{saving ? 'Saving...' : 'Update'}</Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
