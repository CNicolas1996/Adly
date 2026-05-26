import { useEffect, useRef } from 'react'

export default function HeroBackground() {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    let animId
    let mouse = { x: -999, y: -999, active: false }

    const resize = () => {
      canvas.width  = canvas.offsetWidth
      canvas.height = canvas.offsetHeight
    }
    resize()
    window.addEventListener('resize', resize)

    const NODE_COUNT   = 60
    const CONNECT_DIST = 150
    const BASE_SPEED   = 0.22

    function createNode() {
      return {
        x:          Math.random() * canvas.width,
        y:          Math.random() * canvas.height,
        vx:         (Math.random() - 0.5) * BASE_SPEED,
        vy:         (Math.random() - 0.5) * BASE_SPEED,
        r:          Math.random() * 2 + 1,
        pulse:      Math.random() * Math.PI * 2,
        pulseSpeed: Math.random() * 0.02 + 0.008,
        alpha:      Math.random() * 0.4 + 0.25,
        hub:        Math.random() < 0.10,
      }
    }

    const nodes = Array.from({ length: NODE_COUNT }, createNode)

    // Mouse en window — no en canvas — para que funcione con pointerEvents:none
    const onMouseMove = (e) => {
      const rect = canvas.getBoundingClientRect()
      mouse.x = e.clientX - rect.left
      mouse.y = e.clientY - rect.top
      mouse.active = true
    }
    const onMouseLeave = () => { mouse.active = false; mouse.x = -999; mouse.y = -999 }
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseleave', onMouseLeave)

    const onScroll = () => { /* parallax handled per-frame */ }
    window.addEventListener('scroll', onScroll)

    let t = 0
    const draw = () => {
      t++

      // Fondo negro cálido — sin trail, redibujado limpio cada frame
      ctx.fillStyle = '#0a0502'
      ctx.fillRect(0, 0, canvas.width, canvas.height)

      // Mover nodos
      for (const n of nodes) {
        n.pulse += n.pulseSpeed

        if (mouse.active) {
          const dx = mouse.x - n.x
          const dy = mouse.y - n.y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist < 220 && dist > 1) {
            const force = (220 - dist) / 220 * 0.018
            n.vx += (dx / dist) * force
            n.vy += (dy / dist) * force
          }
        }

        n.vx += (Math.random() - 0.5) * 0.008
        n.vy += (Math.random() - 0.5) * 0.008

        const spd = Math.sqrt(n.vx * n.vx + n.vy * n.vy)
        if (spd > 0.85) { n.vx = (n.vx / spd) * 0.85; n.vy = (n.vy / spd) * 0.85 }

        n.vx *= 0.97
        n.vy *= 0.97
        n.x  += n.vx
        n.y  += n.vy

        if (n.x < -80) n.x = canvas.width + 80
        if (n.x > canvas.width + 80) n.x = -80
        if (n.y < -80) n.y = canvas.height + 80
        if (n.y > canvas.height + 80) n.y = -80
      }

      // Conexiones entre nodos
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i], b = nodes[j]
          const dx = a.x - b.x
          const dy = a.y - b.y
          const dist = Math.sqrt(dx * dx + dy * dy)

          if (dist < CONNECT_DIST) {
            const strength = 1 - dist / CONNECT_DIST
            const pulse = Math.sin(t * 0.02 + i * 0.3) * 0.15 + 0.85

            ctx.beginPath()
            ctx.moveTo(a.x, a.y)
            ctx.lineTo(b.x, b.y)
            ctx.strokeStyle = `rgba(232,116,42,${(strength * 0.28 * pulse).toFixed(3)})`
            ctx.lineWidth = strength * 0.9
            ctx.stroke()

            // Paquete viajando por la línea
            if (strength > 0.6 && Math.sin(t * 0.025 + i * 0.7 + j * 0.5) > 0.85) {
              const prog = (Math.sin(t * 0.025 + i + j) * 0.5 + 0.5)
              ctx.beginPath()
              ctx.arc(a.x + (b.x - a.x) * prog, a.y + (b.y - a.y) * prog, 1.4, 0, Math.PI * 2)
              ctx.fillStyle = `rgba(245,180,80,${(strength * 0.7).toFixed(3)})`
              ctx.fill()
            }
          }
        }
      }

      // Conexiones mouse
      if (mouse.active) {
        for (const n of nodes) {
          const dx = n.x - mouse.x
          const dy = n.y - mouse.y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist < CONNECT_DIST * 1.3) {
            const alpha = (1 - dist / (CONNECT_DIST * 1.3)) * 0.25
            ctx.beginPath()
            ctx.moveTo(mouse.x, mouse.y)
            ctx.lineTo(n.x, n.y)
            ctx.strokeStyle = `rgba(245,160,60,${alpha.toFixed(3)})`
            ctx.lineWidth = 0.7
            ctx.stroke()
          }
        }
        // Cursor nodo
        ctx.beginPath()
        ctx.arc(mouse.x, mouse.y, 3, 0, Math.PI * 2)
        ctx.fillStyle = 'rgba(232,116,42,0.6)'
        ctx.fill()

        const ring = (Math.sin(t * 0.08) * 0.5 + 0.5) * 0.18
        ctx.beginPath()
        ctx.arc(mouse.x, mouse.y, 16, 0, Math.PI * 2)
        ctx.strokeStyle = `rgba(232,116,42,${ring.toFixed(3)})`
        ctx.lineWidth = 0.8
        ctx.stroke()
      }

      // Nodos
      for (const n of nodes) {
        const pulse = Math.sin(n.pulse) * 0.18 + 0.82
        const r = n.hub ? n.r * 2 : n.r

        // Glow solo en hubs
        if (n.hub) {
          const glow = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, r * 5)
          glow.addColorStop(0, `rgba(232,116,42,${(n.alpha * 0.2).toFixed(3)})`)
          glow.addColorStop(1, 'rgba(232,116,42,0)')
          ctx.beginPath()
          ctx.arc(n.x, n.y, r * 5, 0, Math.PI * 2)
          ctx.fillStyle = glow
          ctx.fill()
        }

        ctx.beginPath()
        ctx.arc(n.x, n.y, r * pulse, 0, Math.PI * 2)
        ctx.fillStyle = n.hub
          ? `rgba(245,180,80,${(n.alpha * pulse).toFixed(3)})`
          : `rgba(232,116,42,${(n.alpha * pulse).toFixed(3)})`
        ctx.fill()
      }

      // Vignette
      const vig = ctx.createRadialGradient(
        canvas.width / 2, canvas.height * 0.42, 0,
        canvas.width / 2, canvas.height * 0.42, canvas.width * 0.7
      )
      vig.addColorStop(0,   'rgba(0,0,0,0)')
      vig.addColorStop(0.5, 'rgba(0,0,0,0.1)')
      vig.addColorStop(1,   'rgba(0,0,0,0.75)')
      ctx.fillStyle = vig
      ctx.fillRect(0, 0, canvas.width, canvas.height)

      animId = requestAnimationFrame(draw)
    }

    draw()

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', resize)
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseleave', onMouseLeave)
      window.removeEventListener('scroll', onScroll)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      style={{
        position:      'absolute',
        inset:         0,
        width:         '100%',
        height:        '100%',
        zIndex:        0,
        display:       'block',
        pointerEvents: 'none',
      }}
    />
  )
}
