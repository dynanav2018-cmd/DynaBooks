import { Link } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { fetchDashboard } from '../api/dashboard'
import { formatCurrency } from '../utils/format'
import Card from '../components/shared/Card'
import LoadingSpinner from '../components/shared/LoadingSpinner'
import PageHeader from '../components/shared/PageHeader'
import Button from '../components/shared/Button'

export default function Dashboard() {
  const { data, loading, error } = useApi(fetchDashboard)

  if (loading) return <LoadingSpinner />
  if (error) return <p className="text-red-600">Error: {error}</p>

  return (
    <div>
      <PageHeader title="Dashboard">
        <Link to="/invoices/new">
          <Button>New Invoice</Button>
        </Link>
      </PageHeader>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        <Card title="Cash Balance" value={formatCurrency(data.total_cash)} accent />
        <Card title="Accounts Receivable" value={formatCurrency(data.accounts_receivable)} />
        <Card title="Accounts Payable" value={formatCurrency(data.accounts_payable)} />
        <Card title="Revenue This Month" value={formatCurrency(data.revenue_this_month)} />
        <Card title="Expenses This Month" value={formatCurrency(data.expenses_this_month)} />
        <Card
          title="Net Income This Month"
          value={formatCurrency(data.net_income_this_month)}
          accent
        />
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Quick Actions</h3>
        <div className="flex flex-wrap gap-3">
          <Link to="/invoices/new"><Button variant="secondary">Create Invoice</Button></Link>
          <Link to="/contacts"><Button variant="secondary">Manage Contacts</Button></Link>
          <Link to="/reports"><Button variant="secondary">View Reports</Button></Link>
          <Link to="/accounts"><Button variant="secondary">Chart of Accounts</Button></Link>
        </div>
      </div>
    </div>
  )
}
