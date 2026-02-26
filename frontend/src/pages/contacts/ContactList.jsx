import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import { fetchContacts, createContact, updateContact, deleteContact } from '../../api/contacts'
import DataTable from '../../components/shared/DataTable'
import PageHeader from '../../components/shared/PageHeader'
import Button from '../../components/shared/Button'
import Modal from '../../components/shared/Modal'
import FormField, { Input, Select, Textarea } from '../../components/shared/FormField'
import StatusBadge from '../../components/shared/StatusBadge'
import LoadingSpinner from '../../components/shared/LoadingSpinner'

const tabs = [
  { key: '', label: 'All' },
  { key: 'client', label: 'Clients' },
  { key: 'supplier', label: 'Suppliers' },
]

const emptyForm = {
  name: '', contact_type: 'client', email: '', phone: '',
  address_line_1: '', address_line_2: '', country: 'CA',
  tax_number: '', payment_terms_days: 30, notes: '',
}

export default function ContactList() {
  const [searchParams, setSearchParams] = useSearchParams()
  const typeFilter = searchParams.get('type') || ''
  const { data: contacts, loading, refetch } = useApi(() => fetchContacts(typeFilter), [typeFilter])
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const toast = useToast()

  const columns = [
    { key: 'name', label: 'Name' },
    { key: 'contact_type', label: 'Type', render: (v) => <StatusBadge status={v} /> },
    { key: 'email', label: 'Email' },
    { key: 'phone', label: 'Phone' },
    { key: 'payment_terms_days', label: 'Terms', render: (v) => v ? `${v} days` : '' },
    {
      key: 'actions',
      label: '',
      render: (_, row) => (
        <div className="flex gap-2">
          <button onClick={(e) => { e.stopPropagation(); openEdit(row) }} className="text-accent hover:underline text-xs">Edit</button>
          <button onClick={(e) => { e.stopPropagation(); handleDelete(row.id) }} className="text-red-500 hover:underline text-xs">Deactivate</button>
        </div>
      ),
    },
  ]

  const setTab = (key) => {
    if (key) {
      setSearchParams({ type: key })
    } else {
      setSearchParams({})
    }
  }

  const openCreate = () => {
    setEditing(null)
    setForm({ ...emptyForm, contact_type: typeFilter || 'client' })
    setModalOpen(true)
  }

  const openEdit = (contact) => {
    setEditing(contact)
    setForm({
      name: contact.name,
      contact_type: contact.contact_type,
      email: contact.email || '',
      phone: contact.phone || '',
      address_line_1: contact.address_line_1 || '',
      address_line_2: contact.address_line_2 || '',
      country: contact.country || 'CA',
      tax_number: contact.tax_number || '',
      payment_terms_days: contact.payment_terms_days || 30,
      notes: contact.notes || '',
    })
    setModalOpen(true)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      if (editing) {
        await updateContact(editing.id, form)
        toast.success('Contact updated')
      } else {
        await createContact(form)
        toast.success('Contact created')
      }
      setModalOpen(false)
      refetch()
    } catch (err) {
      toast.error(err.message)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Deactivate this contact?')) return
    try {
      await deleteContact(id)
      toast.success('Contact deactivated')
      refetch()
    } catch (err) {
      toast.error(err.message)
    }
  }

  const setField = (field) => (e) => setForm({ ...form, [field]: e.target.value })

  if (loading) return <LoadingSpinner />

  return (
    <div>
      <PageHeader title="Contacts">
        <Button onClick={openCreate}>New Contact</Button>
      </PageHeader>

      <div className="flex gap-1 mb-4 bg-gray-100 rounded-lg p-1 w-fit">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setTab(tab.key)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              typeFilter === tab.key
                ? 'bg-white text-navy shadow-sm'
                : 'text-gray-600 hover:text-gray-800'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <DataTable columns={columns} data={contacts || []} emptyMessage="No contacts found" />

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Edit Contact' : 'New Contact'} wide>
        <form onSubmit={handleSubmit}>
          <div className="grid grid-cols-2 gap-4">
            <FormField label="Name" required>
              <Input value={form.name} onChange={setField('name')} required />
            </FormField>
            <FormField label="Type" required>
              <Select value={form.contact_type} onChange={setField('contact_type')} required>
                <option value="client">Client</option>
                <option value="supplier">Supplier</option>
                <option value="both">Both</option>
              </Select>
            </FormField>
            <FormField label="Email">
              <Input type="email" value={form.email} onChange={setField('email')} />
            </FormField>
            <FormField label="Phone">
              <Input value={form.phone} onChange={setField('phone')} />
            </FormField>
            <FormField label="Address Line 1">
              <Input value={form.address_line_1} onChange={setField('address_line_1')} />
            </FormField>
            <FormField label="Address Line 2">
              <Input value={form.address_line_2} onChange={setField('address_line_2')} />
            </FormField>
            <FormField label="Country">
              <Input value={form.country} onChange={setField('country')} />
            </FormField>
            <FormField label="Tax Number">
              <Input value={form.tax_number} onChange={setField('tax_number')} />
            </FormField>
            <FormField label="Payment Terms (days)">
              <Input type="number" value={form.payment_terms_days} onChange={setField('payment_terms_days')} />
            </FormField>
          </div>
          <FormField label="Notes">
            <Textarea value={form.notes} onChange={setField('notes')} />
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
