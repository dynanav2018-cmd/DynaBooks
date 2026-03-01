import { useState } from 'react'
import { useApi } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import { fetchClosingPreview, performClosing } from '../../api/closing'
import PageHeader from '../../components/shared/PageHeader'
import Button from '../../components/shared/Button'
import Card from '../../components/shared/Card'
import DataTable from '../../components/shared/DataTable'
import LoadingSpinner from '../../components/shared/LoadingSpinner'

export default function ClosingIndex() {
  const { data: preview, loading, error, refetch } = useApi(fetchClosingPreview)
  const [closing, setClosing] = useState(false)
  const [result, setResult] = useState(null)
  const toast = useToast()

  const handleClose = async () => {
    if (!confirm('Are you sure you want to close this fiscal year? This action cannot be undone.')) return
    setClosing(true)
    try {
      const res = await performClosing()
      setResult(res)
      toast.success(res.message)
      refetch()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setClosing(false)
    }
  }

  if (loading) return <LoadingSpinner />

  if (error) {
    return (
      <div>
        <PageHeader title="Year-End Close" subtitle="Close the current fiscal year" />
        <Card>
          <p className="text-gray-600">
            {error.message || 'Unable to load closing preview. There may be no open reporting period.'}
          </p>
        </Card>
      </div>
    )
  }

  if (result) {
    return (
      <div>
        <PageHeader title="Year-End Close" subtitle="Close the current fiscal year" />
        <Card>
          <div className="text-center py-8">
            <div className="text-4xl mb-4">&#10003;</div>
            <h3 className="text-xl font-semibold text-gray-800 mb-2">Year-End Close Complete</h3>
            <p className="text-gray-600">{result.message}</p>
          </div>
        </Card>
      </div>
    )
  }

  const columns = [
    { key: 'name', label: 'Account' },
    { key: 'account_type', label: 'Type', render: (v) => v.replace(/_/g, ' ') },
    { key: 'balance', label: 'Balance', render: (v) => `$${Math.abs(v).toFixed(2)}` },
    { key: 'action', label: 'Action', render: (v, row) =>
      v === 'debit' ? `Debit ${row.name}` : `Credit ${row.name}`
    },
  ]

  const isClosed = preview?.period?.status === 'CLOSED'

  return (
    <div>
      <PageHeader title="Year-End Close" subtitle="Close the current fiscal year" />

      {preview?.period && (
        <Card>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div>
              <p className="text-xs text-gray-500 uppercase">Fiscal Year</p>
              <p className="text-lg font-semibold">{preview.period.calendar_year}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase">Period</p>
              <p className="text-sm">{preview.period.start?.slice(0, 10)} to {preview.period.end?.slice(0, 10)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase">Status</p>
              <p className={`text-sm font-medium ${isClosed ? 'text-red-600' : 'text-green-600'}`}>
                {preview.period.status}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase">Net Income</p>
              <p className={`text-lg font-semibold ${preview.net_income >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                ${preview.net_income?.toFixed(2)}
              </p>
            </div>
          </div>

          {preview.retained_earnings_account && (
            <p className="text-sm text-gray-600 mb-4">
              Net income will be transferred to <strong>{preview.retained_earnings_account}</strong>.
            </p>
          )}
        </Card>
      )}

      {preview?.accounts_to_close?.length > 0 && (
        <div className="mt-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Accounts to Close ({preview.accounts_to_close.length})</h3>
          <DataTable columns={columns} data={preview.accounts_to_close} />
        </div>
      )}

      {!isClosed && preview?.accounts_to_close?.length > 0 && (
        <div className="mt-6 flex justify-end">
          <Button onClick={handleClose} disabled={closing}>
            {closing ? 'Closing...' : 'Close Fiscal Year'}
          </Button>
        </div>
      )}

      {isClosed && (
        <Card>
          <p className="text-gray-600 text-center py-4">This period is already closed.</p>
        </Card>
      )}
    </div>
  )
}
