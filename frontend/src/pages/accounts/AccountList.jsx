import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import { fetchAccounts, createAccount, updateAccount, deleteAccount } from '../../api/accounts'
import DataTable from '../../components/shared/DataTable'
import PageHeader from '../../components/shared/PageHeader'
import Button from '../../components/shared/Button'
import Modal from '../../components/shared/Modal'
import FormField, { Input, Select } from '../../components/shared/FormField'
import LoadingSpinner from '../../components/shared/LoadingSpinner'

const ACCOUNT_TYPES = [
  'Non Current Asset', 'Contra Asset', 'Inventory', 'Bank', 'Current Asset', 'Receivable',
  'Non Current Liability', 'Control', 'Current Liability', 'Payable',
  'Equity', 'Operating Revenue', 'Operating Expense', 'Non Operating Revenue',
  'Direct Expense', 'Overhead Expense', 'Other Expense', 'Reconciliation',
]

const TYPE_GROUP_MAP = {
  'Non Current Asset': 'Asset', 'Contra Asset': 'Contra Asset', 'Inventory': 'Asset',
  'Bank': 'Asset', 'Current Asset': 'Asset', 'Receivable': 'Asset',
  'Non Current Liability': 'Liability', 'Control': 'Liability',
  'Current Liability': 'Liability', 'Payable': 'Liability',
  'Equity': 'Equity', 'Operating Revenue': 'Revenue', 'Non Operating Revenue': 'Revenue',
  'Operating Expense': 'Expense', 'Direct Expense': 'Expense',
  'Overhead Expense': 'Expense', 'Other Expense': 'Expense', 'Reconciliation': 'Expense',
}

export default function AccountList() {
  const [filterType, setFilterType] = useState('')
  const { data: accounts, loading, refetch } = useApi(() => fetchAccounts(filterType), [filterType])
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState({ name: '', account_code: '', account_type: ACCOUNT_TYPES[0], description: '' })
  const toast = useToast()

  const columns = [
    { key: 'account_number', label: 'Account #',
      render: (v, row) => (
        <Link to={`/accounts/${row.id}`} className="text-accent hover:underline font-medium">{v}</Link>
      ),
    },
    { key: 'name', label: 'Account Name' },
    { key: 'type_group', label: 'Type' },
    { key: 'category', label: 'Category' },
    {
      key: 'actions',
      label: '',
      render: (_, row) => (
        <div className="flex gap-2">
          <button onClick={(e) => { e.stopPropagation(); openEdit(row) }} className="text-accent hover:underline text-xs">Edit</button>
          <button onClick={(e) => { e.stopPropagation(); handleDelete(row.id) }} className="text-red-500 hover:underline text-xs">Delete</button>
        </div>
      ),
    },
  ]

  const openCreate = () => {
    setEditing(null)
    setForm({ name: '', account_code: '', account_type: ACCOUNT_TYPES[0], description: '' })
    setModalOpen(true)
  }

  const openEdit = (account) => {
    setEditing(account)
    let desc = account.description || ''
    if (desc.startsWith('Spec #')) desc = ''
    setForm({
      name: account.name,
      account_code: account.account_code || '',
      account_type: account.account_type || ACCOUNT_TYPES[0],
      description: desc,
    })
    setModalOpen(true)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      if (editing) {
        await updateAccount(editing.id, {
          name: form.name,
          account_code: form.account_code,
          account_type: form.account_type,
          description: form.description,
        })
        toast.success('Account updated')
      } else {
        await createAccount(form)
        toast.success('Account created')
      }
      setModalOpen(false)
      refetch()
    } catch (err) {
      toast.error(err.message)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this account?')) return
    try {
      await deleteAccount(id)
      toast.success('Account deleted')
      refetch()
    } catch (err) {
      toast.error(err.message)
    }
  }

  if (loading) return <LoadingSpinner />

  return (
    <div>
      <PageHeader title="Chart of Accounts">
        <Select value={filterType} onChange={(e) => setFilterType(e.target.value)} className="!w-48">
          <option value="">All Types</option>
          {ACCOUNT_TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </Select>
        <Button onClick={openCreate}>New Account</Button>
      </PageHeader>

      <DataTable columns={columns} data={accounts || []} emptyMessage="No accounts found" />

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Edit Account' : 'New Account'}>
        <form onSubmit={handleSubmit}>
          <FormField label="Account #">
            <Input
              type="number"
              value={form.account_code}
              onChange={(e) => setForm({ ...form, account_code: e.target.value })}
              placeholder={editing ? '' : 'Leave blank to auto-generate'}
            />
          </FormField>
          <FormField label="Account Name" required>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </FormField>
          <FormField label="Account Type" required>
            <Select value={form.account_type} onChange={(e) => setForm({ ...form, account_type: e.target.value })} required>
              {ACCOUNT_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </Select>
          </FormField>
          {editing && (
            <FormField label="Category">
              <Input value={TYPE_GROUP_MAP[form.account_type] || form.account_type} disabled className="bg-gray-50" />
            </FormField>
          )}
          <FormField label="Description">
            <Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </FormField>
          <div className="flex justify-end gap-3 mt-6">
            <Button variant="secondary" type="button" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button type="submit">{editing ? 'Update' : 'Create'}</Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
