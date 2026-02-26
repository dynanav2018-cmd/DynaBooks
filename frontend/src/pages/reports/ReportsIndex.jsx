import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import {
  fetchIncomeStatement, fetchBalanceSheet,
  fetchAgingReceivables, fetchAgingPayables,
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

export default function ReportsIndex() {
  const { type } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const [selectedType, setSelectedType] = useState(type || '')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [asOf, setAsOf] = useState(todayISO())
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)

  const needsDateRange = ['income-statement'].includes(selectedType)
  const needsAsOf = ['balance-sheet', 'aging-receivables', 'aging-payables'].includes(selectedType)
  const isAging = selectedType?.startsWith('aging-')

  const generateReport = async () => {
    setLoading(true)
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
          break
        case 'aging-payables':
          data = await fetchAgingPayables(asOf)
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
              onChange={(e) => { setSelectedType(e.target.value); setReport(null) }}
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
            <AgingReport data={report} />
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
