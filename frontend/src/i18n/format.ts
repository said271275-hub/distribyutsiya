import type { Language, TranslationKey } from './catalog'
import { resolveMessage } from './catalog'

export function formatDate(value: string, _language: Language) {
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  const date = dateOnly
    ? new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]))
    : new Date(value)
  if (Number.isNaN(date.getTime())) return resolveMessage('format.invalidDate', _language)
  const day = String(date.getDate()).padStart(2, '0')
  const month = String(date.getMonth() + 1).padStart(2, '0')
  return `${day}.${month}.${date.getFullYear()}`
}

export function formatMoney(
  value: string | number,
  language: Language,
  translate: (key: TranslationKey) => string = (key) => resolveMessage(key, language),
) {
  const locale = language === 'ru' ? 'ru-RU' : 'uz-UZ'
  const amount = new Intl.NumberFormat(locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(value))
  return `${amount} ${translate('format.currency')}`
}
