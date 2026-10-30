import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { resolveMessage, type Language } from './catalog'
import { LANGUAGE_STORAGE_KEY, persistLanguage, readLanguage } from './storage'
import { TranslationContext } from './useTranslation'

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(() => readLanguage(localStorage))

  const setLanguage = useCallback((nextLanguage: Language) => {
    persistLanguage(nextLanguage, localStorage)
    setLanguageState(nextLanguage)
  }, [])

  const t = useCallback(
    (key: Parameters<typeof resolveMessage>[0]) => resolveMessage(key, language),
    [language],
  )

  useEffect(() => {
    document.documentElement.lang = language
    document.title = t('app.title')
    const description = document.querySelector<HTMLMetaElement>('meta[name="description"]')
    if (description) description.content = t('app.description')
  }, [language, t])

  useEffect(() => {
    const syncLanguage = (event: StorageEvent) => {
      if (event.key === LANGUAGE_STORAGE_KEY && (event.newValue === 'uz' || event.newValue === 'ru')) {
        setLanguageState(event.newValue)
      }
    }
    window.addEventListener('storage', syncLanguage)
    return () => window.removeEventListener('storage', syncLanguage)
  }, [])

  const value = useMemo(() => ({ language, setLanguage, t }), [language, setLanguage, t])
  return <TranslationContext.Provider value={value}>{children}</TranslationContext.Provider>
}
