import { useParams, useNavigate, Link } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import { fetchInvoice, postInvoice, deleteInvoice, downloadInvoicePdf } from '../../api/invoices'
import { formatCurrency, formatDate } from '../../utils/format'
import PageHeader from '../../components/shared/PageHeader'
import Button from '../../components/shared/Button'
import StatusBadge from '../../components/shared/StatusBadge'
import LoadingSpinner from '../../components/shared/LoadingSpinner'
import { useSettings } from '../../hooks/useSettings'

export default function InvoiceDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const { data: invoice, loading, refetch } = useApi(() => fetchInvoice(id), [id])
  const { allowEditPosted } = useSettings()

  const handlePost = async () => {
    try {
      await postInvoice(id)
      toast.success('Invoice posted')
      refetch()
    } catch (err) {
      toast.error(err.message)
    }
  }

  const handleDelete = async () => {
    if (!confirm('Delete this invoice?')) return
    try {
      await deleteInvoice(id)
      toast.success('Invoice deleted')
      navigate('/invoices')
    } catch (err) {
      toast.error(err.message)
    }
  }

  const handleDownloadPdf = async () => {
    try {
      const blob = await downloadInvoicePdf(id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `invoice-${invoice.transaction_no || id}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      toast.error('PDF download failed: ' + err.message)
    }
  }

  if (loading) return <LoadingSpinner />
  if (!invoice) return <p className="text-red-600">Invoice not found</p>

  return (
    <div>
      <PageHeader title={`Invoice ${invoice.transaction_no || `#${id}`}`}>
        <div className="flex gap-2">
          {invoice.is_posted && (
            <Button variant="secondary" onClick={handleDownloadPdf}>Download PDF</Button>
          )}
          {(!invoice.is_posted || allowEditPosted) && (
            <>
              <Link to={`/invoices/${id}/edit`}>
                <Button variant="secondary">Edit</Button>
              </Link>
              {!invoice.is_posted && (
                <Button onClick={handlePost}>Post Invoice</Button>
              )}
              <Button variant="danger" onClick={handleDelete}>Delete</Button>
            </>
          )}
          <Button variant="ghost" onClick={() => navigate('/invoices')}>Back</Button>
        </div>
      </PageHeader>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-6 mb-8">
          <div>
            <p className="text-xs text-gray-500 uppercase font-medium">Status</p>
            <StatusBadge status={invoice.is_posted ? 'Posted' : 'Draft'} />
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase font-medium">Client</p>
            <p className="text-sm font-medium">{invoice.contact_name || '—'}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase font-medium">Date</p>
            <p className="text-sm font-medium">{formatDate(invoice.transaction_date)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase font-medium">Amount</p>
            <p className="text-lg font-bold text-accent">{formatCurrency(invoice.amount)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase font-medium">Description</p>
            <p className="text-sm">{invoice.narration}</p>
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
              {invoice.line_items?.map((li, i) => (
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
            {invoice.tax && Object.keys(invoice.tax.taxes || {}).length > 0 && (
              <>
                <div className="flex justify-between text-gray-600">
                  <span>Subtotal</span>
                  <span>{formatCurrency(invoice.amount - (invoice.tax.total || 0))}</span>
                </div>
                {Object.entries(invoice.tax.taxes).map(([code, info]) => (
                  <div key={code} className="flex justify-between text-gray-600">
                    <span>{info.name} ({info.rate}%)</span>
                    <span>{formatCurrency(info.amount)}</span>
                  </div>
                ))}
              </>
            )}
            <div className="flex justify-between font-bold text-gray-900 border-t border-gray-200 pt-2">
              <span>Total</span>
              <span>{formatCurrency(invoice.amount)}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
