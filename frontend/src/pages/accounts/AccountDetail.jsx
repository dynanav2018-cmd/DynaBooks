import { useParams, useNavigate, Link } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { fetchAccountLedger } from '../../api/accounts'
import { formatCurrency, formatDate } from '../../utils/format'
import PageHeader from '../../components/shared/PageHeader'
import Button from '../../components/shared/Button'
import LoadingSpinner from '../../components/shared/LoadingSpinner'

const TRANSACTION_ROUTES = {
  'Client Invoice': (id) => `/invoices/${id}`,
  'Supplier Bill': (id) => `/bills/${id}`,
  'Journal Entry': (id) => `/journals/${id}/edit`,
  'Client Receipt': () => '/banking',
  'Supplier Payment': () => '/banking',
}

export default function AccountDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { data, loading } = useApi(() => fetchAccountLedger(id), [id])

  if (loading) return <LoadingSpinner />
  if (!data) return <p className="text-red-600">Account not found</p>

  const { account, opening_balance, closing_balance, entries } = data

  return (
    <div>
      <PageHeader title={`${account.account_number} — ${account.name}`}>
        <Button variant="ghost" onClick={() => navigate('/accounts')}>Back</Button>
      </PageHeader>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-8">
          <div>
            <p className="text-xs text-gray-500 uppercase font-medium">Account #</p>
            <p className="text-sm font-medium">{account.account_number}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase font-medium">Type</p>
            <p className="text-sm font-medium">{account.category}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase font-medium">Opening Balance</p>
            <p className="text-sm font-medium">{formatCurrency(opening_balance)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase font-medium">Closing Balance</p>
            <p className="text-lg font-bold text-accent">{formatCurrency(closing_balance)}</p>
          </div>
        </div>

        <h3 className="text-sm font-semibold text-gray-700 mb-3">Ledger Entries</h3>
        {entries.length === 0 ? (
          <p className="text-sm text-gray-500 py-4">No entries found</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50">
                  <th className="text-left px-4 py-2 text-xs font-semibold text-gray-600">Entry #</th>
                  <th className="text-left px-4 py-2 text-xs font-semibold text-gray-600">Date</th>
                  <th className="text-left px-4 py-2 text-xs font-semibold text-gray-600">Description</th>
                  <th className="text-right px-4 py-2 text-xs font-semibold text-gray-600">Debit</th>
                  <th className="text-right px-4 py-2 text-xs font-semibold text-gray-600">Credit</th>
                  <th className="text-right px-4 py-2 text-xs font-semibold text-gray-600">Balance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {entries.map((entry) => {
                  const routeFn = TRANSACTION_ROUTES[entry.transaction_type]
                  const entryLink = routeFn ? routeFn(entry.id) : null

                  return (
                    <tr key={`${entry.id}-${entry.transaction_type}`}>
                      <td className="px-4 py-3 text-sm">
                        {entryLink ? (
                          <Link to={entryLink} className="text-accent hover:underline font-medium">
                            {entry.transaction_no}
                          </Link>
                        ) : (
                          <span className="font-medium">{entry.transaction_no}</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm">{formatDate(entry.transaction_date)}</td>
                      <td className="px-4 py-3 text-sm">{entry.narration || entry.transaction_type}</td>
                      <td className="px-4 py-3 text-sm text-right">
                        {entry.debit ? formatCurrency(entry.debit) : ''}
                      </td>
                      <td className="px-4 py-3 text-sm text-right">
                        {entry.credit ? formatCurrency(entry.credit) : ''}
                      </td>
                      <td className="px-4 py-3 text-sm text-right font-medium">
                        {formatCurrency(entry.balance)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
