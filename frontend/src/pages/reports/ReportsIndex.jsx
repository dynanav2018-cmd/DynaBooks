import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useToast } from '../../hooks/useToast'
import {
  fetchIncomeStatement, fetchBalanceSheet,
  fetchAgingReceivables, fetchAgingPayables,
  fetchAgingReceivablesDetail, fetchAgingPayablesDetail,
  downloadReportPdf,
} from '../../api/reports'
import { formatCurrency, todayISO } from '../../utils/format'
import PageHeader from '../../components/shared/PageHeader'
import Button from '../../components/shared/Button'
import FormField, { Input, Select } from '../../components/shared/FormField'
import LoadingSpinner from '../../components/shared/LoadingSpinner'

const reportTypes = [
  { key: 'income-statement', label: 'Income Statement' },
  { key: 'balance-sheet', label: 'Balance Sheet' },
  { key: 'aging-receivables', label: 'Aging - Receivables' },
  { key: 'aging-payables', label: 'Aging - Payables' },
]

function ReportSection({ title, data }) {
  if (!data || typeof data !== 'object') return null
  const entries = Object.entries(data)
  if (entries.length === 0) return null

  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-2">{title}</h3>
      <div className="space-y-1">
        {entries.map(([key, value]) => {
          if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
            if (value.id && value.name) {
              return null
            }
            return <ReportSection key={key} title={key} data={value} />
          }
          return (
            <div key={key} className="flex justify-between py-1 px-2 hover:bg-gray-50 rounded text-sm">
              <span className="text-gray-700">{key}</span>
              <span className="font-medium">
                {typeof value === 'number' ? formatCurrency(value) : String(value)}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function AccountList({ accounts }) {
  if (!accounts || typeof accounts !== 'object') return null

  const entries = Object.entries(accounts)
  if (entries.length === 0) return null

  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-2">Accounts</h3>
      {entries.map(([type, accts]) => (
        <div key={type} className="mb-4">
          <h4 className="text-xs font-semibold text-gray-500 mb-1 px-2">{type}</h4>
          {Array.isArray(accts) ? (
            accts.map((a) => (
              <div key={a.id || a.name} className="flex justify-between py-1 px-2 text-sm text-gray-700">
                <span>{a.name}</span>
                <span>{a.account_code}</span>
              </div>
            ))
          ) : (
            <ReportSection data={accts} />
          )}
        </div>
      ))}
    </div>
  )
}

function AgingReport({ data }) {
  if (!data) return null
  return (
    <div>
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-2">Summary</h3>
        {Object.entries(data.balances || {}).map(([period, amount]) => (
          <div key={period} className="flex justify-between py-1 px-2 text-sm">
            <span className="text-gray-700">{period}</span>
            <span className="font-medium">{formatCurrency(amount)}</span>
          </div>
        ))}
      </div>
      {data.accounts?.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-2">By Account</h3>
          {data.accounts.map((a) => (
            <div key={a.id} className="mb-2">
              <p className="text-sm font-medium text-gray-800 px-2">{a.name}</p>
              {a.balances && Object.entries(a.balances).map(([period, amount]) => (
                <div key={period} className="flex justify-between py-0.5 px-4 text-xs text-gray-600">
                  <span>{period}</span>
                  <span>{formatCurrency(amount)}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ContactAgingDetail({ detail }) {
  if (!detail) return null
  const { contacts = [], unassigned } = detail

  if (contacts.length === 0 && !unassigned) return null

  return (
    <div className="mt-6">
      <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">By Contact</h3>
      {contacts.map((c) => (
        <ContactCard key={c.contact_id} contact={c} />
      ))}
      {unassigned && unassigned.transactions?.length > 0 && (
        <ContactCard
          contact={{
            contact_name: 'Unassigned',
            total_outstanding: unassigned.total_outstanding,
            transactions: unassigned.transactions,
          }}
        />
      )}
    </div>
  )
}

function ContactCard({ contact }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="mb-3 border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex justify-between items-center px-4 py-2.5 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
      >
        <span className="text-sm font-medium text-gray-800">{contact.contact_name}</span>
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-navy">
            {formatCurrency(contact.total_outstanding)}
          </span>
          <span className="text-xs text-gray-400">{expanded ? '\u25B2' : '\u25BC'}</span>
        </div>
      </button>
      {expanded && (
        <div className="px-4 py-2">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-500 border-b border-gray-100">
                <th className="text-left py-1 font-medium">Invoice/Bill #</th>
                <th className="text-left py-1 font-medium">Date</th>
                <th className="text-right py-1 font-medium">Amount</th>
                <th className="text-right py-1 font-medium">Outstanding</th>
                <th className="text-left py-1 font-medium pl-3">Age</th>
              </tr>
            </thead>
            <tbody>
              {contact.transactions.map((tx) => (
                <tr key={tx.transaction_no} className="border-b border-gray-50">
                  <td className="py-1 text-gray-700">{tx.transaction_no}</td>
                  <td className="py-1 text-gray-600">{tx.transaction_date?.split('T')[0]}</td>
                  <td className="py-1 text-right text-gray-700">{formatCurrency(tx.amount)}</td>
                  <td className="py-1 text-right font-medium text-gray-800">{formatCurrency(tx.outstanding)}</td>
                  <td className="py-1 pl-3 text-gray-500">{tx.age_bracket}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default function ReportsIndex() {
  const { type } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const [selectedType, setSelectedType] = useState(type || '')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [asOf, setAsOf] = useState(todayISO())
  const [report, setReport] = useState(null)
  const [agingDetail, setAgingDetail] = useState(null)
  const [loading, setLoading] = useState(false)

  const needsDateRange = ['income-statement'].includes(selectedType)
  const needsAsOf = ['balance-sheet', 'aging-receivables', 'aging-payables'].includes(selectedType)
  const isAging = selectedType?.startsWith('aging-')

  const generateReport = async () => {
    setLoading(true)
    setAgingDetail(null)
    try {
      let data
      switch (selectedType) {
        case 'income-statement':
          data = await fetchIncomeStatement(dateFrom, dateTo)
          break
        case 'balance-sheet':
          data = await fetchBalanceSheet(asOf)
          break
        case 'aging-receivables':
          data = await fetchAgingReceivables(asOf)
          // Also fetch per-contact detail
          fetchAgingReceivablesDetail(asOf)
            .then(setAgingDetail)
            .catch(() => {})
          break
        case 'aging-payables':
          data = await fetchAgingPayables(asOf)
          fetchAgingPayablesDetail(asOf)
            .then(setAgingDetail)
            .catch(() => {})
          break
        default:
          toast.error('Select a report type')
          setLoading(false)
          return
      }
      setReport(data)
      navigate(`/reports/${selectedType}`, { replace: true })
    } catch (err) {
      toast.error(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleDownloadPdf = async () => {
    try {
      const params = {}
      if (needsDateRange) { params.from = dateFrom; params.to = dateTo }
      if (needsAsOf) { params.as_of = asOf }
      const blob = await downloadReportPdf(selectedType, params)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${selectedType}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      toast.error('PDF download failed: ' + err.message)
    }
  }

  return (
    <div>
      <PageHeader title="Reports">
        {report && <Button variant="secondary" onClick={handleDownloadPdf}>Download PDF</Button>}
      </PageHeader>

      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
        <div className="flex flex-wrap gap-4 items-end">
          <FormField label="Report Type">
            <Select
              value={selectedType}
              onChange={(e) => { setSelectedType(e.target.value); setReport(null); setAgingDetail(null) }}
              className="!w-56"
            >
              <option value="">Select report...</option>
              {reportTypes.map((rt) => (
                <option key={rt.key} value={rt.key}>{rt.label}</option>
              ))}
            </Select>
          </FormField>
          {needsDateRange && (
            <>
              <FormField label="From">
                <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
              </FormField>
              <FormField label="To">
                <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
              </FormField>
            </>
          )}
          {needsAsOf && (
            <FormField label="As Of">
              <Input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} />
            </FormField>
          )}
          <Button onClick={generateReport} disabled={!selectedType || loading}>
            {loading ? 'Generating...' : 'Generate'}
          </Button>
        </div>
      </div>

      {loading && <LoadingSpinner />}

      {report && !loading && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            {reportTypes.find((rt) => rt.key === selectedType)?.label}
          </h2>
          {isAging ? (
            <>
              <AgingReport data={report} />
              <ContactAgingDetail detail={agingDetail} />
            </>
          ) : (
            <>
              <ReportSection title="Balances" data={report.balances} />
              <ReportSection title="Totals" data={report.totals} />
              <ReportSection title="Result" data={report.result_amounts} />
              <AccountList accounts={report.accounts} />
            </>
          )}
        </div>
      )}
    </div>
  )
}
