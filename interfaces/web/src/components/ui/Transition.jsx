import { motion } from 'framer-motion'

const variants = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  exit:    { opacity: 0, y: -6 },
}

/**
 * Page transition wrapper for AnimatePresence.
 * Wrap each page's root element with this.
 */
export default function Transition({ children, className = '' }) {
  return (
    <motion.div
      variants={variants}
      initial="initial"
      animate="animate"
      exit="exit"
      transition={{ duration: 0.25, ease: 'easeOut' }}
      style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}
      className={className}
    >
      {children}
    </motion.div>
  )
}
