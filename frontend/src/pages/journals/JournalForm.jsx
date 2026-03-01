import { useState, useEffect, useMemo } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useToast } from '../../hooks/useToast'
import { useApi } from '../../hooks/useApi'
import { createJournal, fetchJournal, updateJournal } from '../../api/journals'
import { fetchAccounts } from '../../api/accounts'
import { fetchRecurringJournals, createRecurringJournal } from '../../api/recurringJournals'
import { todayISO } from '../../utils/format'
import PageHeader from '../../components/shared/PageHeader'
import Button from '../../components/shared/Button'
import FormField, { Input, Select } from '../../components/shared/FormField'
import Modal from '../../components/shared/Modal'
import LoadingSpinner from '../../components/shared/LoadingSpinner'

const emptyLine = { narration: '', account_id: '', debit: '', credit: '' }

export default function JournalForm() {
  const { id } = useParams()
  const isEdit = Boolean(id)
  const navigate = useNavigate()
  const toast = useToast()

  const { data: accounts } = useApi(fetchAccounts, [])
  const { data: templates, refetch: refetchTemplates } = useApi(fetchRecurringJournals, [])

  const [form, setForm] = useState({
    transaction_date: todayISO(),
    narration: 'Journal Entry',
    line_items: [{ ...emptyLine }, { ...emptyLine }],
  })
  const [saving, setSaving] = useState(false)
  const [loadingJournal, setLoadingJournal] = useState(isEdit)
  const [saveModalOpen, setSaveModalOpen] = useState(false)
  const [templateName, setTemplateName] = useState('')

  // Load existing journal for edit mode
  useEffect(() => {
    if (!isEdit) return
    let cancelled = false
    const load = async () => {
      try {
        const journal = await fetchJournal(id)

        // Reconstruct grid lines from line_items + main account
        const gridLines = journal.line_items.map((li) => ({
          account_id: li.account_id?.toString() || '',
          narration: li.narration || '',
          debit: li.credited ? '' : li.amount?.toString() || '',
          credit: li.credited ? li.amount?.toString() || '' : '',
        }))

        // Add the main account back as a grid line
        if (journal.account_id && journal.main_account_amount > 0) {
          gridLines.push({
            account_id: journal.account_id.toString(),
            narration: '',
            debit: journal.credited ? '' : journal.main_account_amount.toString(),
            credit: journal.credited ? journal.main_account_amount.toString() : '',
          })
        }

        if (!cancelled) {
          setForm({
            transaction_date: journal.transaction_date?.split('T')[0] || todayISO(),
            narration: journal.narration || '',
            line_items: gridLines.length >= 2 ? gridLines : [{ ...emptyLine }, { ...emptyLine }],
          })
          setLoadingJournal(false)
        }
      } catch (err) {
        if (!cancelled) {
          toast.error('Failed to load journal entry')
          navigate('/journals')
        }
      }
    }
    load()
    return () => { cancelled = true }
  }, [id, isEdit])

  const loadTemplate = (templateId) => {
    if (!templateId) return
    const tpl = templates?.find((t) => t.id === parseInt(templateId))
    if (!tpl) return

    // Build grid lines from the template's line_items.
    const gridLines = tpl.line_items.map((li) => ({
      account_id: li.account_id?.toString() || '',
      narration: li.narration || '',
      debit: li.credited ? '' : li.amount?.toString() || '',
      credit: li.credited ? li.amount?.toString() || '' : '',
    }))

    // Backward compat: old templates stored a separate account_id for the
    // "main account".  If present and not already in the line items, add it
    // as a balancing line so the grid stays balanced.
    if (tpl.account_id) {
      const mainAlreadyInLines = gridLines.some(
        (gl) => gl.account_id === tpl.account_id.toString()
      )
      if (!mainAlreadyInLines) {
        const totalDebits = gridLines.reduce((s, gl) => s + (parseFloat(gl.debit) || 0), 0)
        const totalCredits = gridLines.reduce((s, gl) => s + (parseFloat(gl.credit) || 0), 0)
        const diff = Math.abs(totalDebits - totalCredits)
        if (diff > 0.005) {
          gridLines.push({
            account_id: tpl.account_id.toString(),
            narration: '',
            debit: totalCredits > totalDebits ? diff.toFixed(2) : '',
            credit: totalDebits > totalCredits ? diff.toFixed(2) : '',
          })
        }
      }
    }

    setForm({
      transaction_date: todayISO(),
      narration: tpl.narration || '',
      line_items: gridLines.length >= 2 ? gridLines : [{ ...emptyLine }, { ...emptyLine }],
    })
  }

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

  const handleSubmit = async (post = true) => {
    if (!totals.balanced) {
      toast.error('Debits and credits must be equal')
      return
    }

    const validLines = form.line_items.filter((li) =>
      li.account_id && (parseFloat(li.debit) > 0 || parseFloat(li.credit) > 0)
    )
    if (validLines.length < 2) {
      toast.error('At least two line items are required')
      return
    }

    setSaving(true)
    try {
      const payload = {
        narration: form.narration,
        transaction_date: form.transaction_date,
        post,
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

      if (isEdit) {
        await updateJournal(id, payload)
        toast.success(post ? 'Journal entry updated & posted' : 'Journal entry updated')
      } else {
        await createJournal(payload)
        toast.success(post ? 'Journal entry created & posted' : 'Journal entry saved as draft')
      }
      navigate('/journals')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleSaveRecurring = async () => {
    if (!templateName.trim()) {
      toast.error('Please enter a template name')
      return
    }

    const validLines = form.line_items.filter((li) =>
      li.account_id && (parseFloat(li.debit) > 0 || parseFloat(li.credit) > 0)
    )
    if (validLines.length < 2) {
      toast.error('At least two line items are required')
      return
    }

    try {
      await createRecurringJournal({
        name: templateName.trim(),
        narration: form.narration,
        line_items: validLines.map((li) => {
          const isCredit = parseFloat(li.credit) > 0
          return {
            account_id: parseInt(li.account_id),
            narration: li.narration,
            amount: isCredit ? parseFloat(li.credit) : parseFloat(li.debit),
            credited: isCredit,
          }
        }),
      })
      toast.success('Template saved')
      setSaveModalOpen(false)
      setTemplateName('')
      refetchTemplates()
    } catch (err) {
      toast.error(err.message)
    }
  }

  const fmtCurrency = (v) => `$${v.toFixed(2)}`

  if (loadingJournal) return <LoadingSpinner />

  return (
    <div>
      <PageHeader title={isEdit ? 'Edit Journal Entry' : 'New Journal Entry'}>
        <Button variant="secondary" onClick={() => navigate('/journals')}>Cancel</Button>
      </PageHeader>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        {/* Load Recurring Template dropdown (create mode only) */}
        {!isEdit && templates && templates.length > 0 && (
          <div className="mb-6 pb-4 border-b border-gray-200">
            <FormField label="Load Recurring Template">
              <Select
                value=""
                onChange={(e) => loadTemplate(e.target.value)}
              >
                <option value="">Select a template...</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </Select>
            </FormField>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
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
          {!isEdit && (
            <Button variant="secondary" onClick={() => setSaveModalOpen(true)} disabled={saving}>
              Save Recurring
            </Button>
          )}
          {isEdit ? (
            <>
              <Button variant="secondary" onClick={() => handleSubmit(false)} disabled={saving || !totals.balanced}>
                Update
              </Button>
              <Button onClick={() => handleSubmit(true)} disabled={saving || !totals.balanced}>
                Update & Post
              </Button>
            </>
          ) : (
            <>
              <Button variant="secondary" onClick={() => handleSubmit(false)} disabled={saving || !totals.balanced}>
                Save Draft
              </Button>
              <Button onClick={() => handleSubmit(true)} disabled={saving || !totals.balanced}>
                Save & Post
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Save Recurring Template Modal (create mode only) */}
      {!isEdit && (
        <Modal open={saveModalOpen} onClose={() => setSaveModalOpen(false)} title="Save as Recurring Template">
          <FormField label="Template Name" required>
            <Input
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              placeholder="e.g. Monthly Rent"
              autoFocus
            />
          </FormField>
          <div className="flex justify-end gap-3 mt-6">
            <Button variant="secondary" onClick={() => setSaveModalOpen(false)}>Cancel</Button>
            <Button onClick={handleSaveRecurring}>Save Template</Button>
          </div>
        </Modal>
      )}
    </div>
  )
}
