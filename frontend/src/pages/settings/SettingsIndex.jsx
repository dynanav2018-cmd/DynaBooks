import { useState, useEffect } from 'react'
import { useApi } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import { fetchCompany, updateCompany, uploadLogo, getLogoUrl } from '../../api/company'
import { fetchTaxes, createTax, updateTax, deleteTax } from '../../api/taxes'
import { fetchProducts, createProduct, updateProduct, deleteProduct } from '../../api/products'
import { fetchRecurringJournals, updateRecurringJournal, deleteRecurringJournal } from '../../api/recurringJournals'
import { fetchAccounts } from '../../api/accounts'
import PageHeader from '../../components/shared/PageHeader'
import Button from '../../components/shared/Button'
import FormField, { Input, Select } from '../../components/shared/FormField'
import DataTable from '../../components/shared/DataTable'
import Modal from '../../components/shared/Modal'
import LoadingSpinner from '../../components/shared/LoadingSpinner'
import { useSettings } from '../../hooks/useSettings'

const tabs = [
  { key: 'company', label: 'Company' },
  { key: 'taxes', label: 'Taxes' },
  { key: 'products', label: 'Products & Recurring' },
  { key: 'journal_templates', label: 'Journal Templates' },
]

function CompanySettings() {
  const { data: company, loading, refetch } = useApi(fetchCompany)
  const [form, setForm] = useState({
    name: '', locale: '',
    address_line_1: '', address_line_2: '', city: '',
    province_state: '', postal_code: '', country: '',
    phone: '', email: '',
    allow_edit_posted: false,
  })
  const [saving, setSaving] = useState(false)
  const [logoPreview, setLogoPreview] = useState(null)
  const [logoKey, setLogoKey] = useState(0)
  const toast = useToast()
  const { refreshSettings } = useSettings()

  useEffect(() => {
    if (company) {
      const info = company.company_info || {}
      setForm({
        name: company.name || '',
        locale: company.locale || '',
        address_line_1: info.address_line_1 || '',
        address_line_2: info.address_line_2 || '',
        city: info.city || '',
        province_state: info.province_state || '',
        postal_code: info.postal_code || '',
        country: info.country || '',
        phone: info.phone || '',
        email: info.email || '',
        allow_edit_posted: info.allow_edit_posted || false,
      })
    }
  }, [company])

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateCompany(form)
      toast.success('Company updated')
      refetch()
      refreshSettings()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleLogoChange = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setLogoPreview(URL.createObjectURL(file))
    try {
      await uploadLogo(file)
      toast.success('Logo uploaded')
      setLogoKey((k) => k + 1)
    } catch (err) {
      toast.error(err.message)
    }
  }

  if (loading) return <LoadingSpinner />

  const sf = (field) => (e) => setForm({ ...form, [field]: e.target.value })

  return (
    <div className="max-w-2xl">
      <FormField label="Company Logo">
        <div className="flex items-center gap-4 mb-2">
          <img
            key={logoKey}
            src={logoPreview || `${getLogoUrl()}?t=${logoKey}`}
            alt=""
            className="h-16 w-auto object-contain border border-gray-200 rounded p-1 bg-white"
            onError={(e) => { e.target.style.display = 'none' }}
            onLoad={(e) => { e.target.style.display = 'block' }}
          />
          <label className="cursor-pointer text-sm text-accent hover:underline">
            Choose file...
            <input type="file" accept=".png,.jpg,.jpeg" onChange={handleLogoChange} className="hidden" />
          </label>
        </div>
        <p className="text-xs text-gray-500">PNG or JPG, max 2 MB. Displayed on invoices and reports.</p>
      </FormField>
      <FormField label="Company Name">
        <Input value={form.name} onChange={sf('name')} />
      </FormField>

      <h3 className="text-sm font-semibold text-gray-700 mt-6 mb-3">Address</h3>
      <div className="grid grid-cols-2 gap-4">
        <FormField label="Address Line 1">
          <Input value={form.address_line_1} onChange={sf('address_line_1')} />
        </FormField>
        <FormField label="Address Line 2">
          <Input value={form.address_line_2} onChange={sf('address_line_2')} />
        </FormField>
        <FormField label="City">
          <Input value={form.city} onChange={sf('city')} />
        </FormField>
        <FormField label="Province / State">
          <Input value={form.province_state} onChange={sf('province_state')} />
        </FormField>
        <FormField label="Postal Code">
          <Input value={form.postal_code} onChange={sf('postal_code')} />
        </FormField>
        <FormField label="Country">
          <Input value={form.country} onChange={sf('country')} />
        </FormField>
        <FormField label="Phone">
          <Input value={form.phone} onChange={sf('phone')} />
        </FormField>
        <FormField label="Email">
          <Input type="email" value={form.email} onChange={sf('email')} />
        </FormField>
      </div>

      <h3 className="text-sm font-semibold text-gray-700 mt-6 mb-3">Accounting Settings</h3>
      <label className="flex items-start gap-3 cursor-pointer">
        <input
          type="checkbox"
          checked={form.allow_edit_posted}
          onChange={(e) => setForm({ ...form, allow_edit_posted: e.target.checked })}
          className="mt-1 h-4 w-4 rounded border-gray-300 text-accent focus:ring-accent"
        />
        <div>
          <span className="text-sm font-medium text-gray-700">Allow editing posted transactions</span>
          <p className="text-xs text-gray-500 mt-0.5">
            When enabled, posted invoices, bills, and journal entries can be edited or deleted.
            The transaction will be un-posted, modified, and can then be re-posted.
          </p>
        </div>
      </label>

      <div className="mt-6">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save'}
        </Button>
      </div>
    </div>
  )
}

function TaxSettings() {
  const { data: taxList, loading, refetch } = useApi(fetchTaxes)
  const { data: controlAccounts } = useApi(() => fetchAccounts('Control'), [])
  const { data: expenseAccounts } = useApi(() => fetchAccounts(null, 'expense'), [])
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState({ name: '', code: '', rate: '', account_id: '', account_category: 'control' })
  const toast = useToast()

  // Combine accounts for lookup
  const allTaxAccounts = [...(controlAccounts || []), ...(expenseAccounts || [])]
  const getAccountInfo = (accountId) => {
    const acct = allTaxAccounts.find((a) => a.id === accountId)
    if (!acct) return null
    const isExpense = (expenseAccounts || []).some((a) => a.id === accountId)
    return { ...acct, isExpense }
  }

  const columns = [
    { key: 'name', label: 'Name' },
    { key: 'code', label: 'Code' },
    { key: 'rate', label: 'Rate', render: (v) => `${v}%` },
    {
      key: 'account_id',
      label: 'Account Type',
      render: (v) => {
        const info = getAccountInfo(v)
        if (!info) return '—'
        return (
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${
            info.isExpense ? 'bg-orange-100 text-orange-800' : 'bg-blue-100 text-blue-800'
          }`}>
            {info.isExpense ? 'Expense' : 'Control'}
          </span>
        )
      },
    },
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
    setForm({ name: '', code: '', rate: '', account_id: '', account_category: 'control' })
    setModalOpen(true)
  }

  const openEdit = (tax) => {
    setEditing(tax)
    const isExpense = (expenseAccounts || []).some((a) => a.id === tax.account_id)
    setForm({
      name: tax.name, code: tax.code, rate: tax.rate.toString(),
      account_id: tax.account_id || '',
      account_category: isExpense ? 'expense' : 'control',
    })
    setModalOpen(true)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const payload = { ...form, rate: parseFloat(form.rate) }
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
          <FormField label="Account Type">
            <Select value={form.account_category} onChange={(e) => setForm({ ...form, account_category: e.target.value, account_id: '' })}>
              <option value="control">Control (Liability / Reclaimable)</option>
              <option value="expense">Expense (Non-reclaimable)</option>
            </Select>
            <p className="text-xs text-gray-500 mt-1">
              {form.account_category === 'expense'
                ? 'Use for taxes paid that cannot be recovered (e.g. PST on purchases without tax exemption).'
                : 'Use for taxes collected or paid that are reported to / recoverable from the government.'}
            </p>
          </FormField>
          <FormField label="Account">
            <Select value={form.account_id} onChange={(e) => setForm({ ...form, account_id: e.target.value })}>
              <option value="">Select account...</option>
              {(form.account_category === 'expense' ? expenseAccounts : controlAccounts)?.map((a) => (
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
  const [subTab, setSubTab] = useState('product')
  const { data: products, loading, refetch } = useApi(() => fetchProducts(subTab), [subTab])
  const { data: revenueAccounts } = useApi(() => fetchAccounts('Operating Revenue'), [])
  const { data: expenseAccounts } = useApi(() => fetchAccounts(null, 'expense'), [])
  const { data: taxes } = useApi(fetchTaxes, [])
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState({ name: '', description: '', default_price: '', revenue_account_id: '', expense_account_id: '', tax_id: '' })
  const toast = useToast()

  const isRecurring = subTab === 'recurring'

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
    setForm({ name: '', description: '', default_price: '', revenue_account_id: '', expense_account_id: '', tax_id: '' })
    setModalOpen(true)
  }

  const openEdit = (product) => {
    setEditing(product)
    setForm({
      name: product.name,
      description: product.description || '',
      default_price: product.default_price?.toString() || '',
      revenue_account_id: product.revenue_account_id?.toString() || '',
      expense_account_id: product.expense_account_id?.toString() || '',
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
      product_type: subTab,
      tax_id: form.tax_id ? parseInt(form.tax_id) : null,
    }
    if (isRecurring) {
      payload.expense_account_id = parseInt(form.expense_account_id)
    } else {
      payload.revenue_account_id = parseInt(form.revenue_account_id)
    }
    try {
      if (editing) {
        await updateProduct(editing.id, payload)
        toast.success(isRecurring ? 'Recurring expense updated' : 'Product updated')
      } else {
        await createProduct(payload)
        toast.success(isRecurring ? 'Recurring expense created' : 'Product created')
      }
      setModalOpen(false)
      refetch()
    } catch (err) {
      toast.error(err.message)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Deactivate this item?')) return
    try {
      await deleteProduct(id)
      toast.success('Item deactivated')
      refetch()
    } catch (err) {
      toast.error(err.message)
    }
  }

  if (loading) return <LoadingSpinner />

  return (
    <div>
      <div className="flex gap-1 mb-4 bg-gray-100 rounded-lg p-1 w-fit">
        <button
          onClick={() => setSubTab('product')}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
            subTab === 'product' ? 'bg-white text-navy shadow-sm' : 'text-gray-600 hover:text-gray-800'
          }`}
        >
          Products
        </button>
        <button
          onClick={() => setSubTab('recurring')}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
            subTab === 'recurring' ? 'bg-white text-navy shadow-sm' : 'text-gray-600 hover:text-gray-800'
          }`}
        >
          Recurring Expenses
        </button>
      </div>

      <div className="flex justify-end mb-4">
        <Button onClick={openCreate}>{isRecurring ? 'New Recurring Expense' : 'New Product'}</Button>
      </div>
      <DataTable columns={columns} data={products || []} emptyMessage={isRecurring ? 'No recurring expenses found' : 'No products found'} />
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? (isRecurring ? 'Edit Recurring Expense' : 'Edit Product') : (isRecurring ? 'New Recurring Expense' : 'New Product')}>
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
          {isRecurring ? (
            <FormField label="Expense Account" required>
              <Select value={form.expense_account_id} onChange={(e) => setForm({ ...form, expense_account_id: e.target.value })} required>
                <option value="">Select account...</option>
                {expenseAccounts?.map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </Select>
            </FormField>
          ) : (
            <FormField label="Revenue Account" required>
              <Select value={form.revenue_account_id} onChange={(e) => setForm({ ...form, revenue_account_id: e.target.value })} required>
                <option value="">Select account...</option>
                {revenueAccounts?.map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </Select>
            </FormField>
          )}
          <FormField label="Tax">
            <Select value={form.tax_id} onChange={(e) => setForm({ ...form, tax_id: e.target.value })}>
              <option value="">No tax</option>
              {taxes?.map((t) => (
                <option key={t.id} value={t.id}>{t.name} ({t.rate}%)</option>
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

function JournalTemplateSettings() {
  const { data: templates, loading, refetch } = useApi(fetchRecurringJournals, [])
  const { data: accounts } = useApi(fetchAccounts, [])
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState({ name: '', narration: '' })
  const toast = useToast()

  const getAccountName = (id) => {
    const acct = accounts?.find((a) => a.id === id)
    return acct ? acct.name : `#${id}`
  }

  const columns = [
    { key: 'name', label: 'Name' },
    { key: 'narration', label: 'Description' },
    { key: 'account_id', label: 'Main Account', render: (v) => getAccountName(v) },
    {
      key: 'line_items',
      label: 'Lines',
      render: (v) => `${v?.length || 0} items`,
    },
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

  const openEdit = (tpl) => {
    setEditing(tpl)
    setForm({ name: tpl.name, narration: tpl.narration || '' })
    setModalOpen(true)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      await updateRecurringJournal(editing.id, {
        name: form.name,
        narration: form.narration,
      })
      toast.success('Template updated')
      setModalOpen(false)
      refetch()
    } catch (err) {
      toast.error(err.message)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this template?')) return
    try {
      await deleteRecurringJournal(id)
      toast.success('Template deleted')
      refetch()
    } catch (err) {
      toast.error(err.message)
    }
  }

  if (loading) return <LoadingSpinner />

  return (
    <div>
      <p className="text-sm text-gray-500 mb-4">
        Recurring journal templates are created from the Journal Entry form using the "Save Recurring" button.
      </p>
      <DataTable columns={columns} data={templates || []} emptyMessage="No journal templates saved yet" />
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="Edit Template">
        <form onSubmit={handleSubmit}>
          <FormField label="Name" required>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </FormField>
          <FormField label="Description">
            <Input value={form.narration} onChange={(e) => setForm({ ...form, narration: e.target.value })} />
          </FormField>
          <div className="flex justify-end gap-3 mt-6">
            <Button variant="secondary" type="button" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button type="submit">Update</Button>
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
        {activeTab === 'journal_templates' && <JournalTemplateSettings />}
      </div>
    </div>
  )
}
