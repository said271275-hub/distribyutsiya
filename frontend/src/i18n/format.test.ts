import { describe, expect, it } from 'vitest'
import { formatDate, formatMoney } from './format'
import { resolveMessage } from './catalog'
import { LANGUAGE_STORAGE_KEY, persistLanguage, readLanguage } from './storage'
import { translateServerError } from './serverErrors'
import { ru } from './ru'
import { uz } from './uz'

const ruUzbekExceptions: string[] = []
const forbiddenUzbekWords = [
  'do‘kon',
  'do\'kon',
  'buyurtma',
  'reys',
  'haydovchi',
  'dispetcher',
  'yetkazildi',
  'qarz',
  'to‘lov',
  'to\'lov',
  'oldindan to‘langan',
  'tara',
  'yuklash ro‘yxati',
  'mahsulot',
  'ombor',
  'hisobot',
  'xodim',
]

describe('translation catalogs', () => {
  it('has matching UZ and RU keys', () => {
    expect(Object.keys(ru).sort()).toEqual(Object.keys(uz).sort())
  })

  describe('language preference storage', () => {
    it('persists only the language setting and restores it on reload', () => {
      const data = new Map<string, string>()
      const storage = {
        getItem: (key: string) => data.get(key) ?? null,
        setItem: (key: string, value: string) => data.set(key, value),
      }

      persistLanguage('ru', storage)
      expect(readLanguage(storage)).toBe('ru')
      expect([...data.keys()]).toEqual([LANGUAGE_STORAGE_KEY])
    })

    it('keeps the previous shop language as a one-time migration fallback', () => {
      const storage = {
        getItem: (key: string) => key === 'shop-language' ? 'ru' : null,
        setItem: () => undefined,
      }
      expect(readLanguage(storage)).toBe('ru')
    })
  })

  it('keeps Cyrillic out of Uzbek messages', () => {
    for (const [key, value] of Object.entries(uz)) {
      expect(value, key).not.toMatch(/[\u0400-\u04ff]/)
    }
  })

  it('keeps Uzbek glossary terms out of Russian messages with no exceptions', () => {
    expect(ruUzbekExceptions).toEqual([])
    for (const [key, value] of Object.entries(ru)) {
      for (const word of forbiddenUzbekWords) {
        expect(value.toLocaleLowerCase(), `${key} contains ${word}`).not.toContain(word)
      }
    }
  })

  it('falls back to Uzbek text without exposing the key', () => {
    const catalogs = {
      uz: { greeting: 'Salom' },
      ru: {},
    }
    expect(resolveMessage('greeting', 'ru', catalogs)).toBe('Salom')
    expect(resolveMessage('missing.key', 'ru', catalogs)).toBe('Tarjima mavjud emas.')
    expect(resolveMessage('missing.key', 'ru', catalogs)).not.toContain('missing.key')
  })

  it('translates known server errors by their stable Uzbek message', () => {
    expect(translateServerError('Telefon raqami yoki parol noto‘g‘ri.', 'ru'))
      .toBe('Неверный номер телефона или пароль.')
    expect(translateServerError('Unmapped server response', 'ru')).toBeUndefined()
  })
})

describe('shared display formats', () => {
  it.each(['uz', 'ru'] as const)('formats dates as DD.MM.YYYY for %s', (language) => {
    expect(formatDate('2026-10-30', language)).toBe('30.10.2026')
    expect(formatDate('not-a-date', language)).toBe(language === 'ru' ? ru['format.invalidDate'] : uz['format.invalidDate'])
  })

  it.each(['uz', 'ru'] as const)('formats money with a localized unit for %s', (language) => {
    const formatted = formatMoney(1234.5, language)
    expect(formatted).toMatch(/1[\s\u00a0\u202f]234,50/)
    expect(formatted.endsWith(language === 'ru' ? ' сум' : ' so‘m')).toBe(true)
  })
})
