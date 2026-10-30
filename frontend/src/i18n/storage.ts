import type { Language } from './catalog'

export const LANGUAGE_STORAGE_KEY = 'app-language'
const LEGACY_SHOP_LANGUAGE_KEY = 'shop-language'

export function readLanguage(storage: Pick<Storage, 'getItem'>): Language {
  const savedLanguage = storage.getItem(LANGUAGE_STORAGE_KEY)
  if (savedLanguage === 'uz' || savedLanguage === 'ru') return savedLanguage

  return storage.getItem(LEGACY_SHOP_LANGUAGE_KEY) === 'ru' ? 'ru' : 'uz'
}

export function persistLanguage(language: Language, storage: Pick<Storage, 'setItem'>) {
  storage.setItem(LANGUAGE_STORAGE_KEY, language)
}
