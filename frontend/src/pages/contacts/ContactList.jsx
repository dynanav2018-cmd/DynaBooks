import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import { fetchContacts, createContact, updateContact, deleteContact, importContacts } from '../../api/contacts'
import { fetchTaxes } from '../../api/taxes'
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

const PAYMENT_TERMS_OPTIONS = ['COD', 'Prepaid', '15 Days', '30 Days']
const PHONE_LABEL_OPTIONS = ['Office', 'Cell', 'Home', 'Toll Free']
const ADDRESS_TYPE_OPTIONS = [
  'Mailing Address', 'Office Address', 'Shipping Address', 'Home Address', 'Address',
]

const emptyForm = {
  name: '', contact_type: 'client', company: '', website: '',
  email: '', phone_1: '', phone_1_label: 'Office',
  phone_2: '', phone_2_label: '',
  tax_number: '', payment_terms: '30 Days',
  default_tax_id: '', default_tax_id_2: '',
  notes: '', addresses: [],
}

const emptyAddress = {
  address_type: 'Mailing Address',
  address_line_1: '', address_line_2: '', city: '',
  province_state: '', postal_code: '', country: 'CA',
}

export default function ContactList() {
  const [searchParams, setSearchParams] = useSearchParams()
  const typeFilter = searchParams.get('type') || ''
  const { data: contacts, loading, refetch } = useApi(() => fetchContacts(typeFilter), [typeFilter])
  const { data: taxes } = useApi(fetchTaxes, [])
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [importOpen, setImportOpen] = useState(false)
  const [importFile, setImportFile] = useState(null)
  const [importType, setImportType] = useState('')
  const [importing, setImporting] = useState(false)
  const toast = useToast()

  const columns = [
    { key: 'name', label: 'Name' },
    { key: 'company', label: 'Company' },
    { key: 'contact_type', label: 'Type', render: (v) => <StatusBadge status={v} /> },
    { key: 'email', label: 'Email' },
    {
      key: 'phone_1', label: 'Phone',
      render: (_, row) => {
        const parts = []
        if (row.phone_1) parts.push(`${row.phone_1_label ? row.phone_1_label + ': ' : ''}${row.phone_1}`)
        if (row.phone_2) parts.push(`${row.phone_2_label ? row.phone_2_label + ': ' : ''}${row.phone_2}`)
        return parts.join(' | ') || ''
      },
    },
    { key: 'payment_terms', label: 'Terms' },
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
    setForm({ ...emptyForm, contact_type: typeFilter || 'client', addresses: [{ ...emptyAddress }] })
    setModalOpen(true)
  }

  const openEdit = (contact) => {
    setEditing(contact)
    const addrs = (contact.addresses && contact.addresses.length > 0)
      ? contact.addresses.map(a => ({ ...a }))
      : [{ ...emptyAddress }]
    setForm({
      name: contact.name,
      contact_type: contact.contact_type,
      company: contact.company || '',
      website: contact.website || '',
      email: contact.email || '',
      phone_1: contact.phone_1 || '',
      phone_1_label: contact.phone_1_label || 'Office',
      phone_2: contact.phone_2 || '',
      phone_2_label: contact.phone_2_label || '',
      tax_number: contact.tax_number || '',
      payment_terms: contact.payment_terms || '30 Days',
      default_tax_id: contact.default_tax_id?.toString() || '',
      default_tax_id_2: contact.default_tax_id_2?.toString() || '',
      notes: contact.notes || '',
      addresses: addrs,
    })
    setModalOpen(true)
  }

  const openImport = () => {
    setImportFile(null)
    setImportType(typeFilter || '')
    setImportOpen(true)
  }

  const handleImport = async () => {
    if (!importFile) return
    setImporting(true)
    try {
      const result = await importContacts(importFile, importType || undefined)
      const msg = `Imported ${result.created} contact${result.created !== 1 ? 's' : ''}`
        + (result.skipped ? `, ${result.skipped} skipped (no name)` : '')
      toast.success(msg)
      if (result.errors?.length) {
        toast.error(`${result.errors.length} row error(s): ${result.errors[0]}`)
      }
      setImportOpen(false)
      refetch()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setImporting(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const payload = {
      ...form,
      default_tax_id: form.default_tax_id ? parseInt(form.default_tax_id) : null,
      default_tax_id_2: form.default_tax_id_2 ? parseInt(form.default_tax_id_2) : null,
    }
    try {
      if (editing) {
        await updateContact(editing.id, payload)
        toast.success('Contact updated')
      } else {
        await createContact(payload)
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

  const openImport = () => {
    setImportFile(null)
    setImportType(typeFilter || '')
    setImportOpen(true)
  }

  const handleImport = async () => {
    if (!importFile) return
    setImporting(true)
    try {
      const result = await importContacts(importFile, importType || undefined)
      const msg = `Imported ${result.created} contact${result.created !== 1 ? 's' : ''}`
        + (result.skipped ? `, ${result.skipped} skipped (no name)` : '')
      toast.success(msg)
      if (result.errors?.length) {
        toast.error(`${result.errors.length} row error(s): ${result.errors[0]}`)
      }
      setImportOpen(false)
      refetch()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setImporting(false)
    }
  }

  const setField = (field) => (e) => setForm({ ...form, [field]: e.target.value })

  const updateAddress = (idx, field, value) => {
    const updated = form.addresses.map((a, i) => i === idx ? { ...a, [field]: value } : a)
    setForm({ ...form, addresses: updated })
  }

  const addAddress = () => {
    // Find first unused address type
    const usedTypes = form.addresses.map(a => a.address_type)
    const nextType = ADDRESS_TYPE_OPTIONS.find(t => !usedTypes.includes(t)) || 'Address'
    setForm({ ...form, addresses: [...form.addresses, { ...emptyAddress, address_type: nextType }] })
  }

  const removeAddress = (idx) => {
    setForm({ ...form, addresses: form.addresses.filter((_, i) => i !== idx) })
  }

  if (loading) return <LoadingSpinner />

  return (
    <div>
      <PageHeader title="Contacts">
        <div className="flex gap-2">
          <Button variant="secondary" onClick={openImport}>Import CSV</Button>
          <Button onClick={openCreate}>New Contact</Button>
        </div>
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
          {/* Basic Info */}
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
            <FormField label="Company">
              <Input value={form.company} onChange={setField('company')} />
            </FormField>
            <FormField label="Website">
              <Input value={form.website} onChange={setField('website')} placeholder="https://" />
            </FormField>
            <FormField label="Email">
              <Input type="email" value={form.email} onChange={setField('email')} />
            </FormField>
            <FormField label="Tax Number">
              <Input value={form.tax_number} onChange={setField('tax_number')} />
            </FormField>
          </div>

          {/* Phone Numbers */}
          <div className="mt-4 border-t pt-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Phone Numbers</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="flex gap-2">
                <div className="w-32">
                  <FormField label="Label">
                    <Select value={form.phone_1_label} onChange={setField('phone_1_label')}>
                      <option value="">--</option>
                      {PHONE_LABEL_OPTIONS.map(l => <option key={l} value={l}>{l}</option>)}
                    </Select>
                  </FormField>
                </div>
                <div className="flex-1">
                  <FormField label="Phone 1">
                    <Input value={form.phone_1} onChange={setField('phone_1')} />
                  </FormField>
                </div>
              </div>
              <div className="flex gap-2">
                <div className="w-32">
                  <FormField label="Label">
                    <Select value={form.phone_2_label} onChange={setField('phone_2_label')}>
                      <option value="">--</option>
                      {PHONE_LABEL_OPTIONS.map(l => <option key={l} value={l}>{l}</option>)}
                    </Select>
                  </FormField>
                </div>
                <div className="flex-1">
                  <FormField label="Phone 2">
                    <Input value={form.phone_2} onChange={setField('phone_2')} />
                  </FormField>
                </div>
              </div>
            </div>
          </div>

          {/* Payment Terms & Default Taxes */}
          <div className="mt-4 border-t pt-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Defaults</h3>
            <div className="grid grid-cols-3 gap-4">
              <FormField label="Payment Terms">
                <Select value={form.payment_terms} onChange={setField('payment_terms')}>
                  {PAYMENT_TERMS_OPTIONS.map(t => <option key={t} value={t}>{t}</option>)}
                </Select>
              </FormField>
              <FormField label="Default Tax 1">
                <Select value={form.default_tax_id} onChange={setField('default_tax_id')}>
                  <option value="">None</option>
                  {taxes?.map(t => (
                    <option key={t.id} value={t.id}>{t.name} ({t.rate}%)</option>
                  ))}
                </Select>
              </FormField>
              <FormField label="Default Tax 2">
                <Select value={form.default_tax_id_2} onChange={setField('default_tax_id_2')}>
                  <option value="">None</option>
                  {taxes?.map(t => (
                    <option key={t.id} value={t.id}>{t.name} ({t.rate}%)</option>
                  ))}
                </Select>
              </FormField>
            </div>
          </div>

          {/* Addresses */}
          <div className="mt-4 border-t pt-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-700">Addresses</h3>
              {form.addresses.length < ADDRESS_TYPE_OPTIONS.length && (
                <button type="button" onClick={addAddress}
                  className="text-xs text-accent hover:underline">
                  + Add Address
                </button>
              )}
            </div>
            {form.addresses.map((addr, idx) => (
              <div key={idx} className="border rounded-lg p-3 mb-3 bg-gray-50">
                <div className="flex items-center justify-between mb-2">
                  <div className="w-48">
                    <Select value={addr.address_type}
                      onChange={(e) => updateAddress(idx, 'address_type', e.target.value)}>
                      {ADDRESS_TYPE_OPTIONS.map(t => <option key={t} value={t}>{t}</option>)}
                    </Select>
                  </div>
                  {form.addresses.length > 1 && (
                    <button type="button" onClick={() => removeAddress(idx)}
                      className="text-xs text-red-500 hover:underline">Remove</button>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <FormField label="Address Line 1">
                    <Input value={addr.address_line_1}
                      onChange={(e) => updateAddress(idx, 'address_line_1', e.target.value)} />
                  </FormField>
                  <FormField label="Address Line 2">
                    <Input value={addr.address_line_2}
                      onChange={(e) => updateAddress(idx, 'address_line_2', e.target.value)} />
                  </FormField>
                  <FormField label="City">
                    <Input value={addr.city}
                      onChange={(e) => updateAddress(idx, 'city', e.target.value)} />
                  </FormField>
                  <FormField label="Province / State">
                    <Input value={addr.province_state}
                      onChange={(e) => updateAddress(idx, 'province_state', e.target.value)} />
                  </FormField>
                  <FormField label="Postal Code">
                    <Input value={addr.postal_code}
                      onChange={(e) => updateAddress(idx, 'postal_code', e.target.value)} />
                  </FormField>
                  <FormField label="Country">
                    <Input value={addr.country}
                      onChange={(e) => updateAddress(idx, 'country', e.target.value)} />
                  </FormField>
                </div>
              </div>
            ))}
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

      {/* Import CSV Modal */}
      <Modal open={importOpen} onClose={() => setImportOpen(false)} title="Import Contacts from CSV">
        <div className="space-y-4">
          <p className="text-sm text-gray-600">
            Upload a CSV file with contact data. Required column: <strong>name</strong>.
            Optional columns: company, email, phone_1, phone_1_label, phone_2, phone_2_label,
            website, tax_number, payment_terms, notes, contact_type,
            address_line_1, address_line_2, city, province_state, postal_code, country.
          </p>

          <FormField label="Import As Type">
            <Select value={importType} onChange={(e) => setImportType(e.target.value)}>
              <option value="">Use CSV column (or default to Client)</option>
              <option value="client">Client</option>
              <option value="supplier">Supplier</option>
              <option value="both">Both</option>
            </Select>
          </FormField>

          <FormField label="CSV File" required>
            <input
              type="file"
              accept=".csv"
              onChange={(e) => setImportFile(e.target.files[0] || null)}
              className="block w-full text-sm text-gray-700 file:mr-4 file:py-2 file:px-4
                file:rounded-md file:border-0 file:text-sm file:font-medium
                file:bg-navy file:text-white hover:file:bg-accent cursor-pointer"
            />
          </FormField>

          <div className="flex items-center justify-between pt-2">
            <a
              href="/api/contacts/import/template"
              download="contacts_template.csv"
              className="text-sm text-accent hover:underline"
            >
              Download CSV Template
            </a>
            <div className="flex gap-3">
              <Button variant="secondary" onClick={() => setImportOpen(false)}>Cancel</Button>
              <Button onClick={handleImport} disabled={!importFile || importing}>
                {importing ? 'Importing...' : 'Import'}
              </Button>
            </div>
          </div>
        </div>
      </Modal>
    </div>
  )
}
