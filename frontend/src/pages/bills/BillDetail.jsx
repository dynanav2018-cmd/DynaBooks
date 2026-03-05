import { useParams, useNavigate, Link } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import { fetchBill, postBill, deleteBill, downloadBillPdf } from '../../api/bills'
import { formatCurrency, formatDate } from '../../utils/format'
import PageHeader from '../../components/shared/PageHeader'
import Button from '../../components/shared/Button'
import StatusBadge from '../../components/shared/StatusBadge'
import LoadingSpinner from '../../components/shared/LoadingSpinner'
import { useSettings } from '../../hooks/useSettings'

export default function BillDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const { data: bill, loading, refetch } = useApi(() => fetchBill(id), [id])
  const { allowEditPosted } = useSettings()

  const handlePost = async () => {
    try {
      await postBill(id)
      toast.success('Bill posted')
      refetch()
    } catch (err) {
      toast.error(err.message)
    }
  }

  const handleDelete = async () => {
    if (!confirm('Delete this bill?')) return
    try {
      await deleteBill(id)
      toast.success('Bill deleted')
      navigate('/bills')
    } catch (err) {
      toast.error(err.message)
    }
  }

  const handleDownloadPdf = async () => {
    try {
      const blob = await downloadBillPdf(id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `bill-${bill.transaction_no || id}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      toast.error('PDF download failed: ' + err.message)
    }
  }

  if (loading) return <LoadingSpinner />
  if (!bill) return <p className="text-red-600">Bill not found</p>

  return (
    <div>
      <PageHeader title={`Bill ${bill.transaction_no || `#${id}`}`}>
        <div className="flex gap-2">
          {bill.is_posted && (
            <Button variant="secondary" onClick={handleDownloadPdf}>Download PDF</Button>
          )}
          {(!bill.is_posted || allowEditPosted) && (
            <>
              <Link to={`/bills/${id}/edit`}>
                <Button variant="secondary">Edit</Button>
              </Link>
              {!bill.is_posted && (
                <Button onClick={handlePost}>Post Bill</Button>
              )}
              <Button variant="danger" onClick={handleDelete}>Delete</Button>
            </>
          )}
          <Button variant="ghost" onClick={() => navigate('/bills')}>Back</Button>
        </div>
      </PageHeader>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-6 mb-8">
          <div>
            <p className="text-xs text-gray-500 uppercase font-medium">Status</p>
            <StatusBadge status={bill.is_posted ? 'Posted' : 'Draft'} />
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase font-medium">Supplier</p>
            <p className="text-sm font-medium">{bill.contact_name || '—'}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase font-medium">Date</p>
            <p className="text-sm font-medium">{formatDate(bill.transaction_date)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase font-medium">Amount</p>
            <p className="text-lg font-bold text-accent">{formatCurrency(bill.amount)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase font-medium">Description</p>
            <p className="text-sm">{bill.narration}</p>
          </div>
        </div>

        <h3 className="text-sm font-semibold text-gray-700 mb-3">Line Items</h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="text-left px-4 py-2 text-xs font-semibold text-gray-600">Description</th>
                <th className="text-right px-4 py-2 text-xs font-semibold text-gray-600">Qty</th>
                <th className="text-right px-4 py-2 text-xs font-semibold text-gray-600">Amount</th>
                <th className="text-right px-4 py-2 text-xs font-semibold text-gray-600">Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {bill.line_items?.map((li, i) => (
                <tr key={i}>
                  <td className="px-4 py-3 text-sm">{li.narration || '-'}</td>
                  <td className="px-4 py-3 text-sm text-right">{li.quantity}</td>
                  <td className="px-4 py-3 text-sm text-right">{formatCurrency(li.amount)}</td>
                  <td className="px-4 py-3 text-sm text-right font-medium">
                    {formatCurrency(li.amount * li.quantity)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-4 flex justify-end">
          <div className="w-64 space-y-1 text-sm">
            {bill.tax && Object.keys(bill.tax.taxes || {}).length > 0 && (
              <>
                <div className="flex justify-between text-gray-600">
                  <span>Subtotal</span>
                  <span>{formatCurrency(bill.amount - (bill.tax.total || 0))}</span>
                </div>
                {Object.entries(bill.tax.taxes).map(([code, info]) => (
                  <div key={code} className="flex justify-between text-gray-600">
                    <span>{info.name} ({info.rate}%)</span>
                    <span>{formatCurrency(info.amount)}</span>
                  </div>
                ))}
              </>
            )}
            <div className="flex justify-between font-bold text-gray-900 border-t border-gray-200 pt-2">
              <span>Total</span>
              <span>{formatCurrency(bill.amount)}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
