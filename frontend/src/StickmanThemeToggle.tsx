import React, { useEffect, useRef, useState } from 'react'
import { useTheme } from './useTheme'

interface StickmanThemeToggleProps {
  className?: string
}

export const StickmanThemeToggle: React.FC<StickmanThemeToggleProps> = ({ className = '' }) => {
  const { isDark, toggleTheme } = useTheme()
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  // Holatlar:
  // 'day_idle': kunduzi erkin turadi
  // 'jump_into_hole': teshikka sakrab tushadi va tun bo'ladi
  // 'night_hidden': chuqur ichida yotadi
  // 'night_peek': har 5 sekundda chuqurdan boshini chiqarib sakrab poylaydi va qaytib tushadi
  // 'jump_out_to_sun': chuqurdan sakrab chiqib quyoshcha oldiga boradi va yo'q bo'lib/singib ketadi
  const stateRef = useRef<'day_idle' | 'jump_into_hole' | 'night_hidden' | 'night_peek' | 'jump_out_to_sun'>(
    isDark ? 'night_hidden' : 'day_idle'
  )
  const animProgressRef = useRef(0)
  const prevIsDarkRef = useRef(isDark)
  const isHoveredRef = useRef(false)
  const [isHovered, setIsHovered] = useState(false)

  // Tunda har 5 sekundda poylab (peek) turish taymeri
  useEffect(() => {
    let peekTimer: ReturnType<typeof setTimeout>
    if (isDark) {
      const schedulePeek = () => {
        peekTimer = setTimeout(() => {
          if (stateRef.current === 'night_hidden') {
            stateRef.current = 'night_peek'
            animProgressRef.current = 0
          }
          schedulePeek()
        }, 5000)
      }
      schedulePeek()
    }
    return () => clearTimeout(peekTimer)
  }, [isDark])

  // Foydalanuvchi bosganda holatni o'zgartirish
  const handleToggle = () => {
    if (!isDark) {
      // Kunduzdan tunga: bolacha teshikka sakrab tushadi, so'ng tun bo'ladi
      stateRef.current = 'jump_into_hole'
      animProgressRef.current = 0
      setTimeout(() => {
        toggleTheme()
      }, 350)
    } else {
      // Tundan kunduzga: qaytib chiqib quyoshcha oldiga boradi
      stateRef.current = 'jump_out_to_sun'
      animProgressRef.current = 0
      toggleTheme()
    }
  }

  // Tashqi theme o'zgarishini kuzatish (agar boshqa joydan o'zgarsa)
  useEffect(() => {
    if (prevIsDarkRef.current !== isDark) {
      if (isDark && stateRef.current !== 'jump_into_hole') {
        stateRef.current = 'night_hidden'
      } else if (!isDark && stateRef.current !== 'jump_out_to_sun') {
        stateRef.current = 'day_idle'
      }
      prevIsDarkRef.current = isDark
    }
  }, [isDark])

  // Canvas render loop (60 FPS)
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let animId: number
    let lastTime = performance.now()
    let sunRaysAngle = 0

    const render = (time: number) => {
      const dt = Math.min((time - lastTime) / 1000, 0.1)
      lastTime = time

      const w = 116
      const h = 36
      const groundY = 26
      const holeX = 90
      const sunX = 20
      const sunY = h / 2

      // HiDPI / Retina moslashuv
      const dpr = window.devicePixelRatio || 1
      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr
        canvas.height = h * dpr
      }

      ctx.save()
      ctx.scale(dpr, dpr)
      ctx.clearRect(0, 0, w, h)

      // 1. Kapsula (Toggle fon va chegara)
      ctx.beginPath()
      ctx.roundRect(1, 1, w - 2, h - 2, (h - 2) / 2)
      ctx.fillStyle = isDark ? '#1a2424' : '#f8fafc'
      ctx.fill()
      ctx.lineWidth = 1.2
      ctx.strokeStyle = isHoveredRef.current
        ? (isDark ? '#63d9b8' : '#087f68')
        : (isDark ? '#2e3e3c' : '#cbd5e1')
      ctx.stroke()

      // 2. Teshik (Hole / Chuqur)
      ctx.save()
      ctx.beginPath()
      ctx.ellipse(holeX, groundY + 1.5, 11, 4, 0, 0, Math.PI * 2)
      ctx.fillStyle = isDark ? '#0d1312' : '#94a3b8'
      ctx.fill()
      ctx.lineWidth = 1
      ctx.strokeStyle = isDark ? '#243130' : '#cbd5e1'
      ctx.stroke()
      ctx.restore()

      // 3. Quyosh / Oy
      if (!isDark) {
        // Quyoshcha (☀️)
        sunRaysAngle += dt * 1.5
        ctx.save()
        ctx.translate(sunX, sunY)

        // Nurlar
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

        // Quyosh diski
        ctx.beginPath()
        ctx.arc(0, 0, 6.2, 0, Math.PI * 2)
        ctx.fillStyle = '#f59e0b'
        ctx.fill()
        ctx.restore()
      } else {
        // Oy (🌙)
        ctx.save()
        ctx.translate(sunX, sunY)
        ctx.fillStyle = '#38bdf8'
        ctx.beginPath()
        ctx.arc(0, 0, 6.8, -Math.PI / 2, Math.PI / 2, false)
        ctx.bezierCurveTo(-2, 4.5, -2, -4.5, 0, -6.8)
        ctx.closePath()
        ctx.fill()

        // Yulduzchalar
        ctx.fillStyle = '#7dd3fc'
        ctx.beginPath()
        ctx.arc(8, -5, 1, 0, Math.PI * 2)
        ctx.fill()
        ctx.beginPath()
        ctx.arc(9, 6, 0.8, 0, Math.PI * 2)
        ctx.fill()
        ctx.restore()
      }

      // 4. Holat va progress
      const state = stateRef.current

      if (state === 'jump_into_hole') {
        animProgressRef.current += dt * 2.2
        if (animProgressRef.current >= 1) {
          animProgressRef.current = 1
          stateRef.current = 'night_hidden'
        }
      } else if (state === 'night_peek') {
        animProgressRef.current += dt * 1.4
        if (animProgressRef.current >= 1) {
          animProgressRef.current = 0
          stateRef.current = 'night_hidden'
        }
      } else if (state === 'jump_out_to_sun') {
        animProgressRef.current += dt * 1.2
        if (animProgressRef.current >= 1) {
          animProgressRef.current = 1
          stateRef.current = 'day_idle'
        }
      }

      // 5. Bolakay (Stickman) koordinatalari
      const p = animProgressRef.current
      let stickmanX = 54
      let stickmanY = groundY
      let stickmanScale = 1
      let stickmanOpacity = 1
      let armAngle = 0
      let legSpread = 0.2
      let isVisible = true

      if (state === 'day_idle') {
        stickmanX = 54
        stickmanY = groundY
        stickmanScale = 1
        stickmanOpacity = 1
        armAngle = Math.sin(time * 0.003) * 0.2
        legSpread = 0.2 + Math.sin(time * 0.002) * 0.05
      } else if (state === 'jump_into_hole') {
        // Teshikka sakrab tushish
        stickmanX = 54 + (holeX - 54) * p
        const jumpArc = Math.sin(p * Math.PI) * 14
        stickmanY = groundY - jumpArc + p * 4
        stickmanScale = Math.max(0, 1 - p * 0.85)
        stickmanOpacity = Math.max(0, 1 - p * 0.95)
        armAngle = p * Math.PI * 1.5
        legSpread = 0.6
      } else if (state === 'night_hidden') {
        isVisible = false
      } else if (state === 'night_peek') {
        // Tunda har 5 sekundda poylash: boshini chiqarib sakraydi va chuqurga qaytadi
        isVisible = true
        const peekArc = Math.sin(p * Math.PI)
        stickmanX = holeX
        // Bosh va ko'zlari teshikdan chiqadi
        stickmanY = groundY + 4 - peekArc * 11
        stickmanScale = 0.85
        stickmanOpacity = peekArc
        armAngle = Math.sin(p * Math.PI * 2) * 0.4
        legSpread = 0.1
      } else if (state === 'jump_out_to_sun') {
        // Teshikdan sakrab chiqib quyoshcha tomon yuguradi va yo'q bo'lib/singib ketadi
        isVisible = true
        if (p < 0.35) {
          // Chuqurdan yuqoriga sakrab chiqish
          const jumpP = p / 0.35
          stickmanX = holeX - (holeX - 60) * jumpP
          stickmanY = groundY - Math.sin(jumpP * Math.PI) * 14
          stickmanScale = Math.min(1, 0.4 + jumpP * 0.6)
          stickmanOpacity = Math.min(1, jumpP * 2)
          armAngle = -0.5
          legSpread = 0.4
        } else {
          // Quyoshcha tomon yugurib borish va yo'q bo'lib ketish (fade out / singib ketish)
          const runP = (p - 0.35) / 0.65
          stickmanX = 60 - (60 - (sunX + 6)) * runP
          stickmanY = groundY
          armAngle = Math.sin(runP * Math.PI * 8) * 0.8
          legSpread = Math.sin(runP * Math.PI * 8) * 0.6

          if (runP > 0.7) {
            // Quyoshga yetganda asta-sekin yo'q bo'lib ketadi
            const fade = (runP - 0.7) / 0.3
            stickmanOpacity = Math.max(0, 1 - fade)
            stickmanScale = Math.max(0, 1 - fade * 0.5)
          } else {
            stickmanOpacity = 1
            stickmanScale = 1
          }
        }
      }

      // Stickmanni chizish
      if (isVisible && stickmanOpacity > 0.02) {
        ctx.save()
        ctx.globalAlpha = stickmanOpacity
        ctx.translate(stickmanX, stickmanY)
        ctx.scale(stickmanScale, stickmanScale)

        const strokeColor = isDark ? '#ffffff' : '#0f172a'
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
  }, [isDark])

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
