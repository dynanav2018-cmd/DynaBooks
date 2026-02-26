import { useState } from 'react'
import { useApi } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import { fetchReceipts, createReceipt, fetchPayments, createPayment, createAssignment } from '../../api/banking'
import { fetchAccounts } from '../../api/accounts'
import { fetchInvoices } from '../../api/invoices'
import { fetchBills } from '../../api/bills'
import { formatCurrency, formatDate, todayISO } from '../../utils/format'
import DataTable from '../../components/shared/DataTable'
import PageHeader from '../../components/shared/PageHeader'
import Button from '../../components/shared/Button'
import StatusBadge from '../../components/shared/StatusBadge'
import Modal from '../../components/shared/Modal'
import FormField, { Input, Select } from '../../components/shared/FormField'

export default function BankingIndex() {
  const [tab, setTab] = useState('receipts')
  const toast = useToast()

  const { data: receipts, loading: loadingReceipts, refetch: refetchReceipts } = useApi(fetchReceipts)
  const { data: payments, loading: loadingPayments, refetch: refetchPayments } = useApi(fetchPayments)
  const { data: bankAccounts } = useApi(() => fetchAccounts('Bank'), [])
  const { data: invoices } = useApi(fetchInvoices, [])
  const { data: bills } = useApi(fetchBills, [])

  const [showReceiptModal, setShowReceiptModal] = useState(false)
  const [showPaymentModal, setShowPaymentModal] = useState(false)

  const [receiptForm, setReceiptForm] = useState({
    narration: 'Client Receipt',
    transaction_date: todayISO(),
    bank_account_id: '',
    amount: '',
    assign_invoice_id: '',
  })

  const [paymentForm, setPaymentForm] = useState({
    narration: 'Supplier Payment',
    transaction_date: todayISO(),
    bank_account_id: '',
    amount: '',
    assign_bill_id: '',
  })

  const [saving, setSaving] = useState(false)

  const handleCreateReceipt = async () => {
    if (!receiptForm.bank_account_id || !receiptForm.amount) {
      toast.error('Bank account and amount are required')
      return
    }
    setSaving(true)
    try {
      const result = await createReceipt({
        narration: receiptForm.narration,
        transaction_date: receiptForm.transaction_date,
        line_items: [{
          narration: receiptForm.narration,
          account_id: parseInt(receiptForm.bank_account_id),
          amount: parseFloat(receiptForm.amount),
        }],
        post: true,
      })

      if (receiptForm.assign_invoice_id) {
        await createAssignment({
          transaction_id: result.id,
          assigned_id: parseInt(receiptForm.assign_invoice_id),
          assigned_type: 'ClientInvoice',
          amount: parseFloat(receiptForm.amount),
          assignment_date: receiptForm.transaction_date,
        })
        toast.success('Receipt created and assigned to invoice')
      } else {
        toast.success('Receipt created')
      }

      setShowReceiptModal(false)
      setReceiptForm({
        narration: 'Client Receipt',
        transaction_date: todayISO(),
        bank_account_id: '',
        amount: '',
        assign_invoice_id: '',
      })
      refetchReceipts()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleCreatePayment = async () => {
    if (!paymentForm.bank_account_id || !paymentForm.amount) {
      toast.error('Bank account and amount are required')
      return
    }
    setSaving(true)
    try {
      const result = await createPayment({
        narration: paymentForm.narration,
        transaction_date: paymentForm.transaction_date,
        line_items: [{
          narration: paymentForm.narration,
          account_id: parseInt(paymentForm.bank_account_id),
          amount: parseFloat(paymentForm.amount),
        }],
        post: true,
      })

      if (paymentForm.assign_bill_id) {
        await createAssignment({
          transaction_id: result.id,
          assigned_id: parseInt(paymentForm.assign_bill_id),
          assigned_type: 'SupplierBill',
          amount: parseFloat(paymentForm.amount),
          assignment_date: paymentForm.transaction_date,
        })
        toast.success('Payment created and assigned to bill')
      } else {
        toast.success('Payment created')
      }

      setShowPaymentModal(false)
      setPaymentForm({
        narration: 'Supplier Payment',
        transaction_date: todayISO(),
        bank_account_id: '',
        amount: '',
        assign_bill_id: '',
      })
      refetchPayments()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  const receiptColumns = [
    { key: 'transaction_no', label: 'Receipt #' },
    { key: 'transaction_date', label: 'Date', render: (v) => formatDate(v) },
    { key: 'narration', label: 'Description' },
    {
      key: 'amount',
      label: 'Amount',
      render: (v) => <span className="font-medium text-green-700">{formatCurrency(v)}</span>,
    },
    {
      key: 'is_posted',
      label: 'Status',
      render: (v) => <StatusBadge status={v ? 'Posted' : 'Draft'} />,
    },
  ]

  const paymentColumns = [
    { key: 'transaction_no', label: 'Payment #' },
    { key: 'transaction_date', label: 'Date', render: (v) => formatDate(v) },
    { key: 'narration', label: 'Description' },
    {
      key: 'amount',
      label: 'Amount',
      render: (v) => <span className="font-medium text-red-700">{formatCurrency(v)}</span>,
    },
    {
      key: 'is_posted',
      label: 'Status',
      render: (v) => <StatusBadge status={v ? 'Posted' : 'Draft'} />,
    },
  ]

  const postedInvoices = invoices?.filter((inv) => inv.is_posted) || []
  const postedBills = bills?.filter((b) => b.is_posted) || []

  return (
    <div>
      <PageHeader title="Banking">
        {tab === 'receipts' ? (
          <Button onClick={() => setShowReceiptModal(true)}>New Receipt</Button>
        ) : (
          <Button onClick={() => setShowPaymentModal(true)}>New Payment</Button>
        )}
      </PageHeader>

      <div className="flex gap-1 mb-4 bg-gray-100 rounded-lg p-1 w-fit">
        {[
          { key: 'receipts', label: 'Receipts' },
          { key: 'payments', label: 'Payments' },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              tab === t.key
                ? 'bg-white text-navy shadow-sm'
                : 'text-gray-600 hover:text-gray-800'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'receipts' && (
        <DataTable
          columns={receiptColumns}
          data={receipts || []}
          emptyMessage="No receipts found"
        />
      )}

      {tab === 'payments' && (
        <DataTable
          columns={paymentColumns}
          data={payments || []}
          emptyMessage="No payments found"
        />
      )}

      {/* Receipt Modal */}
      <Modal open={showReceiptModal} onClose={() => setShowReceiptModal(false)} title="New Receipt" wide>
        <div className="space-y-4">
          <FormField label="Description">
            <Input
              value={receiptForm.narration}
              onChange={(e) => setReceiptForm({ ...receiptForm, narration: e.target.value })}
            />
          </FormField>
          <FormField label="Date" required>
            <Input
              type="date"
              value={receiptForm.transaction_date}
              onChange={(e) => setReceiptForm({ ...receiptForm, transaction_date: e.target.value })}
            />
          </FormField>
          <FormField label="Bank Account" required>
            <Select
              value={receiptForm.bank_account_id}
              onChange={(e) => setReceiptForm({ ...receiptForm, bank_account_id: e.target.value })}
            >
              <option value="">Select bank account...</option>
              {bankAccounts?.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </Select>
          </FormField>
          <FormField label="Amount" required>
            <Input
              type="number"
              min="0"
              step="0.01"
              value={receiptForm.amount}
              onChange={(e) => setReceiptForm({ ...receiptForm, amount: e.target.value })}
              placeholder="0.00"
            />
          </FormField>
          <FormField label="Assign to Invoice">
            <Select
              value={receiptForm.assign_invoice_id}
              onChange={(e) => setReceiptForm({ ...receiptForm, assign_invoice_id: e.target.value })}
            >
              <option value="">None (unassigned)</option>
              {postedInvoices.map((inv) => (
                <option key={inv.id} value={inv.id}>
                  {inv.transaction_no} - {formatCurrency(inv.amount)}
                </option>
              ))}
            </Select>
          </FormField>
          <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
            <Button variant="secondary" onClick={() => setShowReceiptModal(false)} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={handleCreateReceipt} disabled={saving}>
              Create Receipt
            </Button>
          </div>
        </div>
      </Modal>

      {/* Payment Modal */}
      <Modal open={showPaymentModal} onClose={() => setShowPaymentModal(false)} title="New Payment" wide>
        <div className="space-y-4">
          <FormField label="Description">
            <Input
              value={paymentForm.narration}
              onChange={(e) => setPaymentForm({ ...paymentForm, narration: e.target.value })}
            />
          </FormField>
          <FormField label="Date" required>
            <Input
              type="date"
              value={paymentForm.transaction_date}
              onChange={(e) => setPaymentForm({ ...paymentForm, transaction_date: e.target.value })}
            />
          </FormField>
          <FormField label="Bank Account" required>
            <Select
              value={paymentForm.bank_account_id}
              onChange={(e) => setPaymentForm({ ...paymentForm, bank_account_id: e.target.value })}
            >
              <option value="">Select bank account...</option>
              {bankAccounts?.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </Select>
          </FormField>
          <FormField label="Amount" required>
            <Input
              type="number"
              min="0"
              step="0.01"
              value={paymentForm.amount}
              onChange={(e) => setPaymentForm({ ...paymentForm, amount: e.target.value })}
              placeholder="0.00"
            />
          </FormField>
          <FormField label="Assign to Bill">
            <Select
              value={paymentForm.assign_bill_id}
              onChange={(e) => setPaymentForm({ ...paymentForm, assign_bill_id: e.target.value })}
            >
              <option value="">None (unassigned)</option>
              {postedBills.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.transaction_no} - {formatCurrency(b.amount)}
                </option>
              ))}
            </Select>
          </FormField>
          <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
            <Button variant="secondary" onClick={() => setShowPaymentModal(false)} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={handleCreatePayment} disabled={saving}>
              Create Payment
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
