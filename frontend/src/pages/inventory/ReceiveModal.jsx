import { useState } from 'react'
import { useToast } from '../../hooks/useToast'
import { receivePurchaseOrder } from '../../api/purchaseOrders'
import Modal from '../../components/shared/Modal'
import Button from '../../components/shared/Button'
import { Input } from '../../components/shared/FormField'

export default function ReceiveModal({ po, onClose, onReceived }) {
  const toast = useToast()
  const [saving, setSaving] = useState(false)

  // Initialize quantities to receive: remaining = ordered - received
  const [quantities, setQuantities] = useState(() => {
    const q = {}
    for (const line of po.lines || []) {
      const remaining = (line.quantity_ordered || 0) - (line.quantity_received || 0)
      q[line.id] = String(Math.max(0, remaining))
    }
    return q
  })

  const handleSubmit = async (e) => {
    e.preventDefault()

    const received_quantities = {}
    for (const [lineId, qty] of Object.entries(quantities)) {
      const n = parseFloat(qty) || 0
      if (n > 0) {
        received_quantities[lineId] = n
      }
    }

    if (Object.keys(received_quantities).length === 0) {
      toast.error('Enter at least one quantity to receive')
      return
    }

    setSaving(true)
    try {
      const result = await receivePurchaseOrder(po.id, { received_quantities })
      onReceived(result.bill_id)
    } catch (err) {
      toast.error(err.message || 'Failed to receive goods')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open onClose={onClose} title={`Receive: ${po.po_number}`} wide>
      <form onSubmit={handleSubmit}>
        <table className="w-full text-sm mb-4">
          <thead>
            <tr className="text-left text-xs text-gray-500 uppercase border-b">
              <th className="py-2">Product</th>
              <th className="py-2">Ordered</th>
              <th className="py-2">Already Received</th>
              <th className="py-2">Qty to Receive</th>
            </tr>
          </thead>
          <tbody>
            {(po.lines || []).map((line) => {
              const remaining = (line.quantity_ordered || 0) - (line.quantity_received || 0)
              return (
                <tr key={line.id} className="border-b">
                  <td className="py-2">{line.product_name || line.description}</td>
                  <td className="py-2">{Number(line.quantity_ordered).toFixed(0)}</td>
                  <td className="py-2">{Number(line.quantity_received).toFixed(0)}</td>
                  <td className="py-2 w-32">
                    <Input
                      type="number"
                      min="0"
                      max={remaining}
                      step="any"
                      value={quantities[line.id] || ''}
                      onChange={(e) =>
                        setQuantities((prev) => ({ ...prev, [line.id]: e.target.value }))
                      }
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>

        <div className="flex justify-end gap-3">
          <Button variant="secondary" type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={saving}>
            {saving ? 'Receiving...' : 'Receive & Create Bill'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
