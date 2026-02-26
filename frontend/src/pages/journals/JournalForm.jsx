import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useToast } from '../../hooks/useToast'
import { useApi } from '../../hooks/useApi'
import { createJournal } from '../../api/journals'
import { fetchAccounts } from '../../api/accounts'
import { todayISO } from '../../utils/format'
import PageHeader from '../../components/shared/PageHeader'
import Button from '../../components/shared/Button'
import FormField, { Input, Select } from '../../components/shared/FormField'

const emptyLine = { narration: '', account_id: '', debit: '', credit: '' }

export default function JournalForm() {
  const navigate = useNavigate()
  const toast = useToast()

  const { data: accounts } = useApi(fetchAccounts, [])

  const [form, setForm] = useState({
    account_id: '',
    transaction_date: todayISO(),
    narration: 'Journal Entry',
    line_items: [{ ...emptyLine }, { ...emptyLine }],
  })
  const [saving, setSaving] = useState(false)

  const updateLine = (index, field, value) => {
    setForm((prev) => {
      const lines = [...prev.line_items]
      const updated = { ...lines[index], [field]: value }
      // Clear the opposite column when entering a value
      if (field === 'debit' && value) updated.credit = ''
      if (field === 'credit' && value) updated.debit = ''
      lines[index] = updated
      return { ...prev, line_items: lines }
    })
  }

  const addLine = () => {
    setForm((prev) => ({ ...prev, line_items: [...prev.line_items, { ...emptyLine }] }))
  }

  const removeLine = (index) => {
    if (form.line_items.length <= 2) return
    setForm((prev) => ({
      ...prev,
      line_items: prev.line_items.filter((_, i) => i !== index),
    }))
  }

  const totals = useMemo(() => {
    let totalDebits = 0
    let totalCredits = 0
    form.line_items.forEach((li) => {
      totalDebits += parseFloat(li.debit) || 0
      totalCredits += parseFloat(li.credit) || 0
    })
    return { totalDebits, totalCredits, balanced: Math.abs(totalDebits - totalCredits) < 0.005 }
  }, [form.line_items])

  const handleSubmit = async () => {
    if (!form.account_id) {
      toast.error('Please select a main account')
      return
    }
    if (!totals.balanced) {
      toast.error('Debits and credits must be equal')
      return
    }

    const validLines = form.line_items.filter((li) =>
      li.account_id && (parseFloat(li.debit) > 0 || parseFloat(li.credit) > 0)
    )
    if (validLines.length === 0) {
      toast.error('At least one line item is required')
      return
    }

    setSaving(true)
    try {
      const payload = {
        narration: form.narration,
        transaction_date: form.transaction_date,
        account_id: parseInt(form.account_id),
        post: true,
        line_items: validLines.map((li) => {
          const isCredit = parseFloat(li.credit) > 0
          return {
            narration: li.narration,
            account_id: parseInt(li.account_id),
            amount: isCredit ? parseFloat(li.credit) : parseFloat(li.debit),
            credited: isCredit,
          }
        }),
      }

      await createJournal(payload)
      toast.success('Journal entry created & posted')
      navigate('/journals')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  const fmtCurrency = (v) => `$${v.toFixed(2)}`

  return (
    <div>
      <PageHeader title="New Journal Entry">
        <Button variant="secondary" onClick={() => navigate('/journals')}>Cancel</Button>
      </PageHeader>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <FormField label="Main Account" required>
            <Select value={form.account_id} onChange={(e) => setForm({ ...form, account_id: e.target.value })} required>
              <option value="">Select account...</option>
              {accounts?.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </Select>
          </FormField>
          <FormField label="Date" required>
            <Input
              type="date"
              value={form.transaction_date}
              onChange={(e) => setForm({ ...form, transaction_date: e.target.value })}
              required
            />
          </FormField>
          <FormField label="Description">
            <Input
              value={form.narration}
              onChange={(e) => setForm({ ...form, narration: e.target.value })}
            />
          </FormField>
        </div>

        <h3 className="text-sm font-semibold text-gray-700 mb-3">Line Items</h3>
        <div className="space-y-3">
          {form.line_items.map((li, i) => (
            <div key={i} className="grid grid-cols-12 gap-2 items-end">
              <div className="col-span-4">
                {i === 0 && <label className="block text-xs text-gray-500 mb-1">Account</label>}
                <Select value={li.account_id} onChange={(e) => updateLine(i, 'account_id', e.target.value)} required>
                  <option value="">Account...</option>
                  {accounts?.map((a) => (
                    <option key={a.id} value={a.id}>{a.name}</option>
                  ))}
                </Select>
              </div>
              <div className="col-span-3">
                {i === 0 && <label className="block text-xs text-gray-500 mb-1">Description</label>}
                <Input
                  value={li.narration}
                  onChange={(e) => updateLine(i, 'narration', e.target.value)}
                  placeholder="Description"
                />
              </div>
              <div className="col-span-2">
                {i === 0 && <label className="block text-xs text-gray-500 mb-1">Debit</label>}
                <Input
                  type="number"
                  min="0"
                  step="0.01"
                  value={li.debit}
                  onChange={(e) => updateLine(i, 'debit', e.target.value)}
                  placeholder="0.00"
                />
              </div>
              <div className="col-span-2">
                {i === 0 && <label className="block text-xs text-gray-500 mb-1">Credit</label>}
                <Input
                  type="number"
                  min="0"
                  step="0.01"
                  value={li.credit}
                  onChange={(e) => updateLine(i, 'credit', e.target.value)}
                  placeholder="0.00"
                />
              </div>
              <div className="col-span-1">
                <button
                  type="button"
                  onClick={() => removeLine(i)}
                  className="p-2 text-red-400 hover:text-red-600 disabled:opacity-30"
                  disabled={form.line_items.length <= 2}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
          ))}
        </div>

        <button
          type="button"
          onClick={addLine}
          className="mt-3 text-sm text-accent hover:text-accent-dark font-medium"
        >
          + Add Line Item
        </button>

        <div className="mt-6 flex justify-end">
          <div className="w-64 space-y-1 text-sm">
            <div className="flex justify-between text-gray-600">
              <span>Total Debits</span>
              <span>{fmtCurrency(totals.totalDebits)}</span>
            </div>
            <div className="flex justify-between text-gray-600">
              <span>Total Credits</span>
              <span>{fmtCurrency(totals.totalCredits)}</span>
            </div>
            <div className={`flex justify-between font-bold text-base border-t border-gray-200 pt-2 ${
              totals.balanced ? 'text-green-700' : 'text-red-600'
            }`}>
              <span>Difference</span>
              <span>{fmtCurrency(Math.abs(totals.totalDebits - totals.totalCredits))}</span>
            </div>
            {!totals.balanced && (
              <p className="text-xs text-red-500">Debits and credits must balance</p>
            )}
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-8 pt-4 border-t border-gray-200">
          <Button variant="secondary" onClick={() => navigate('/journals')} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={saving || !totals.balanced}>
            Save & Post
          </Button>
        </div>
      </div>
    </div>
  )
}
