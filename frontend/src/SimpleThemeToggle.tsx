import { Moon, Sun } from 'lucide-react'
import { useTheme } from './useTheme'
import './SimpleThemeToggle.css'

/** Oddiy kun/tun tugmasi: kunda oy, tunda quyosh belgisi ko'rsatiladi (bosilganda shunga o'tadi). */
export function SimpleThemeToggle({ className = '' }: { className?: string }) {
  const { isDark, toggleTheme } = useTheme()
  const label = isDark ? 'Kun rejimiga o‘tish' : 'Tun rejimiga o‘tish'
  return (
    <button
      type="button"
      className={`simple-theme-toggle ${className}`.trim()}
      onClick={toggleTheme}
      aria-label={label}
      title={label}
    >
      {isDark ? <Sun size={18} strokeWidth={1.9} /> : <Moon size={18} strokeWidth={1.9} />}
    </button>
  )
}
