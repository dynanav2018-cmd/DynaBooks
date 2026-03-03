import { useState, useMemo } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import { fetchContacts } from '../../api/contacts'
import { fetchInventory } from '../../api/inventory'
import { fetchTaxes } from '../../api/taxes'
import { createPurchaseOrder, updatePurchaseOrder, fetchPurchaseOrder } from '../../api/purchaseOrders'
import PageHeader from '../../components/shared/PageHeader'
import Button from '../../components/shared/Button'
import FormField, { Input, Select } from '../../components/shared/FormField'

const formatCurrency = (v) => {
  const n = Number(v) || 0
  return new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(n)
}

const emptyLine = { product_id: '', description: '', quantity_ordered: '', unit_cost: '', tax_id: '' }

export default function PurchaseOrderForm() {
  const { id } = useParams()
  const isEdit = Boolean(id)
  const navigate = useNavigate()
  const toast = useToast()

  const { data: contacts } = useApi(() => fetchContacts('supplier'), [])
  const { data: products } = useApi(fetchInventory, [])
  const { data: taxes } = useApi(fetchTaxes, [])

  const [form, setForm] = useState({
    supplier_contact_id: '',
    order_date: new Date().toISOString().split('T')[0],
    expected_date: '',
    notes: '',
    lines: [{ ...emptyLine }],
  })
  const [loaded, setLoaded] = useState(!isEdit)
  const [saving, setSaving] = useState(false)

  // Load existing PO for editing
  useApi(
    () => (isEdit ? fetchPurchaseOrder(id) : Promise.resolve(null)),
    [id],
    {
      onSuccess: (data) => {
        if (data) {
          setForm({
            supplier_contact_id: String(data.supplier_contact_id || ''),
            order_date: data.order_date || '',
            expected_date: data.expected_date || '',
            notes: data.notes || '',
            lines: (data.lines || []).map((l) => ({
              product_id: String(l.product_id || ''),
              description: l.description || '',
              quantity_ordered: String(l.quantity_ordered || ''),
              unit_cost: String(l.unit_cost || ''),
              tax_id: l.tax_id ? String(l.tax_id) : '',
            })),
          })
          setLoaded(true)
        }
      },
    },
  )

  const updateLine = (index, field, value) => {
    setForm((prev) => {
      const lines = [...prev.lines]
      lines[index] = { ...lines[index], [field]: value }
      return { ...prev, lines }
    })
  }

  const selectProduct = (index, productId) => {
    const product = (products || []).find((p) => p.id === parseInt(productId))
    if (product) {
      setForm((prev) => {
        const lines = [...prev.lines]
        lines[index] = {
          ...lines[index],
          product_id: String(productId),
          description: product.name,
          unit_cost: String(product.average_cost || product.default_price || ''),
        }
        return { ...prev, lines }
      })
    }
  }

  const addLine = () => setForm((prev) => ({ ...prev, lines: [...prev.lines, { ...emptyLine }] }))

  const removeLine = (index) => {
    if (form.lines.length <= 1) return
    setForm((prev) => ({ ...prev, lines: prev.lines.filter((_, i) => i !== index) }))
  }

  const totals = useMemo(() => {
    let subtotal = 0
    form.lines.forEach((l) => {
      subtotal += (parseFloat(l.quantity_ordered) || 0) * (parseFloat(l.unit_cost) || 0)
    })
    return { subtotal }
  }, [form.lines])

  const handleSubmit = async (send = false) => {
    if (!form.supplier_contact_id) {
      toast.error('Supplier is required')
      return
    }
    if (!form.lines.some((l) => l.product_id && l.quantity_ordered)) {
      toast.error('At least one line with a product and quantity is required')
      return
    }

    const payload = {
      supplier_contact_id: parseInt(form.supplier_contact_id),
      order_date: form.order_date,
      expected_date: form.expected_date || null,
      notes: form.notes,
      send,
      lines: form.lines
        .filter((l) => l.product_id && l.quantity_ordered)
        .map((l) => ({
          product_id: parseInt(l.product_id),
          description: l.description,
          quantity_ordered: parseFloat(l.quantity_ordered),
          unit_cost: parseFloat(l.unit_cost) || 0,
          tax_id: l.tax_id ? parseInt(l.tax_id) : null,
        })),
    }

    setSaving(true)
    try {
      if (isEdit) {
        await updatePurchaseOrder(id, payload)
        toast.success('Purchase order updated')
      } else {
        await createPurchaseOrder(payload)
        toast.success(send ? 'Purchase order created and sent' : 'Purchase order created')
      }
      navigate('/purchase-orders')
    } catch (err) {
      toast.error(err.message || 'Failed to save purchase order')
    } finally {
      setSaving(false)
    }
  }

  if (!loaded) return <div className="p-6 text-gray-500">Loading...</div>

  return (
    <div className="p-6">
      <PageHeader title={isEdit ? 'Edit Purchase Order' : 'New Purchase Order'} />

      <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <FormField label="Supplier" required>
            <Select
              value={form.supplier_contact_id}
              onChange={(e) => setForm({ ...form, supplier_contact_id: e.target.value })}
            >
              <option value="">Select supplier...</option>
              {(contacts || []).map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </Select>
          </FormField>
          <FormField label="Order Date" required>
            <Input
              type="date"
              value={form.order_date}
              onChange={(e) => setForm({ ...form, order_date: e.target.value })}
            />
          </FormField>
          <FormField label="Expected Date">
            <Input
              type="date"
              value={form.expected_date}
              onChange={(e) => setForm({ ...form, expected_date: e.target.value })}
            />
          </FormField>
          <FormField label="Notes">
            <Input
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              placeholder="Internal notes"
            />
          </FormField>
        </div>

        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Line Items</h3>
          <div className="grid grid-cols-12 gap-2 mb-2 text-xs text-gray-500 uppercase font-medium">
            <div className="col-span-3">Product</div>
            <div className="col-span-3">Description</div>
            <div className="col-span-2">Qty</div>
            <div className="col-span-2">Unit Cost</div>
            <div className="col-span-1">Tax</div>
            <div className="col-span-1"></div>
          </div>
          {form.lines.map((line, i) => (
            <div key={i} className="grid grid-cols-12 gap-2 items-end mb-2">
              <div className="col-span-3">
                <Select value={line.product_id} onChange={(e) => selectProduct(i, e.target.value)}>
                  <option value="">Select product...</option>
                  {(products || []).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.sku ? `${p.sku} — ` : ''}{p.name}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="col-span-3">
                <Input
                  value={line.description}
                  onChange={(e) => updateLine(i, 'description', e.target.value)}
                  placeholder="Description"
                />
              </div>
              <div className="col-span-2">
                <Input
                  type="number"
                  min="0"
                  step="any"
                  value={line.quantity_ordered}
                  onChange={(e) => updateLine(i, 'quantity_ordered', e.target.value)}
                  placeholder="Qty"
                />
              </div>
              <div className="col-span-2">
                <Input
                  type="number"
                  min="0"
                  step="any"
                  value={line.unit_cost}
                  onChange={(e) => updateLine(i, 'unit_cost', e.target.value)}
                  placeholder="Cost"
                />
              </div>
              <div className="col-span-1">
                <Select value={line.tax_id} onChange={(e) => updateLine(i, 'tax_id', e.target.value)}>
                  <option value="">None</option>
                  {(taxes || []).map((t) => (
                    <option key={t.id} value={t.id}>{t.code}</option>
                  ))}
                </Select>
              </div>
              <div className="col-span-1">
                <button
                  type="button"
                  onClick={() => removeLine(i)}
                  disabled={form.lines.length <= 1}
                  className="text-red-500 hover:text-red-700 disabled:opacity-30 text-sm p-1"
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
          <button
            type="button"
            onClick={addLine}
            className="text-sm text-accent hover:text-navy mt-2"
          >
            + Add Line
          </button>
        </div>

        <div className="flex justify-between items-center border-t pt-4">
          <div className="text-lg font-semibold text-gray-800">
            Total: {formatCurrency(totals.subtotal)}
          </div>
          <div className="flex gap-3">
            <Button variant="secondary" onClick={() => navigate('/purchase-orders')}>
              Cancel
            </Button>
            <Button variant="secondary" onClick={() => handleSubmit(false)} disabled={saving}>
              {saving ? 'Saving...' : 'Save Draft'}
            </Button>
            {!isEdit && (
              <Button onClick={() => handleSubmit(true)} disabled={saving}>
                Save & Send
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
