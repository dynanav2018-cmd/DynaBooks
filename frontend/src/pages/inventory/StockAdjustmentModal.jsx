import { useState } from 'react'
import { useApi } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import { fetchInventory, createStockAdjustment } from '../../api/inventory'
import Modal from '../../components/shared/Modal'
import Button from '../../components/shared/Button'
import FormField, { Input, Select } from '../../components/shared/FormField'

export default function StockAdjustmentModal({ productId, onClose, onSaved }) {
  const toast = useToast()
  const { data: products } = useApi(fetchInventory)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    product_id: productId ? String(productId) : '',
    adjustment_type: 'increase',
    quantity: '',
    unit_cost: '',
    notes: '',
  })

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.product_id || !form.quantity) {
      toast.error('Product and quantity are required')
      return
    }

    const qty = parseFloat(form.quantity)
    if (isNaN(qty) || qty <= 0) {
      toast.error('Quantity must be a positive number')
      return
    }

    const quantity_change = form.adjustment_type === 'increase' ? qty : -qty

    const payload = {
      product_id: parseInt(form.product_id),
      quantity_change,
      notes: form.notes,
    }
    if (form.adjustment_type === 'increase' && form.unit_cost) {
      payload.unit_cost = parseFloat(form.unit_cost)
    }

    setSaving(true)
    try {
      await createStockAdjustment(payload)
      toast.success('Stock adjustment recorded')
      onSaved()
    } catch (err) {
      toast.error(err.message || 'Failed to create adjustment')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open onClose={onClose} title="Stock Adjustment" wide>
      <form onSubmit={handleSubmit} className="space-y-4">
        {!productId && (
          <FormField label="Product" required>
            <Select
              value={form.product_id}
              onChange={(e) => setForm({ ...form, product_id: e.target.value })}
            >
              <option value="">Select product...</option>
              {(products || []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.sku ? `${p.sku} — ` : ''}{p.name} (On hand: {Number(p.quantity_on_hand).toFixed(0)})
                </option>
              ))}
            </Select>
          </FormField>
        )}

        <FormField label="Adjustment Type" required>
          <Select
            value={form.adjustment_type}
            onChange={(e) => setForm({ ...form, adjustment_type: e.target.value })}
          >
            <option value="increase">Increase (Stock In)</option>
            <option value="decrease">Decrease / Write-Off (Stock Out)</option>
          </Select>
        </FormField>

        <FormField label="Quantity" required>
          <Input
            type="number"
            min="0.0001"
            step="any"
            value={form.quantity}
            onChange={(e) => setForm({ ...form, quantity: e.target.value })}
            placeholder="Enter quantity"
          />
        </FormField>

        {form.adjustment_type === 'increase' && (
          <FormField label="Unit Cost">
            <Input
              type="number"
              min="0"
              step="any"
              value={form.unit_cost}
              onChange={(e) => setForm({ ...form, unit_cost: e.target.value })}
              placeholder="Cost per unit (for WAC calc)"
            />
          </FormField>
        )}

        <FormField label="Notes">
          <Input
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            placeholder="Reason for adjustment"
          />
        </FormField>

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="secondary" type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={saving}>
            {saving ? 'Saving...' : 'Record Adjustment'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
