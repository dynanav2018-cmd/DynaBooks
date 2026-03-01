import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import { useCompany } from '../../hooks/useCompany'
import { fetchCompanies, createCompanyApi } from '../../api/companies'
import Button from '../../components/shared/Button'
import Modal from '../../components/shared/Modal'
import FormField, { Input, Select } from '../../components/shared/FormField'
import LoadingSpinner from '../../components/shared/LoadingSpinner'

const months = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

export default function CompanySelector() {
  const { data: companies, loading, refetch } = useApi(fetchCompanies)
  const { setCompany } = useCompany()
  const navigate = useNavigate()
  const toast = useToast()

  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState({ name: '', year_start: '1', locale: 'en_CA' })
  const [creating, setCreating] = useState(false)

  const handleSelect = (company) => {
    setCompany(company.slug, company.name)
    navigate('/dashboard')
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    setCreating(true)
    try {
      const newCompany = await createCompanyApi({
        name: form.name,
        year_start: parseInt(form.year_start),
        locale: form.locale,
      })
      toast.success(`Company "${newCompany.name}" created`)
      setModalOpen(false)
      setForm({ name: '', year_start: '1', locale: 'en_CA' })
      refetch()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setCreating(false)
    }
  }

  if (loading) return <LoadingSpinner />

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
      <div className="max-w-md w-full">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-navy">DynaBooks</h1>
          <p className="text-gray-600 mt-2">Select a company to get started</p>
        </div>

        <div className="space-y-3">
          {companies?.map((c) => (
            <button
              key={c.slug}
              onClick={() => handleSelect(c)}
              className="w-full bg-white border border-gray-200 rounded-lg p-4 text-left hover:border-accent hover:shadow-sm transition-all"
            >
              <div className="font-semibold text-gray-800">{c.name}</div>
              <div className="text-xs text-gray-500 mt-1">
                Fiscal year starts {months[(c.year_start || 1) - 1]} &middot; {c.locale}
              </div>
            </button>
          ))}
        </div>

        <div className="mt-6 text-center">
          <Button onClick={() => setModalOpen(true)}>Create New Company</Button>
        </div>

        <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="Create New Company">
          <form onSubmit={handleCreate}>
            <FormField label="Company Name" required>
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Acme Corp"
                required
              />
            </FormField>
            <FormField label="Fiscal Year Start">
              <Select value={form.year_start} onChange={(e) => setForm({ ...form, year_start: e.target.value })}>
                {months.map((m, i) => (
                  <option key={i + 1} value={i + 1}>{m}</option>
                ))}
              </Select>
            </FormField>
            <FormField label="Locale">
              <Input
                value={form.locale}
                onChange={(e) => setForm({ ...form, locale: e.target.value })}
                placeholder="en_CA"
              />
            </FormField>
            <div className="flex justify-end gap-3 mt-6">
              <Button variant="secondary" type="button" onClick={() => setModalOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={creating}>
                {creating ? 'Creating...' : 'Create'}
              </Button>
            </div>
          </form>
        </Modal>
      </div>
    </div>
  )
}
