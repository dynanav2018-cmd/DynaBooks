import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import { fetchInventory } from '../../api/inventory'
import { fetchAccounts } from '../../api/accounts'
import { fetchTaxes } from '../../api/taxes'
import { fetchContacts } from '../../api/contacts'
import { createProduct } from '../../api/products'
import DataTable from '../../components/shared/DataTable'
import PageHeader from '../../components/shared/PageHeader'
import Button from '../../components/shared/Button'
import StatusBadge from '../../components/shared/StatusBadge'
import Modal from '../../components/shared/Modal'
import FormField, { Input, Select } from '../../components/shared/FormField'
import StockAdjustmentModal from './StockAdjustmentModal'

const formatCurrency = (v) => {
  const n = Number(v) || 0
  return new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(n)
}

const emptyForm = {
  name: '', description: '', default_price: '', sku: '',
  revenue_account_id: '', tax_id: '',
  track_inventory: true,
  reorder_point: '', inventory_account_id: '', cogs_account_id: '',
  preferred_supplier_id: '',
}

export default function InventoryList() {
  const navigate = useNavigate()
  const toast = useToast()
  const { data: products, loading, refetch } = useApi(fetchInventory)
  const [filter, setFilter] = useState('all')
  const [showAdjust, setShowAdjust] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ ...emptyForm })
  const [saving, setSaving] = useState(false)

  const { data: revenueAccounts } = useApi(() => fetchAccounts('Operating Revenue'), [])
  const { data: inventoryAccounts } = useApi(() => fetchAccounts('Inventory'), [])
  const { data: cogsAccounts } = useApi(() => fetchAccounts('Direct Expense'), [])
  const { data: taxes } = useApi(fetchTaxes, [])
  const { data: suppliers } = useApi(() => fetchContacts('supplier'), [])

  const filtered = (products || []).filter((p) => {
    if (filter === 'tracked') return p.track_inventory
    if (filter === 'sales') return !p.track_inventory
    if (filter === 'low') return p.track_inventory && p.quantity_on_hand <= p.reorder_point
    return true
  })

  const columns = [
    { key: 'sku', label: 'SKU' },
    { key: 'name', label: 'Product' },
    {
      key: 'quantity_on_hand',
      label: 'On Hand',
      render: (v, row) => row.track_inventory ? Number(v).toFixed(0) : '—',
    },
    {
      key: 'average_cost',
      label: 'Avg Cost',
      render: (v, row) => row.track_inventory ? formatCurrency(v) : '—',
    },
    {
      key: '_value',
      label: 'Value',
      render: (_, row) => row.track_inventory ? formatCurrency(row.quantity_on_hand * row.average_cost) : '—',
    },
    {
      key: 'default_price',
      label: 'Price',
      render: (v) => v ? formatCurrency(v) : '—',
    },
    {
      key: '_status',
      label: 'Status',
      render: (_, row) => {
        if (!row.track_inventory) return <StatusBadge status="Sales Only" />
        return row.quantity_on_hand <= row.reorder_point ? (
          <StatusBadge status="Low Stock" />
        ) : (
          <StatusBadge status="In Stock" />
        )
      },
    },
  ]

  const filters = [
    { key: 'all', label: 'All' },
    { key: 'tracked', label: 'Tracked' },
    { key: 'sales', label: 'Sales Only' },
    { key: 'low', label: 'Low Stock' },
  ]

  const openCreate = () => {
    setForm({ ...emptyForm })
    setShowCreate(true)
  }

  const handleCreateSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const payload = {
        name: form.name,
        description: form.description,
        default_price: parseFloat(form.default_price) || 0,
        product_type: 'product',
        revenue_account_id: parseInt(form.revenue_account_id),
        tax_id: form.tax_id ? parseInt(form.tax_id) : null,
        sku: form.sku || null,
        track_inventory: form.track_inventory,
        preferred_supplier_id: form.preferred_supplier_id ? parseInt(form.preferred_supplier_id) : null,
      }
      if (form.track_inventory) {
        payload.reorder_point = parseFloat(form.reorder_point) || 0
        payload.inventory_account_id = form.inventory_account_id ? parseInt(form.inventory_account_id) : null
        payload.cogs_account_id = form.cogs_account_id ? parseInt(form.cogs_account_id) : null
      }
      await createProduct(payload)
      toast.success('Inventory item created')
      setShowCreate(false)
      refetch()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="p-6 text-gray-500">Loading...</div>

  return (
    <div className="p-6">
      <PageHeader title="Inventory & Sales Items">
        <Button variant="secondary" onClick={() => setShowAdjust(true)}>
          Adjust Stock
        </Button>
        <Button variant="secondary" onClick={() => navigate('/purchase-orders/new')}>
          New Purchase Order
        </Button>
        <Button onClick={openCreate}>
          Add Items
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
        emptyMessage="No inventory items found. Click 'Add Items' to create one."
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

      {showCreate && (
        <Modal open={showCreate} onClose={() => setShowCreate(false)} title="New Inventory Item">
          <form onSubmit={handleCreateSubmit}>
            <FormField label="Name" required>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            </FormField>
            <FormField label="Description">
              <Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </FormField>
            <FormField label="SKU">
              <Input value={form.sku} onChange={(e) => setForm({ ...form, sku: e.target.value })} placeholder="e.g. WIDGET-001" />
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

            <label className="flex items-center gap-2 mt-3 mb-3 cursor-pointer">
              <input
                type="checkbox"
                checked={form.track_inventory}
                onChange={(e) => setForm({ ...form, track_inventory: e.target.checked })}
                className="h-4 w-4 rounded border-gray-300 text-accent focus:ring-accent"
              />
              <span className="text-sm font-medium text-gray-700">Track Inventory</span>
            </label>
            {form.track_inventory && (
              <>
                <FormField label="Reorder Point">
                  <Input type="number" min="0" step="any" value={form.reorder_point} onChange={(e) => setForm({ ...form, reorder_point: e.target.value })} placeholder="0" />
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
              </>
            )}

            <div className="flex justify-end gap-3 mt-6">
              <Button variant="secondary" type="button" onClick={() => setShowCreate(false)}>Cancel</Button>
              <Button type="submit" disabled={saving}>{saving ? 'Creating...' : 'Create'}</Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
