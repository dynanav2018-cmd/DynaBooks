import { useState, useEffect, useMemo } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useToast } from '../../hooks/useToast'
import { useApi } from '../../hooks/useApi'
import { createInvoice, fetchInvoice, updateInvoice } from '../../api/invoices'
import { fetchContacts, fetchContactAddresses } from '../../api/contacts'
import { fetchAccounts } from '../../api/accounts'
import { fetchTaxes } from '../../api/taxes'
import { fetchProducts } from '../../api/products'
import { todayISO } from '../../utils/format'
import PageHeader from '../../components/shared/PageHeader'
import Button from '../../components/shared/Button'
import FormField, { Input, Select } from '../../components/shared/FormField'
import LoadingSpinner from '../../components/shared/LoadingSpinner'

const emptyLine = { narration: '', account_id: '', quantity: 1, amount: '', tax_id: '', product_id: '' }

export default function InvoiceForm() {
  const { id } = useParams()
  const isEdit = Boolean(id)
  const navigate = useNavigate()
  const toast = useToast()

  const { data: contacts } = useApi(() => fetchContacts('client'), [])
  const { data: accounts } = useApi(() => fetchAccounts('Operating Revenue'), [])
  const { data: taxes } = useApi(fetchTaxes, [])
  const { data: products } = useApi(() => fetchProducts('product'), [])

  const [form, setForm] = useState({
    contact_id: '',
    billing_address_id: '',
    shipping_address_id: '',
    transaction_date: todayISO(),
    narration: 'Client Invoice',
    line_items: [{ ...emptyLine }],
  })
  const [saving, setSaving] = useState(false)
  const [loaded, setLoaded] = useState(!isEdit)
  const [contactAddresses, setContactAddresses] = useState([])

  useEffect(() => {
    if (isEdit) {
      Promise.all([fetchInvoice(id), fetchProducts('product')]).then(([inv, prods]) => {
        setForm({
          contact_id: inv.contact_id?.toString() || '',
          billing_address_id: inv.billing_address_id?.toString() || '',
          shipping_address_id: inv.shipping_address_id?.toString() || '',
          transaction_date: inv.transaction_date?.split('T')[0] || todayISO(),
          narration: inv.narration || '',
          line_items: inv.line_items.map((li) => {
            const matched = prods?.find((p) => p.name === li.narration)
            return {
              narration: li.narration || '',
              account_id: li.account_id || '',
              quantity: li.quantity || 1,
              amount: li.amount || '',
              tax_id: li.tax_id || '',
              product_id: matched ? matched.id.toString() : '',
            }
          }),
        })
        if (inv.contact_id) {
          fetchContactAddresses(inv.contact_id).then(setContactAddresses).catch(() => {})
        }
        setLoaded(true)
      }).catch((err) => {
        toast.error(err.message)
        navigate('/invoices')
      })
    }
  }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch addresses when contact changes
  const handleContactChange = (contactId) => {
    setForm(prev => ({ ...prev, contact_id: contactId, billing_address_id: '', shipping_address_id: '' }))
    if (contactId) {
      fetchContactAddresses(contactId).then((addrs) => {
        setContactAddresses(addrs)
        // Default billing to first address
        if (addrs.length > 0) {
          setForm(prev => ({ ...prev, billing_address_id: addrs[0].id.toString(), shipping_address_id: addrs[0].id.toString() }))
        }
      }).catch(() => setContactAddresses([]))
    } else {
      setContactAddresses([])
    }
  }

  const updateLine = (index, field, value) => {
    setForm((prev) => {
      const lines = [...prev.line_items]
      lines[index] = { ...lines[index], [field]: value }
      return { ...prev, line_items: lines }
    })
  }

  const selectProduct = (index, productId) => {
    if (!productId) {
      updateLine(index, 'product_id', '')
      return
    }
    const product = products?.find((p) => p.id === parseInt(productId))
    if (!product) return
    setForm((prev) => {
      const lines = [...prev.line_items]
      lines[index] = {
        ...lines[index],
        product_id: productId.toString(),
        narration: product.name,
        account_id: product.revenue_account_id?.toString() || '',
        amount: product.default_price?.toString() || '',
        tax_id: product.tax_id?.toString() || '',
      }
      return { ...prev, line_items: lines }
    })
  }

  const addLine = () => {
    setForm((prev) => ({ ...prev, line_items: [...prev.line_items, { ...emptyLine }] }))
  }

  const removeLine = (index) => {
    if (form.line_items.length <= 1) return
    setForm((prev) => ({
      ...prev,
      line_items: prev.line_items.filter((_, i) => i !== index),
    }))
  }

  const totals = useMemo(() => {
    let subtotal = 0
    let taxTotal = 0
    const taxRates = {}
    taxes?.forEach((t) => { taxRates[t.id] = t.rate })

    form.line_items.forEach((li) => {
      const lineAmount = (parseFloat(li.amount) || 0) * (parseFloat(li.quantity) || 0)
      subtotal += lineAmount
      if (li.tax_id && taxRates[li.tax_id]) {
        taxTotal += lineAmount * taxRates[li.tax_id] / 100
      }
    })

    return { subtotal, taxTotal, total: subtotal + taxTotal }
  }, [form.line_items, taxes])

  const handleSubmit = async (post = false) => {
    setSaving(true)
    try {
      const payload = {
        narration: form.narration,
        transaction_date: form.transaction_date,
        contact_id: form.contact_id ? parseInt(form.contact_id) : undefined,
        billing_address_id: form.billing_address_id ? parseInt(form.billing_address_id) : undefined,
        shipping_address_id: form.shipping_address_id ? parseInt(form.shipping_address_id) : undefined,
        post,
        line_items: form.line_items.map((li) => ({
          narration: li.narration,
          account_id: parseInt(li.account_id),
          quantity: parseFloat(li.quantity) || 1,
          amount: parseFloat(li.amount) || 0,
          tax_id: li.tax_id ? parseInt(li.tax_id) : undefined,
        })),
      }

      if (isEdit) {
        await updateInvoice(id, payload)
        toast.success(post ? 'Invoice updated & posted' : 'Invoice updated')
      } else {
        const result = await createInvoice(payload)
        toast.success(post ? 'Invoice created & posted' : 'Invoice saved as draft')
        navigate(`/invoices/${result.id}`)
        return
      }
      navigate('/invoices')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (!loaded) return <LoadingSpinner />

  const formatCurrency = (v) => `$${v.toFixed(2)}`

  return (
    <div>
      <PageHeader title={isEdit ? 'Edit Invoice' : 'New Invoice'}>
        <Button variant="secondary" onClick={() => navigate('/invoices')}>Cancel</Button>
      </PageHeader>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <FormField label="Client">
            <Select value={form.contact_id} onChange={(e) => handleContactChange(e.target.value)}>
              <option value="">Select client...</option>
              {contacts?.map((c) => (
                <option key={c.id} value={c.id}>{c.name}{c.company ? ` (${c.company})` : ''}</option>
              ))}
            </Select>
          </FormField>
          <FormField label="Date" required>
            <Input
              type="date"
              value={form.transaction_date}
              onChange={(e) => setForm({ ...form, transaction_date: e.target.value })}
              required
            />
          </FormField>
          <FormField label="Description">
            <Input
              value={form.narration}
              onChange={(e) => setForm({ ...form, narration: e.target.value })}
            />
          </FormField>
        </div>

        {contactAddresses.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <FormField label="Billing Address">
              <Select value={form.billing_address_id} onChange={(e) => {
                const val = e.target.value
                setForm(prev => ({
                  ...prev,
                  billing_address_id: val,
                  shipping_address_id: prev.shipping_address_id || val,
                }))
              }}>
                <option value="">Select address...</option>
                {contactAddresses.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.address_type}: {a.address_line_1}{a.city ? `, ${a.city}` : ''}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField label="Shipping Address">
              <Select value={form.shipping_address_id} onChange={(e) => setForm({ ...form, shipping_address_id: e.target.value })}>
                <option value="">Same as billing</option>
                {contactAddresses.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.address_type}: {a.address_line_1}{a.city ? `, ${a.city}` : ''}
                  </option>
                ))}
              </Select>
            </FormField>
          </div>
        )}

        <h3 className="text-sm font-semibold text-gray-700 mb-3">Line Items</h3>
        <div className="space-y-3">
          {form.line_items.map((li, i) => (
            <div key={i} className="grid grid-cols-12 gap-2 items-end">
              {products?.length > 0 && (
                <div className="col-span-2">
                  {i === 0 && <label className="block text-xs text-gray-500 mb-1">Product</label>}
                  <Select value={li.product_id} onChange={(e) => selectProduct(i, e.target.value)}>
                    <option value="">Select...</option>
                    {products.map((p) => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </Select>
                </div>
              )}
              <div className={products?.length > 0 ? 'col-span-2' : 'col-span-3'}>
                {i === 0 && <label className="block text-xs text-gray-500 mb-1">Description</label>}
                <Input
                  value={li.narration}
                  onChange={(e) => updateLine(i, 'narration', e.target.value)}
                  placeholder="Description"
                />
              </div>
              <div className="col-span-2">
                {i === 0 && <label className="block text-xs text-gray-500 mb-1">Account</label>}
                <Select value={li.account_id} onChange={(e) => updateLine(i, 'account_id', e.target.value)} required>
                  <option value="">Account...</option>
                  {accounts?.map((a) => (
                    <option key={a.id} value={a.id}>{a.name}</option>
                  ))}
                </Select>
              </div>
              <div className="col-span-1">
                {i === 0 && <label className="block text-xs text-gray-500 mb-1">Qty</label>}
                <Input
                  type="number"
                  min="1"
                  step="1"
                  value={li.quantity}
                  onChange={(e) => updateLine(i, 'quantity', e.target.value)}
                />
              </div>
              <div className="col-span-2">
                {i === 0 && <label className="block text-xs text-gray-500 mb-1">Price</label>}
                <Input
                  type="number"
                  min="0"
                  step="0.01"
                  value={li.amount}
                  onChange={(e) => updateLine(i, 'amount', e.target.value)}
                  placeholder="0.00"
                />
              </div>
              <div className="col-span-2">
                {i === 0 && <label className="block text-xs text-gray-500 mb-1">Tax</label>}
                <Select value={li.tax_id} onChange={(e) => updateLine(i, 'tax_id', e.target.value)}>
                  <option value="">No tax</option>
                  {taxes?.map((t) => (
                    <option key={t.id} value={t.id}>{t.name} ({t.rate}%)</option>
                  ))}
                </Select>
              </div>
              <div className="col-span-1">
                <button
                  type="button"
                  onClick={() => removeLine(i)}
                  className="p-2 text-red-400 hover:text-red-600 disabled:opacity-30"
                  disabled={form.line_items.length <= 1}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
          ))}
        </div>

        <button
          type="button"
          onClick={addLine}
          className="mt-3 text-sm text-accent hover:text-accent-dark font-medium"
        >
          + Add Line Item
        </button>

        <div className="mt-6 flex justify-end">
          <div className="w-64 space-y-1 text-sm">
            <div className="flex justify-between text-gray-600">
              <span>Subtotal</span>
              <span>{formatCurrency(totals.subtotal)}</span>
            </div>
            <div className="flex justify-between text-gray-600">
              <span>Tax</span>
              <span>{formatCurrency(totals.taxTotal)}</span>
            </div>
            <div className="flex justify-between font-bold text-gray-900 text-base border-t border-gray-200 pt-2">
              <span>Total</span>
              <span>{formatCurrency(totals.total)}</span>
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-8 pt-4 border-t border-gray-200">
          <Button variant="secondary" onClick={() => navigate('/invoices')} disabled={saving}>
            Cancel
          </Button>
          <Button variant="secondary" onClick={() => handleSubmit(false)} disabled={saving}>
            {isEdit ? 'Update' : 'Save Draft'}
          </Button>
          <Button onClick={() => handleSubmit(true)} disabled={saving}>
            {isEdit ? 'Update & Post' : 'Save & Post'}
          </Button>
        </div>
      </div>
    </div>
  )
}
