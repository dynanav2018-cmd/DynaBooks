import { createContext, useContext, useState, useCallback } from 'react'

const CompanyContext = createContext(null)

export function CompanyProvider({ children }) {
  const [company, setCompanyState] = useState(() => {
    const slug = localStorage.getItem('currentCompany')
    const name = localStorage.getItem('currentCompanyName')
    return slug ? { slug, name: name || slug } : null
  })

  const setCompany = useCallback((slug, name) => {
    if (slug) {
      localStorage.setItem('currentCompany', slug)
      localStorage.setItem('currentCompanyName', name || slug)
      setCompanyState({ slug, name: name || slug })
    } else {
      localStorage.removeItem('currentCompany')
      localStorage.removeItem('currentCompanyName')
      setCompanyState(null)
    }
  }, [])

  return (
    <CompanyContext.Provider value={{ company, setCompany }}>
      {children}
    </CompanyContext.Provider>
  )
}

export function useCompany() {
  const ctx = useContext(CompanyContext)
  if (!ctx) throw new Error('useCompany must be used inside CompanyProvider')
  return ctx
}
