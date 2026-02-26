import { useState, useEffect } from 'react'
import { useApi } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import { fetchCompany, updateCompany } from '../../api/company'
import { fetchTaxes, createTax, updateTax, deleteTax } from '../../api/taxes'
import { fetchProducts, createProduct, updateProduct, deleteProduct } from '../../api/products'
import { fetchAccounts } from '../../api/accounts'
import PageHeader from '../../components/shared/PageHeader'
import Button from '../../components/shared/Button'
import FormField, { Input, Select } from '../../components/shared/FormField'
import DataTable from '../../components/shared/DataTable'
import Modal from '../../components/shared/Modal'
import LoadingSpinner from '../../components/shared/LoadingSpinner'

const tabs = [
  { key: 'company', label: 'Company' },
  { key: 'taxes', label: 'Taxes' },
  { key: 'products', label: 'Products' },
]

function CompanySettings() {
  const { data: company, loading, refetch } = useApi(fetchCompany)
  const [form, setForm] = useState({ name: '', locale: '' })
  const [saving, setSaving] = useState(false)
  const toast = useToast()

  useEffect(() => {
    if (company) {
      setForm({ name: company.name || '', locale: company.locale || '' })
    }
  }, [company])

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateCompany(form)
      toast.success('Company updated')
      refetch()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingSpinner />

  return (
    <div className="max-w-lg">
      <FormField label="Company Name">
        <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
      </FormField>
      <FormField label="Locale">
        <Input value={form.locale} onChange={(e) => setForm({ ...form, locale: e.target.value })} />
      </FormField>
      <Button onClick={handleSave} disabled={saving}>
        {saving ? 'Saving...' : 'Save'}
      </Button>
    </div>
  )
}

function TaxSettings() {
  const { data: taxList, loading, refetch } = useApi(fetchTaxes)
  const { data: accounts } = useApi(() => fetchAccounts('Control'), [])
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState({ name: '', code: '', rate: '', account_id: '' })
  const toast = useToast()

  const columns = [
    { key: 'name', label: 'Name' },
    { key: 'code', label: 'Code' },
    { key: 'rate', label: 'Rate', render: (v) => `${(v * 100).toFixed(1)}%` },
    {
      key: 'actions',
      label: '',
      render: (_, row) => (
        <div className="flex gap-2">
          <button onClick={() => openEdit(row)} className="text-accent hover:underline text-xs">Edit</button>
          <button onClick={() => handleDelete(row.id)} className="text-red-500 hover:underline text-xs">Delete</button>
        </div>
      ),
    },
  ]

  const openCreate = () => {
    setEditing(null)
    setForm({ name: '', code: '', rate: '', account_id: '' })
    setModalOpen(true)
  }

  const openEdit = (tax) => {
    setEditing(tax)
    setForm({ name: tax.name, code: tax.code, rate: (tax.rate * 100).toString(), account_id: tax.account_id || '' })
    setModalOpen(true)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const payload = { ...form, rate: parseFloat(form.rate) / 100 }
    if (payload.account_id) payload.account_id = parseInt(payload.account_id)
    try {
      if (editing) {
        await updateTax(editing.id, payload)
        toast.success('Tax updated')
      } else {
        await createTax(payload)
        toast.success('Tax created')
      }
      setModalOpen(false)
      refetch()
    } catch (err) {
      toast.error(err.message)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this tax?')) return
    try {
      await deleteTax(id)
      toast.success('Tax deleted')
      refetch()
    } catch (err) {
      toast.error(err.message)
    }
  }

  if (loading) return <LoadingSpinner />

  return (
    <div>
      <div className="flex justify-end mb-4">
        <Button onClick={openCreate}>New Tax</Button>
      </div>
      <DataTable columns={columns} data={taxList || []} emptyMessage="No taxes configured" />
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Edit Tax' : 'New Tax'}>
        <form onSubmit={handleSubmit}>
          <FormField label="Name" required>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </FormField>
          <FormField label="Code" required>
            <Input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required />
          </FormField>
          <FormField label="Rate (%)" required>
            <Input type="number" step="0.1" value={form.rate} onChange={(e) => setForm({ ...form, rate: e.target.value })} required />
          </FormField>
          <FormField label="Control Account">
            <Select value={form.account_id} onChange={(e) => setForm({ ...form, account_id: e.target.value })}>
              <option value="">None</option>
              {accounts?.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </Select>
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

function ProductSettings() {
  const { data: products, loading, refetch } = useApi(fetchProducts)
  const { data: accounts } = useApi(() => fetchAccounts('Operating Revenue'), [])
  const { data: taxes } = useApi(fetchTaxes, [])
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState({ name: '', description: '', default_price: '', revenue_account_id: '', tax_id: '' })
  const toast = useToast()

  const columns = [
    { key: 'name', label: 'Name' },
    { key: 'description', label: 'Description' },
    { key: 'default_price', label: 'Price', render: (v) => `$${(v || 0).toFixed(2)}` },
    {
      key: 'actions',
      label: '',
      render: (_, row) => (
        <div className="flex gap-2">
          <button onClick={() => openEdit(row)} className="text-accent hover:underline text-xs">Edit</button>
          <button onClick={() => handleDelete(row.id)} className="text-red-500 hover:underline text-xs">Deactivate</button>
        </div>
      ),
    },
  ]

  const openCreate = () => {
    setEditing(null)
    setForm({ name: '', description: '', default_price: '', revenue_account_id: '', tax_id: '' })
    setModalOpen(true)
  }

  const openEdit = (product) => {
    setEditing(product)
    setForm({
      name: product.name,
      description: product.description || '',
      default_price: product.default_price?.toString() || '',
      revenue_account_id: product.revenue_account_id?.toString() || '',
      tax_id: product.tax_id?.toString() || '',
    })
    setModalOpen(true)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const payload = {
      name: form.name,
      description: form.description,
      default_price: parseFloat(form.default_price) || 0,
      revenue_account_id: parseInt(form.revenue_account_id),
      tax_id: form.tax_id ? parseInt(form.tax_id) : null,
    }
    try {
      if (editing) {
        await updateProduct(editing.id, payload)
        toast.success('Product updated')
      } else {
        await createProduct(payload)
        toast.success('Product created')
      }
      setModalOpen(false)
      refetch()
    } catch (err) {
      toast.error(err.message)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Deactivate this product?')) return
    try {
      await deleteProduct(id)
      toast.success('Product deactivated')
      refetch()
    } catch (err) {
      toast.error(err.message)
    }
  }

  if (loading) return <LoadingSpinner />

  return (
    <div>
      <div className="flex justify-end mb-4">
        <Button onClick={openCreate}>New Product</Button>
      </div>
      <DataTable columns={columns} data={products || []} emptyMessage="No products found" />
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Edit Product' : 'New Product'}>
        <form onSubmit={handleSubmit}>
          <FormField label="Name" required>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </FormField>
          <FormField label="Description">
            <Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </FormField>
          <FormField label="Default Price">
            <Input type="number" step="0.01" value={form.default_price} onChange={(e) => setForm({ ...form, default_price: e.target.value })} />
          </FormField>
          <FormField label="Revenue Account" required>
            <Select value={form.revenue_account_id} onChange={(e) => setForm({ ...form, revenue_account_id: e.target.value })} required>
              <option value="">Select account...</option>
              {accounts?.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </Select>
          </FormField>
          <FormField label="Tax">
            <Select value={form.tax_id} onChange={(e) => setForm({ ...form, tax_id: e.target.value })}>
              <option value="">No tax</option>
              {taxes?.map((t) => (
                <option key={t.id} value={t.id}>{t.name} ({(t.rate * 100).toFixed(0)}%)</option>
              ))}
            </Select>
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

export default function SettingsIndex() {
  const [activeTab, setActiveTab] = useState('company')

  return (
    <div>
      <PageHeader title="Settings" />

      <div className="flex gap-1 mb-6 bg-gray-100 rounded-lg p-1 w-fit">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? 'bg-white text-navy shadow-sm'
                : 'text-gray-600 hover:text-gray-800'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        {activeTab === 'company' && <CompanySettings />}
        {activeTab === 'taxes' && <TaxSettings />}
        {activeTab === 'products' && <ProductSettings />}
      </div>
    </div>
  )
}
