import React, { useEffect, useRef, useState } from 'react'
import { useTheme } from './useTheme'

interface StickmanThemeToggleProps {
  className?: string
}

type StickmanState = 'day' | 'to_night' | 'night' | 'night_peek' | 'to_day'

export const StickmanThemeToggle: React.FC<StickmanThemeToggleProps> = ({ className = '' }) => {
  const { isDark, toggleTheme } = useTheme()
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  const isDarkRef = useRef(isDark)
  isDarkRef.current = isDark

  const stateRef = useRef<StickmanState>(isDark ? 'night' : 'day')
  const progressRef = useRef(0)
  const isAnimatingRef = useRef(false)
  const isHoveredRef = useRef(false)
  const [isHovered, setIsHovered] = useState(false)

  // Tashqi theme o'zgarishini kuzatish
  const prevIsDark = useRef(isDark)
  useEffect(() => {
    if (prevIsDark.current !== isDark) {
      prevIsDark.current = isDark
      if (!isAnimatingRef.current) {
        stateRef.current = isDark ? 'night' : 'day'
        progressRef.current = 0
      }
    }
  }, [isDark])

  // Tunda har 5 sekundda poylab (peek) turish
  useEffect(() => {
    const timer = setInterval(() => {
      if (isDarkRef.current && stateRef.current === 'night' && !isAnimatingRef.current) {
        stateRef.current = 'night_peek'
        progressRef.current = 0
      }
    }, 5000)
    return () => clearInterval(timer)
  }, [])

  // Bosilganda xavfsiz va aniq almashtirish
  const handleToggle = () => {
    if (isAnimatingRef.current) return // animatsiya ketayotganda qayta bosishni bloklash

    if (!isDarkRef.current) {
      // Kunduzdan tunga: bolacha teshikka sakraydi
      isAnimatingRef.current = true
      stateRef.current = 'to_night'
      progressRef.current = 0
    } else {
      // Tundan kunduzga: bolacha chuqurdan sakrab chiqadi va quyosh sari boradi
      isAnimatingRef.current = true
      stateRef.current = 'to_day'
      progressRef.current = 0
      // Quyosh darhol yoki sakrash boshida chiqadi
      toggleTheme()
    }
  }

  // Yagona uzluksiz 60FPS render loop
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let animId: number
    let lastTime = performance.now()
    let sunRaysAngle = 0

    const render = (time: number) => {
      const dt = Math.min((time - lastTime) / 1000, 0.05)
      lastTime = time

      const w = 116
      const h = 36
      const groundY = 26
      const holeX = 92
      const sunX = 20
      const sunY = h / 2
      const currentDark = isDarkRef.current

      // Retina / HiDPI
      const dpr = window.devicePixelRatio || 1
      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr
        canvas.height = h * dpr
      }

      ctx.save()
      ctx.scale(dpr, dpr)
      ctx.clearRect(0, 0, w, h)

      // 1. Kapsula (Toggle fon)
      ctx.beginPath()
      ctx.roundRect(1, 1, w - 2, h - 2, (h - 2) / 2)
      ctx.fillStyle = currentDark ? '#1a2424' : '#f8fafc'
      ctx.fill()
      ctx.lineWidth = 1.2
      ctx.strokeStyle = isHoveredRef.current
        ? (currentDark ? '#63d9b8' : '#087f68')
        : (currentDark ? '#2e3e3c' : '#cbd5e1')
      ctx.stroke()

      // 2. Teshik (Hole)
      ctx.save()
      ctx.beginPath()
      ctx.ellipse(holeX, groundY + 1.5, 11, 4, 0, 0, Math.PI * 2)
      ctx.fillStyle = currentDark ? '#0d1312' : '#94a3b8'
      ctx.fill()
      ctx.lineWidth = 1
      ctx.strokeStyle = currentDark ? '#243130' : '#cbd5e1'
      ctx.stroke()
      ctx.restore()

      // 3. Quyosh / Oy
      if (!currentDark) {
        // Quyoshcha
        sunRaysAngle += dt * 1.5
        ctx.save()
        ctx.translate(sunX, sunY)

        ctx.strokeStyle = '#f59e0b'
        ctx.lineWidth = 1.6
        ctx.lineCap = 'round'
        for (let i = 0; i < 8; i++) {
          const angle = sunRaysAngle + (i * Math.PI) / 4
          const x1 = Math.cos(angle) * 8.5
          const y1 = Math.sin(angle) * 8.5
          const x2 = Math.cos(angle) * 11.5
          const y2 = Math.sin(angle) * 11.5
          ctx.beginPath()
          ctx.moveTo(x1, y1)
          ctx.lineTo(x2, y2)
          ctx.stroke()
        }

        ctx.beginPath()
        ctx.arc(0, 0, 6.2, 0, Math.PI * 2)
        ctx.fillStyle = '#f59e0b'
        ctx.fill()
        ctx.restore()
      } else {
        // Oy
        ctx.save()
        ctx.translate(sunX, sunY)
        ctx.fillStyle = '#38bdf8'
        ctx.beginPath()
        ctx.arc(0, 0, 6.8, -Math.PI / 2, Math.PI / 2, false)
        ctx.bezierCurveTo(-2, 4.5, -2, -4.5, 0, -6.8)
        ctx.closePath()
        ctx.fill()

        ctx.fillStyle = '#7dd3fc'
        ctx.beginPath()
        ctx.arc(8, -5, 1, 0, Math.PI * 2)
        ctx.fill()
        ctx.beginPath()
        ctx.arc(9, 6, 0.8, 0, Math.PI * 2)
        ctx.fill()
        ctx.restore()
      }

      // 4. Holat mashinasi va progress
      const state = stateRef.current
      progressRef.current += dt

      let stickmanX = 54
      let stickmanY = groundY
      let stickmanScale = 1
      let stickmanOpacity = 1
      let armAngle = 0
      let legSpread = 0.2
      let isVisible = true

      if (state === 'day') {
        stickmanX = 54
        stickmanY = groundY
        stickmanScale = 1
        stickmanOpacity = 1
        armAngle = Math.sin(time * 0.003) * 0.15
        legSpread = 0.2 + Math.sin(time * 0.002) * 0.05
      } else if (state === 'to_night') {
        // 0.5 soniyada teshikka sakrab tushadi
        const duration = 0.55
        const p = Math.min(progressRef.current / duration, 1)

        stickmanX = 54 + (holeX - 54) * p
        const jumpArc = Math.sin(p * Math.PI) * 16
        stickmanY = groundY - jumpArc + p * 3.5
        stickmanScale = Math.max(0, 1 - p * 0.8)
        stickmanOpacity = Math.max(0, 1 - p * 0.95)
        armAngle = p * Math.PI * 1.5
        legSpread = 0.6

        if (p >= 1) {
          stateRef.current = 'night'
          isAnimatingRef.current = false
          progressRef.current = 0
          toggleTheme() // Teshikka tushib bo'lgach tun bo'ladi
        }
      } else if (state === 'night') {
        isVisible = false
      } else if (state === 'night_peek') {
        // Teshikdan sakrab mo'ralaydi (0.7 soniya)
        const duration = 0.7
        const p = Math.min(progressRef.current / duration, 1)
        isVisible = true

        const peekArc = Math.sin(p * Math.PI)
        stickmanX = holeX
        stickmanY = groundY + 4 - peekArc * 12
        stickmanScale = 0.85
        stickmanOpacity = peekArc
        armAngle = Math.sin(p * Math.PI * 2) * 0.4
        legSpread = 0.1

        if (p >= 1) {
          stateRef.current = 'night'
          progressRef.current = 0
        }
      } else if (state === 'to_day') {
        // Chuqurdan chiqib quyoshcha tomon yuguradi va singib ketadi (1.4 soniya)
        const totalDuration = 1.3
        const p = Math.min(progressRef.current / totalDuration, 1)
        isVisible = true

        if (p < 0.35) {
          // Chuqurdan sakrab chiqish (0 -> 0.35)
          const jumpP = p / 0.35
          stickmanX = holeX - (holeX - 62) * jumpP
          stickmanY = groundY - Math.sin(jumpP * Math.PI) * 15
          stickmanScale = Math.min(1, 0.4 + jumpP * 0.6)
          stickmanOpacity = Math.min(1, jumpP * 2)
          armAngle = -0.4
          legSpread = 0.4
        } else if (p < 0.75) {
          // Quyoshcha tomon yugurish (0.35 -> 0.75)
          const runP = (p - 0.35) / 0.4
          stickmanX = 62 - (62 - (sunX + 6)) * runP
          stickmanY = groundY
          armAngle = Math.sin(runP * Math.PI * 8) * 0.7
          legSpread = Math.sin(runP * Math.PI * 8) * 0.5
          stickmanOpacity = 1
          stickmanScale = 1
        } else {
          // Quyoshcha oldida yo'q bo'lib/singib ketish va markazda paydo bo'lish (0.75 -> 1.0)
          const fadeP = (p - 0.75) / 0.25
          if (fadeP < 0.5) {
            // Quyoshga singib yo'q bo'ladi
            stickmanX = sunX + 6
            stickmanY = groundY
            stickmanOpacity = Math.max(0, 1 - fadeP * 2)
            stickmanScale = Math.max(0, 1 - fadeP)
          } else {
            // Kunduzgi joyida (x=54) mayin paydo bo'ladi
            const appearP = (fadeP - 0.5) / 0.5
            stickmanX = 54
            stickmanY = groundY
            stickmanOpacity = appearP
            stickmanScale = 0.5 + appearP * 0.5
          }
        }

        if (p >= 1) {
          stateRef.current = 'day'
          isAnimatingRef.current = false
          progressRef.current = 0
        }
      }

      // 5. Stickmanni chizish
      if (isVisible && stickmanOpacity > 0.02) {
        ctx.save()
        ctx.globalAlpha = Math.min(1, Math.max(0, stickmanOpacity))
        ctx.translate(stickmanX, stickmanY)
        ctx.scale(stickmanScale, stickmanScale)

        const strokeColor = currentDark ? '#ffffff' : '#0f172a'
        ctx.strokeStyle = strokeColor
        ctx.fillStyle = strokeColor
        ctx.lineWidth = 1.3
        ctx.lineCap = 'round'
        ctx.lineJoin = 'round'

        // Bosh (Head)
        ctx.beginPath()
        ctx.arc(0, -15, 3.2, 0, Math.PI * 2)
        ctx.fill()

        // Tana (Spine)
        ctx.beginPath()
        ctx.moveTo(0, -12)
        ctx.lineTo(0, -5)
        ctx.stroke()

        // Qo'llar (Arms)
        ctx.beginPath()
        ctx.moveTo(0, -10)
        ctx.lineTo(-4 * Math.cos(armAngle), -10 - 4 * Math.sin(armAngle))
        ctx.moveTo(0, -10)
        ctx.lineTo(4 * Math.cos(armAngle), -10 + 4 * Math.sin(armAngle))
        ctx.stroke()

        // Oyoqlar (Legs)
        ctx.beginPath()
        ctx.moveTo(0, -5)
        ctx.lineTo(-3 - legSpread * 3, 0)
        ctx.moveTo(0, -5)
        ctx.lineTo(3 + legSpread * 3, 0)
        ctx.stroke()

        ctx.restore()
      }

      ctx.restore()
      animId = requestAnimationFrame(render)
    }

    animId = requestAnimationFrame(render)
    return () => cancelAnimationFrame(animId)
  }, []) // Yagona uzluksiz loop

  return (
    <button
      type="button"
      onClick={handleToggle}
      onMouseEnter={() => {
        isHoveredRef.current = true
        setIsHovered(true)
      }}
      onMouseLeave={() => {
        isHoveredRef.current = false
        setIsHovered(false)
      }}
      className={`stickman-theme-toggle ${className}`}
      aria-label={isDark ? 'Yorug‘ rejimga o‘tish' : 'Qorong‘i rejimga o‘tish'}
      title={isDark ? 'Yorug‘ rejim (Bolakay quyosh sari chiqadi)' : 'Qorong‘i rejim (Bolakay chuqurga sakraydi)'}
      style={{
        background: 'transparent',
        border: 'none',
        padding: 0,
        margin: 0,
        cursor: 'pointer',
        display: 'inline-flex',
        alignItems: 'center',
        verticalAlign: 'middle',
        boxShadow: 'none',
        outline: 'none',
      }}
    >
      <canvas
        ref={canvasRef}
        style={{
          width: 116,
          height: 36,
          display: 'block',
          borderRadius: 18,
          boxShadow: isHovered
            ? (isDark ? '0 0 12px rgba(99, 217, 184, 0.25)' : '0 2px 8px rgba(0, 0, 0, 0.12)')
            : '0 1px 2px rgba(0, 0, 0, 0.05)',
          transition: 'box-shadow 0.2s ease',
        }}
      />
    </button>
  )
}
export default StickmanThemeToggle
