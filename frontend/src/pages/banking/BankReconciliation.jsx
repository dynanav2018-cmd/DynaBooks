import { useState, useMemo } from 'react'
import { useApi } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import { fetchAccounts } from '../../api/accounts'
import {
  fetchReconciliations, createReconciliation,
  fetchReconciliation, updateReconciliation,
} from '../../api/reconciliation'
import PageHeader from '../../components/shared/PageHeader'
import Button from '../../components/shared/Button'
import FormField, { Input, Select } from '../../components/shared/FormField'
import LoadingSpinner from '../../components/shared/LoadingSpinner'

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

export default function BankReconciliation() {
  const { data: allAccounts } = useApi(() => fetchAccounts('Bank'), [])
  const toast = useToast()

  const [selectedAccount, setSelectedAccount] = useState('')
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear())
  const [selectedMonth, setSelectedMonth] = useState(new Date().getMonth() + 1)
  const [recData, setRecData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [statementBalance, setStatementBalance] = useState('')
  const [clearedIds, setClearedIds] = useState(new Set())
  const [history, setHistory] = useState([])

  // Load history when account changes
  const loadHistory = async (accountId) => {
    if (!accountId) { setHistory([]); return }
    try {
      const recs = await fetchReconciliations(accountId)
      setHistory(recs)
    } catch { setHistory([]) }
  }

  const handleAccountChange = (accountId) => {
    setSelectedAccount(accountId)
    setRecData(null)
    loadHistory(accountId)
  }

  const startReconciliation = async () => {
    if (!selectedAccount) { toast.error('Select a bank account'); return }
    setLoading(true)
    try {
      const rec = await createReconciliation({
        account_id: parseInt(selectedAccount),
        period_year: selectedYear,
        period_month: selectedMonth,
      })
      const full = await fetchReconciliation(rec.id)
      setRecData(full)
      setStatementBalance(full.statement_balance?.toString() || '0')
      setClearedIds(new Set(full.entries?.filter(e => e.is_cleared).map(e => e.ledger_id) || []))
    } catch (err) {
      toast.error(err.message)
    } finally {
      setLoading(false)
    }
  }

  const toggleCleared = (ledgerId) => {
    setClearedIds(prev => {
      const next = new Set(prev)
      if (next.has(ledgerId)) next.delete(ledgerId)
      else next.add(ledgerId)
      return next
    })
  }

  const toggleAll = () => {
    if (!recData?.entries) return
    const allIds = recData.entries.map(e => e.ledger_id)
    if (clearedIds.size === allIds.length) {
      setClearedIds(new Set())
    } else {
      setClearedIds(new Set(allIds))
    }
  }

  const { clearedTotal, unclearedTotal } = useMemo(() => {
    if (!recData?.entries) return { clearedTotal: 0, unclearedTotal: 0 }
    let ct = 0, ut = 0
    for (const e of recData.entries) {
      const amt = e.entry_type === 'D' ? e.amount : -e.amount
      if (clearedIds.has(e.ledger_id)) ct += amt
      else ut += amt
    }
    return { clearedTotal: ct, unclearedTotal: ut }
  }, [recData, clearedIds])

  const difference = (parseFloat(statementBalance) || 0) - clearedTotal

  const saveReconciliation = async (complete = false) => {
    try {
      await updateReconciliation(recData.id, {
        statement_balance: parseFloat(statementBalance) || 0,
        cleared_ledger_ids: [...clearedIds],
        complete,
      })
      toast.success(complete ? 'Reconciliation completed' : 'Reconciliation saved')
      if (complete) {
        setRecData(null)
        loadHistory(selectedAccount)
      }
    } catch (err) {
      toast.error(err.message)
    }
  }

  const fmt = (v) => `$${Math.abs(v).toFixed(2)}${v < 0 ? ' CR' : ''}`
  const currentYear = new Date().getFullYear()
  const years = Array.from({ length: 5 }, (_, i) => currentYear - i)

  return (
    <div>
      <PageHeader title="Bank Reconciliation" />

      {/* Account and Period Selection */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
          <FormField label="Bank Account">
            <Select value={selectedAccount} onChange={(e) => handleAccountChange(e.target.value)}>
              <option value="">Select account...</option>
              {allAccounts?.map(a => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </Select>
          </FormField>
          <FormField label="Year">
            <Select value={selectedYear} onChange={(e) => setSelectedYear(parseInt(e.target.value))}>
              {years.map(y => <option key={y} value={y}>{y}</option>)}
            </Select>
          </FormField>
          <FormField label="Month">
            <Select value={selectedMonth} onChange={(e) => setSelectedMonth(parseInt(e.target.value))}>
              {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
            </Select>
          </FormField>
          <Button onClick={startReconciliation} disabled={loading || !selectedAccount}>
            {loading ? 'Loading...' : 'Start Reconciliation'}
          </Button>
        </div>
      </div>

      {/* Previous Reconciliations */}
      {history.length > 0 && !recData && (
        <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Previous Reconciliations</h3>
          <div className="space-y-2">
            {history.map(r => (
              <div key={r.id} className="flex items-center justify-between text-sm border-b pb-2">
                <span>{MONTHS[r.period_month - 1]} {r.period_year}</span>
                <span>Statement: ${parseFloat(r.statement_balance).toFixed(2)}</span>
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                  r.status === 'completed' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
                }`}>
                  {r.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Reconciliation Worksheet */}
      {recData && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">
              {MONTHS[recData.period_month - 1]} {recData.period_year}
            </h3>
            <div className="flex items-center gap-4">
              <FormField label="Statement Balance">
                <Input
                  type="number"
                  step="0.01"
                  value={statementBalance}
                  onChange={(e) => setStatementBalance(e.target.value)}
                  className="w-40"
                />
              </FormField>
            </div>
          </div>

          {/* Entries table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-gray-500">
                  <th className="pb-2 w-10">
                    <input type="checkbox"
                      checked={recData.entries?.length > 0 && clearedIds.size === recData.entries.length}
                      onChange={toggleAll}
                      className="rounded"
                    />
                  </th>
                  <th className="pb-2">Date</th>
                  <th className="pb-2">Ref #</th>
                  <th className="pb-2">Description</th>
                  <th className="pb-2 text-right">Debit</th>
                  <th className="pb-2 text-right">Credit</th>
                </tr>
              </thead>
              <tbody>
                {recData.entries?.map(e => (
                  <tr key={e.ledger_id}
                    className={`border-b cursor-pointer hover:bg-blue-50 ${clearedIds.has(e.ledger_id) ? 'bg-green-50' : ''}`}
                    onClick={() => toggleCleared(e.ledger_id)}
                  >
                    <td className="py-2">
                      <input type="checkbox"
                        checked={clearedIds.has(e.ledger_id)}
                        onChange={() => toggleCleared(e.ledger_id)}
                        className="rounded"
                      />
                    </td>
                    <td className="py-2">{e.transaction_date?.split('T')[0]}</td>
                    <td className="py-2">{e.transaction_no}</td>
                    <td className="py-2">{e.narration}</td>
                    <td className="py-2 text-right">{e.entry_type === 'D' ? fmt(e.amount) : ''}</td>
                    <td className="py-2 text-right">{e.entry_type === 'C' ? fmt(e.amount) : ''}</td>
                  </tr>
                ))}
                {(!recData.entries || recData.entries.length === 0) && (
                  <tr><td colSpan={6} className="py-4 text-center text-gray-400">No transactions for this period</td></tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Summary */}
          <div className="mt-6 grid grid-cols-2 gap-6">
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Cleared Total</span>
                <span className="font-medium">{fmt(clearedTotal)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Uncleared Total</span>
                <span className="font-medium">{fmt(unclearedTotal)}</span>
              </div>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Statement Balance</span>
                <span className="font-medium">${(parseFloat(statementBalance) || 0).toFixed(2)}</span>
              </div>
              <div className={`flex justify-between font-bold text-base pt-2 border-t ${
                Math.abs(difference) < 0.01 ? 'text-green-700' : 'text-red-700'
              }`}>
                <span>Difference</span>
                <span>{fmt(difference)}</span>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 mt-6 pt-4 border-t">
            <Button variant="secondary" onClick={() => setRecData(null)}>Cancel</Button>
            <Button variant="secondary" onClick={() => saveReconciliation(false)}>Save Draft</Button>
            <Button onClick={() => saveReconciliation(true)} disabled={Math.abs(difference) >= 0.01}>
              Complete Reconciliation
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
