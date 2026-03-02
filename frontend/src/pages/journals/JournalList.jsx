import { Link, useNavigate } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import { fetchJournals, deleteJournal, postJournal } from '../../api/journals'
import { formatCurrency, formatDate } from '../../utils/format'
import DataTable from '../../components/shared/DataTable'
import PageHeader from '../../components/shared/PageHeader'
import Button from '../../components/shared/Button'
import StatusBadge from '../../components/shared/StatusBadge'
import LoadingSpinner from '../../components/shared/LoadingSpinner'
import { useSettings } from '../../hooks/useSettings'

export default function JournalList() {
  const { data: journals, loading, refetch } = useApi(fetchJournals)
  const navigate = useNavigate()
  const toast = useToast()
  const { allowEditPosted } = useSettings()

  const handleDelete = async (e, journal) => {
    e.stopPropagation()
    if (!confirm('Delete this journal entry?')) return
    try {
      await deleteJournal(journal.id)
      toast.success('Journal entry deleted')
      refetch()
    } catch (err) {
      toast.error(err.message)
    }
  }

  const handlePost = async (e, journal) => {
    e.stopPropagation()
    try {
      await postJournal(journal.id)
      toast.success('Journal entry posted')
      refetch()
    } catch (err) {
      toast.error(err.message)
    }
  }

  const columns = [
    { key: 'transaction_no', label: 'Entry #' },
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
    {
      key: 'id',
      label: 'Actions',
      render: (_, row) => (
        <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
          {(!row.is_posted || allowEditPosted) && (
            <>
              <Link
                to={`/journals/${row.id}/edit`}
                className="px-2 py-1 text-xs bg-gray-500 text-white rounded hover:bg-gray-600"
                onClick={(e) => e.stopPropagation()}
              >
                Edit
              </Link>
              {!row.is_posted && (
                <button
                  onClick={(e) => handlePost(e, row)}
                  className="px-2 py-1 text-xs bg-accent text-white rounded hover:bg-accent-dark"
                >
                  Post
                </button>
              )}
              <button
                onClick={(e) => handleDelete(e, row)}
                className="px-2 py-1 text-xs bg-red-500 text-white rounded hover:bg-red-600"
              >
                Delete
              </button>
            </>
          )}
        </div>
      ),
    },
  ]

  if (loading) return <LoadingSpinner />

  return (
    <div>
      <PageHeader title="Journal Entries">
        <Link to="/journals/new">
          <Button>New Journal Entry</Button>
        </Link>
      </PageHeader>

      <DataTable
        columns={columns}
        data={journals || []}
        emptyMessage="No journal entries found"
      />
    </div>
  )
}
