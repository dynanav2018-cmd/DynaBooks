import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import {
  fetchPurchaseOrder,
  sendPurchaseOrder,
  cancelPurchaseOrder,
  deletePurchaseOrder,
} from '../../api/purchaseOrders'
import PageHeader from '../../components/shared/PageHeader'
import Button from '../../components/shared/Button'
import DataTable from '../../components/shared/DataTable'
import StatusBadge from '../../components/shared/StatusBadge'
import ReceiveModal from './ReceiveModal'

const formatCurrency = (v) => {
  const n = Number(v) || 0
  return new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(n)
}

const formatDate = (v) => {
  if (!v) return ''
  return new Date(v).toLocaleDateString('en-CA')
}

export default function PurchaseOrderDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const { data: po, loading, refetch } = useApi(() => fetchPurchaseOrder(id), [id])
  const [showReceive, setShowReceive] = useState(false)
  const [acting, setActing] = useState(false)

  if (loading) return <div className="p-6 text-gray-500">Loading...</div>
  if (!po) return <div className="p-6 text-gray-500">Purchase order not found</div>

  const handleSend = async () => {
    setActing(true)
    try {
      await sendPurchaseOrder(id)
      toast.success('Purchase order marked as sent')
      refetch()
    } catch (err) {
      toast.error(err.message || 'Failed to send')
    } finally {
      setActing(false)
    }
  }

  const handleCancel = async () => {
    if (!confirm('Cancel this purchase order?')) return
    setActing(true)
    try {
      await cancelPurchaseOrder(id)
      toast.success('Purchase order cancelled')
      refetch()
    } catch (err) {
      toast.error(err.message || 'Failed to cancel')
    } finally {
      setActing(false)
    }
  }

  const handleDelete = async () => {
    if (!confirm('Delete this purchase order?')) return
    setActing(true)
    try {
      await deletePurchaseOrder(id)
      toast.success('Purchase order deleted')
      navigate('/purchase-orders')
    } catch (err) {
      toast.error(err.message || 'Failed to delete')
    } finally {
      setActing(false)
    }
  }

  const columns = [
    { key: 'product_name', label: 'Product' },
    { key: 'description', label: 'Description' },
    { key: 'quantity_ordered', label: 'Ordered', render: (v) => Number(v).toFixed(0) },
    { key: 'quantity_received', label: 'Received', render: (v) => Number(v).toFixed(0) },
    { key: 'unit_cost', label: 'Unit Cost', render: formatCurrency },
    {
      key: '_total',
      label: 'Line Total',
      render: (_, row) => formatCurrency(row.quantity_ordered * row.unit_cost),
    },
  ]

  return (
    <div className="p-6">
      <PageHeader title={`Purchase Order ${po.po_number}`}>
        {po.status === 'draft' && (
          <>
            <Button variant="secondary" onClick={() => navigate(`/purchase-orders/${id}/edit`)} disabled={acting}>
              Edit
            </Button>
            <Button onClick={handleSend} disabled={acting}>Send</Button>
            <Button variant="danger" onClick={handleDelete} disabled={acting}>Delete</Button>
          </>
        )}
        {(po.status === 'sent' || po.status === 'partial') && (
          <>
            <Button onClick={() => setShowReceive(true)} disabled={acting}>
              Receive Goods
            </Button>
            <Button variant="danger" onClick={handleCancel} disabled={acting}>Cancel</Button>
          </>
        )}
        {po.bill_id && (
          <Link to={`/bills/${po.bill_id}`}>
            <Button variant="secondary">View Bill</Button>
          </Link>
        )}
      </PageHeader>

      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <p className="text-xs text-gray-500 uppercase font-medium">Supplier</p>
            <p className="text-sm font-medium text-gray-800 mt-1">{po.supplier_name}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase font-medium">Order Date</p>
            <p className="text-sm font-medium text-gray-800 mt-1">{formatDate(po.order_date)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase font-medium">Expected Date</p>
            <p className="text-sm font-medium text-gray-800 mt-1">{formatDate(po.expected_date) || '—'}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase font-medium">Status</p>
            <p className="mt-1">
              <StatusBadge status={po.status.charAt(0).toUpperCase() + po.status.slice(1)} />
            </p>
          </div>
        </div>
        {po.notes && (
          <div className="mt-4">
            <p className="text-xs text-gray-500 uppercase font-medium">Notes</p>
            <p className="text-sm text-gray-700 mt-1">{po.notes}</p>
          </div>
        )}
      </div>

      <h3 className="text-lg font-semibold text-gray-800 mb-4">Line Items</h3>
      <DataTable columns={columns} data={po.lines || []} emptyMessage="No lines" />

      <div className="mt-4 text-right">
        <span className="text-lg font-semibold text-gray-800">
          Total: {formatCurrency(po.total)}
        </span>
      </div>

      {showReceive && (
        <ReceiveModal
          po={po}
          onClose={() => setShowReceive(false)}
          onReceived={(billId) => {
            setShowReceive(false)
            toast.success('Goods received. Bill created.')
            if (billId) {
              navigate(`/bills/${billId}`)
            } else {
              refetch()
            }
          }}
        />
      )}
    </div>
  )
}
