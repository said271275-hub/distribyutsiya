import { useTranslation } from './useTranslation'

export function LanguageSelect() {
  const { language, setLanguage, t } = useTranslation()
  return (
    <label className="language-select">
      <span className="sr-only">{t('language.select')}</span>
      <select
        aria-label={t('language.select')}
        value={language}
        onChange={(event) => {
          const value = event.target.value
          if (value === 'uz' || value === 'ru') setLanguage(value)
        }}
      >
        <option value="uz">{t('language.uz')}</option>
        <option value="ru">{t('language.ru')}</option>
      </select>
    </label>
  )
}
