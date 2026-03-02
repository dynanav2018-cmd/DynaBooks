import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { fetchCompany } from '../api/company'

const SettingsContext = createContext({ allowEditPosted: false })

export function SettingsProvider({ children }) {
  const [settings, setSettings] = useState({ allowEditPosted: false })

  const refreshSettings = useCallback(async () => {
    try {
      const company = await fetchCompany()
      const info = company.company_info || {}
      setSettings({
        allowEditPosted: info.allow_edit_posted || false,
      })
    } catch {
      // Keep defaults on error
    }
  }, [])

  useEffect(() => { refreshSettings() }, [refreshSettings])

  return (
    <SettingsContext.Provider value={{ ...settings, refreshSettings }}>
      {children}
    </SettingsContext.Provider>
  )
}

export function useSettings() {
  return useContext(SettingsContext)
}
