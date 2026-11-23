import { useEffect, useRef, useState } from 'react'
import { CalendarDays, ChevronDown, ChevronLeft, ChevronRight } from 'lucide-react'
import { useTranslation } from './i18n/useTranslation'
import './ShopDatePicker.css'

type ShopDatePickerProps = {
  /** 'YYYY-MM-DD' yoki '' */
  value: string
  onChange: (value: string) => void
  /** Eng erta tanlash mumkin bo‘lgan sana ('YYYY-MM-DD') */
  min?: string
  /** Eng kech tanlash mumkin bo‘lgan sana ('YYYY-MM-DD') */
  max?: string
  placeholder?: string
  ariaLabel?: string
}

const POPOVER_WIDTH = 292

const MONTHS = {
  uz: ['Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun', 'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr'],
  ru: ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'],
}

const WEEKDAYS = {
  uz: ['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'],
  ru: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
}

const TEXT = {
  uz: { placeholder: 'Sanani tanlang', today: 'Bugun', tomorrow: 'Ertaga', prev: 'Oldingi oy', next: 'Keyingi oy' },
  ru: { placeholder: 'Выберите дату', today: 'Сегодня', tomorrow: 'Завтра', prev: 'Предыдущий месяц', next: 'Следующий месяц' },
}

function pad(value: number) {
  return String(value).padStart(2, '0')
}

function toIso(year: number, month: number, day: number) {
  return `${year}-${pad(month + 1)}-${pad(day)}`
}

function parseIso(value?: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value ?? '')
  if (!match) return null
  return { year: Number(match[1]), month: Number(match[2]) - 1, day: Number(match[3]) }
}

function isoInDays(days: number) {
  const date = new Date()
  date.setDate(date.getDate() + days)
  return toIso(date.getFullYear(), date.getMonth(), date.getDate())
}

function viewFor(value?: string, min?: string) {
  const base = parseIso(value) ?? parseIso(min) ?? parseIso(isoInDays(0))!
  return { year: base.year, month: base.month }
}

export default function ShopDatePicker({ value, onChange, min, max, placeholder, ariaLabel }: ShopDatePickerProps) {
  const { language } = useTranslation()
  const lang = language === 'ru' ? 'ru' : 'uz'
  const text = TEXT[lang]
  const rootRef = useRef<HTMLDivElement | null>(null)
  const triggerRef = useRef<HTMLButtonElement | null>(null)
  const [open, setOpen] = useState(false)
  const [alignRight, setAlignRight] = useState(false)
  const [view, setView] = useState(() => viewFor(value, min))

  useEffect(() => {
    if (!open) return
    const onPointerDown = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false)
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false)
        triggerRef.current?.focus()
      }
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  const isDisabled = (iso: string) => Boolean((min && iso < min) || (max && iso > max))

  const toggle = () => {
    if (!open) {
      setView(viewFor(value, min))
      // Ekran o‘ng chetiga yaqin bo‘lsa, kalendarni o‘ngga tekislaymiz
      const rect = rootRef.current?.getBoundingClientRect()
      setAlignRight(Boolean(rect && rect.left + POPOVER_WIDTH > window.innerWidth - 8 && rect.right - POPOVER_WIDTH >= 8))
    }
    setOpen((current) => !current)
  }

  const select = (iso: string) => {
    if (isDisabled(iso)) return
    onChange(iso)
    setOpen(false)
    triggerRef.current?.focus()
  }

  const { year, month } = view
  const offset = (new Date(year, month, 1).getDay() + 6) % 7 // Dushanba — birinchi kun
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const prevMonthEnd = toIso(month === 0 ? year - 1 : year, month === 0 ? 11 : month - 1, new Date(year, month, 0).getDate())
  const nextMonthStart = toIso(month === 11 ? year + 1 : year, month === 11 ? 0 : month + 1, 1)
  const prevBlocked = Boolean(min && prevMonthEnd < min)
  const nextBlocked = Boolean(max && nextMonthStart > max)
  const todayIso = isoInDays(0)
  const tomorrowIso = isoInDays(1)

  const goPrev = () => setView(month === 0 ? { year: year - 1, month: 11 } : { year, month: month - 1 })
  const goNext = () => setView(month === 11 ? { year: year + 1, month: 0 } : { year, month: month + 1 })

  const parsed = parseIso(value)
  const display = parsed ? `${pad(parsed.day)}.${pad(parsed.month + 1)}.${parsed.year}` : ''

  return (
    // preventDefault: <label> ichida ishlatilganda, kalendarning bo‘sh joyiga bosish uni yopib qo‘ymasligi uchun
    <div className="shop-datepicker" ref={rootRef} onClick={(event) => event.preventDefault()}>
      <button
        ref={triggerRef}
        type="button"
        className={`sdp-trigger ${open ? 'is-open' : ''}`}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={ariaLabel}
        onClick={toggle}
      >
        <CalendarDays size={16} className="sdp-trigger-icon" />
        <span className={display ? '' : 'sdp-placeholder'}>{display || placeholder || text.placeholder}</span>
        <ChevronDown size={15} className="sdp-trigger-chevron" />
      </button>

      {open && (
        <div className={`sdp-popover${alignRight ? ' is-right' : ''}`} role="dialog" aria-label={`${MONTHS[lang][month]} ${year}`}>
          <div className="sdp-header">
            <strong className="sdp-title">{MONTHS[lang][month]} {year}</strong>
            <div className="sdp-nav-group">
              <button type="button" className="sdp-nav" onClick={goPrev} disabled={prevBlocked} aria-label={text.prev} title={text.prev}>
                <ChevronLeft size={17} />
              </button>
              <button type="button" className="sdp-nav" onClick={goNext} disabled={nextBlocked} aria-label={text.next} title={text.next}>
                <ChevronRight size={17} />
              </button>
            </div>
          </div>

          <div className="sdp-weekdays" aria-hidden="true">
            {WEEKDAYS[lang].map((name) => <span key={name}>{name}</span>)}
          </div>

          <div className="sdp-days">
            {Array.from({ length: offset }).map((_, index) => <span key={`gap-${index}`} className="sdp-gap" />)}
            {Array.from({ length: daysInMonth }).map((_, index) => {
              const day = index + 1
              const iso = toIso(year, month, day)
              const classes = ['sdp-day']
              if (iso === value) classes.push('is-selected')
              if (iso === todayIso) classes.push('is-today')
              return (
                <button
                  key={iso}
                  type="button"
                  className={classes.join(' ')}
                  disabled={isDisabled(iso)}
                  aria-pressed={iso === value}
                  onClick={() => select(iso)}
                >
                  {day}
                </button>
              )
            })}
          </div>

          <div className="sdp-footer">
            <button type="button" className="sdp-action" disabled={isDisabled(todayIso)} onClick={() => select(todayIso)}>{text.today}</button>
            <button type="button" className="sdp-action is-accent" disabled={isDisabled(tomorrowIso)} onClick={() => select(tomorrowIso)}>{text.tomorrow}</button>
          </div>
        </div>
      )}
    </div>
  )
}
