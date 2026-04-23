import { motion } from 'framer-motion'

const SIZES = { sm: 16, md: 24, lg: 36 }

/**
 * Orange spinning ring.
 * size: 'sm' | 'md' | 'lg'
 */
export default function Spinner({ size = 'md' }) {
  const px = SIZES[size] ?? 24

  return (
    <motion.svg
      width={px} height={px}
      viewBox="0 0 24 24"
      animate={{ rotate: 360 }}
      transition={{ duration: 0.9, repeat: Infinity, ease: 'linear' }}
      style={{ display: 'block', flexShrink: 0 }}
    >
      <circle
        cx="12" cy="12" r="9"
        fill="none"
        stroke="#2a2a2a"
        strokeWidth="2.5"
      />
      <circle
        cx="12" cy="12" r="9"
        fill="none"
        stroke="#e8742a"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeDasharray="20 40"
      />
    </motion.svg>
  )
}
