import { Check, Copy, Phone } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from './i18n/useTranslation'
import './ContactMenu.css'

type Contact = { id: number; name: string; phone: string }

const texts = {
  uz: { button: 'Aloqa', call: 'Qo‘ng‘iroq qilish', copy: 'Nusxalash', copied: 'Nusxalandi' },
  ru: { button: 'Связаться', call: 'Позвонить', copy: 'Копировать', copied: 'Скопировано' },
}

function prettyPhone(phone: string) {
  const match = phone.replace(/\D/g, '').match(/^998(\d{2})(\d{3})(\d{2})(\d{2})$/)
  return match ? `+998 ${match[1]} ${match[2]} ${match[3]} ${match[4]}` : phone
}

/** "Aloqa" tugmasi: bosilganda hamkor kompaniyalar raqamlari ko‘rinadi (kompyuterda ham ishlaydi). */
export function ContactMenu({ contacts }: { contacts: Contact[] }) {
  const { language } = useTranslation()
  const text = texts[language]
  const [open, setOpen] = useState(false)
  const [copiedId, setCopiedId] = useState<number | null>(null)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  const withPhone = contacts.filter((contact) => contact.phone)
  if (withPhone.length === 0) return null

  const copyPhone = async (contact: Contact) => {
    try {
      await navigator.clipboard.writeText(contact.phone)
      setCopiedId(contact.id)
    } catch {
      // Nusxalashga ruxsat bo‘lmasa, raqam ekranda ko‘rinib turadi.
      setCopiedId(null)
    }
  }

  return (
    <div className="contact-menu" ref={rootRef}>
      <button
        type="button"
        className="shop-help-link"
        aria-expanded={open}
        aria-label={text.button}
        onClick={() => { setOpen((value) => !value); setCopiedId(null) }}
      >
        <Phone size={16} />{text.button}
      </button>
      {open && (
        <div className="contact-menu-panel">
          {withPhone.map((contact) => (
            <div className="contact-menu-item" key={contact.id}>
              <small>{contact.name}</small>
              <strong>{prettyPhone(contact.phone)}</strong>
              <div className="contact-menu-actions">
                <a href={`tel:${contact.phone}`}><Phone size={14} />{text.call}</a>
                <button type="button" onClick={() => void copyPhone(contact)}>
                  {copiedId === contact.id ? <Check size={14} /> : <Copy size={14} />}
                  {copiedId === contact.id ? text.copied : text.copy}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
