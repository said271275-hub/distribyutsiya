import { Moon, Sun } from 'lucide-react'
import { useTheme } from './useTheme'
import './SimpleThemeToggle.css'

/** Kun/tun almashtirgich: sirpanadigan doira tanlangan rejim belgisi ostida turadi. */
export function SimpleThemeToggle({ className = '' }: { className?: string }) {
  const { isDark, toggleTheme } = useTheme()
  const label = isDark ? 'Kun rejimiga o‘tish' : 'Tun rejimiga o‘tish'
  return (
    <button
      type="button"
      role="switch"
      aria-checked={isDark}
      className={`simple-theme-toggle${isDark ? ' is-dark' : ''} ${className}`.trim()}
      onClick={toggleTheme}
      aria-label={label}
      title={label}
    >
      <span className="simple-theme-thumb" aria-hidden="true" />
      <span className={`simple-theme-icon${isDark ? '' : ' is-active'}`} aria-hidden="true"><Sun size={17} strokeWidth={2} /></span>
      <span className={`simple-theme-icon${isDark ? ' is-active' : ''}`} aria-hidden="true"><Moon size={17} strokeWidth={2} /></span>
    </button>
  )
}
