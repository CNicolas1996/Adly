import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import ChatWindow from '@/components/chat/ChatWindow'

export default function Chat({ onToggleSidebar }) {
  const { id } = useParams()
  const navigate = useNavigate()

  return (
    <motion.div
      className="adly-bg"
      style={{
        display: 'flex',
        height: '100vh',
        position: 'relative',
        overflow: 'hidden',
      }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <ChatWindow analysisId={id} onBack={() => navigate('/home')} />
      </div>
    </motion.div>
  )
}
