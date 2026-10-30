import { createContext, useContext } from 'react'
import type { Language, TranslationKey } from './catalog'

export type TranslationContextValue = {
  language: Language
  setLanguage: (language: Language) => void
  t: (key: TranslationKey) => string
}

export const TranslationContext = createContext<TranslationContextValue | null>(null)

export function useTranslation() {
  const context = useContext(TranslationContext)
  if (!context) throw new Error('useTranslation must be used inside I18nProvider.')
  return context
}
