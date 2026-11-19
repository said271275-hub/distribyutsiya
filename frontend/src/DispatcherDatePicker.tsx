import React, { useState, useRef, useEffect } from 'react'
import { Calendar as CalendarIcon, ChevronLeft, ChevronRight, X } from 'lucide-react'

interface DispatcherDatePickerProps {
  value: string // 'YYYY-MM-DD' yoki ''
  onChange: (value: string) => void
  placeholder?: string
  className?: string
}

const MONTH_NAMES = [
  'Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun',
  'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr'
]

const WEEKDAY_NAMES = ['Dsh', 'Ssh', 'Chsh', 'Pay', 'Jum', 'Shn', 'Yak']

export const DispatcherDatePicker: React.FC<DispatcherDatePickerProps> = ({
  value,
  onChange,
  placeholder = 'Sanani tanlang',
  className = '',
}) => {
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement | null>(null)

  // Ichki ko'rsatilayotgan oy/yil
  const initialDate = value ? new Date(value) : new Date()
  const [viewYear, setViewYear] = useState(() => (isNaN(initialDate.getTime()) ? new Date().getFullYear() : initialDate.getFullYear()))
  const [viewMonth, setViewMonth] = useState(() => (isNaN(initialDate.getTime()) ? new Date().getMonth() : initialDate.getMonth()))

  // Agar value tashqaridan o'zgarsa, viewYear/viewMonth ni yangilash
  useEffect(() => {
    if (value) {
      const d = new Date(value)
      if (!isNaN(d.getTime())) {
        setViewYear(d.getFullYear())
        setViewMonth(d.getMonth())
      }
    }
  }, [value])

  // Tashqariga bosilganda popoverni yopish
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleOutsideClick)
    }
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick)
    }
  }, [isOpen])

  // Oy o'tkazish
  const handlePrevMonth = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (viewMonth === 0) {
      setViewMonth(11)
      setViewYear((y) => y - 1)
    } else {
      setViewMonth((m) => m - 1)
    }
  }

  const handleNextMonth = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (viewMonth === 11) {
      setViewMonth(0)
      setViewYear((y) => y + 1)
    } else {
      setViewMonth((m) => m + 1)
    }
  }

  // Sanani tanlash
  const handleSelectDay = (year: number, month: number, day: number) => {
    const mStr = String(month + 1).padStart(2, '0')
    const dStr = String(day).padStart(2, '0')
    onChange(`${year}-${mStr}-${dStr}`)
    setIsOpen(false)
  }

  // Bugungi sana
  const handleSelectToday = (e: React.MouseEvent) => {
    e.stopPropagation()
    const now = new Date()
    const y = now.getFullYear()
    const m = String(now.getMonth() + 1).padStart(2, '0')
    const d = String(now.getDate()).padStart(2, '0')
    onChange(`${y}-${m}-${d}`)
    setIsOpen(false)
  }

  // Tozalash
  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation()
    onChange('')
    setIsOpen(false)
  }

  // Kalendar kunlari hisob-kitobi
  const firstDayOfMonth = new Date(viewYear, viewMonth, 1)
  // 0: Yakshanba -> 6 (Yak), 1: Dushanba -> 0 (Dsh)
  const startingDayIndex = (firstDayOfMonth.getDay() + 6) % 7
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate()
  const daysInPrevMonth = new Date(viewYear, viewMonth, 0).getDate()

  // Formatlangan ko'rinish
  let formattedDisplay = ''
  if (value) {
    const [y, m, d] = value.split('-').map(Number)
    if (y && m && d) {
      formattedDisplay = `${String(d).padStart(2, '0')}.${String(m).padStart(2, '0')}.${y}`
    }
  }

  const today = new Date()
  const todayY = today.getFullYear()
  const todayM = today.getMonth()
  const todayD = today.getDate()

  return (
    <div className={`dispatcher-date-picker-wrap ${className}`} ref={containerRef}>
      <button
        type="button"
        className={`dispatcher-date-input-btn ${isOpen ? 'is-focused' : ''}`}
        onClick={() => setIsOpen((prev) => !prev)}
      >
        <CalendarIcon size={16} className="dispatcher-date-input-icon" />
        <span className={`dispatcher-date-input-text ${!formattedDisplay ? 'is-placeholder' : ''}`}>
          {formattedDisplay || placeholder}
        </span>
        {value && (
          <span
            className="dispatcher-date-input-clear"
            onClick={handleClear}
            title="Tozalash"
            role="button"
          >
            <X size={13} />
          </span>
        )}
      </button>

      {isOpen && (
        <div className="dispatcher-calendar-popover" role="dialog">
          {/* Header */}
          <div className="dispatcher-calendar-header">
            <span className="dispatcher-calendar-title">
              {MONTH_NAMES[viewMonth]} {viewYear}
            </span>
            <div className="dispatcher-calendar-nav">
              <button
                type="button"
                className="dispatcher-calendar-nav-btn"
                onClick={handlePrevMonth}
                title="Oldingi oy"
              >
                <ChevronLeft size={16} />
              </button>
              <button
                type="button"
                className="dispatcher-calendar-nav-btn"
                onClick={handleNextMonth}
                title="Keyingi oy"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>

          {/* Hafta kunlari sarlavhasi */}
          <div className="dispatcher-calendar-weekdays">
            {WEEKDAY_NAMES.map((name) => (
              <span key={name} className="dispatcher-calendar-weekday">
                {name}
              </span>
            ))}
          </div>

          {/* Kunlar to'ri */}
          <div className="dispatcher-calendar-days">
            {/* Oldingi oydan to'ldirish */}
            {Array.from({ length: startingDayIndex }).map((_, i) => {
              const dayNum = daysInPrevMonth - startingDayIndex + 1 + i
              return (
                <button
                  key={`prev-${i}`}
                  type="button"
                  className="dispatcher-calendar-day is-outside"
                  onClick={() => {
                    if (viewMonth === 0) {
                      handleSelectDay(viewYear - 1, 11, dayNum)
                    } else {
                      handleSelectDay(viewYear, viewMonth - 1, dayNum)
                    }
                  }}
                >
                  {dayNum}
                </button>
              )
            })}

            {/* Joriy oy kunlari */}
            {Array.from({ length: daysInMonth }).map((_, i) => {
              const dayNum = i + 1
              const dateStr = `${viewYear}-${String(viewMonth + 1).padStart(2, '0')}-${String(dayNum).padStart(2, '0')}`
              const isSelected = value === dateStr
              const isToday = viewYear === todayY && viewMonth === todayM && dayNum === todayD

              return (
                <button
                  key={`cur-${dayNum}`}
                  type="button"
                  className={`dispatcher-calendar-day ${isSelected ? 'is-selected' : ''} ${isToday ? 'is-today' : ''}`}
                  onClick={() => handleSelectDay(viewYear, viewMonth, dayNum)}
                >
                  {dayNum}
                </button>
              )
            })}
          </div>

          {/* Footer amallar */}
          <div className="dispatcher-calendar-footer">
            <button
              type="button"
              className="dispatcher-calendar-action-btn"
              onClick={handleClear}
            >
              Tozalash
            </button>
            <button
              type="button"
              className="dispatcher-calendar-action-btn is-accent"
              onClick={handleSelectToday}
            >
              Bugun
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
export default DispatcherDatePicker
