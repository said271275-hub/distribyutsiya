import { ru } from './ru'
import { uz, type TranslationKey } from './uz'

export type Language = 'uz' | 'ru'

const messages: Record<Language, Partial<Record<string, string>>> = { uz, ru }

export function resolveMessage(
  key: string,
  language: Language,
  catalogs: Record<Language, Partial<Record<string, string>>> = messages,
) {
  return catalogs[language][key] ?? catalogs.uz[key] ?? 'Tarjima mavjud emas.'
}

export type { TranslationKey }
