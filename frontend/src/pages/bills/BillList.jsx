import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { fetchBills } from '../../api/bills'
import { formatCurrency, formatDate } from '../../utils/format'
import DataTable from '../../components/shared/DataTable'
import PageHeader from '../../components/shared/PageHeader'
import Button from '../../components/shared/Button'
import StatusBadge from '../../components/shared/StatusBadge'
import LoadingSpinner from '../../components/shared/LoadingSpinner'

export default function BillList() {
  const { data: bills, loading } = useApi(fetchBills)
  const [filter, setFilter] = useState('all')
  const navigate = useNavigate()

  const filtered = bills
    ? bills.filter((b) => {
        if (filter === 'draft') return !b.is_posted
        if (filter === 'posted') return b.is_posted
        return true
      })
    : []

  const columns = [
    { key: 'transaction_no', label: 'Bill #' },
    { key: 'transaction_date', label: 'Date', render: (v) => formatDate(v) },
    { key: 'narration', label: 'Description' },
    {
      key: 'amount',
      label: 'Amount',
      render: (v) => <span className="font-medium">{formatCurrency(v)}</span>,
    },
    {
      key: 'is_posted',
      label: 'Status',
      render: (v) => <StatusBadge status={v ? 'Posted' : 'Draft'} />,
    },
  ]

  if (loading) return <LoadingSpinner />

  return (
    <div>
      <PageHeader title="Bills">
        <Link to="/bills/new">
          <Button>New Bill</Button>
        </Link>
      </PageHeader>

      <div className="flex gap-1 mb-4 bg-gray-100 rounded-lg p-1 w-fit">
        {['all', 'draft', 'posted'].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors capitalize ${
              filter === f
                ? 'bg-white text-navy shadow-sm'
                : 'text-gray-600 hover:text-gray-800'
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      <DataTable
        columns={columns}
        data={filtered}
        onRowClick={(row) => navigate(`/bills/${row.id}`)}
        emptyMessage="No bills found"
      />
    </div>
  )
}
