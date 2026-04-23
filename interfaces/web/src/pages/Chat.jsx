import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import ChatWindow from '@/components/chat/ChatWindow'

export default function Chat({ onToggleSidebar }) {
  const { id } = useParams()
  const navigate = useNavigate()

  const handleBack = () => navigate('/home')

  return (
    <motion.div
      style={{
        display: 'flex',
        height: '100vh',
        background: '#000',
        position: 'relative',
        overflow: 'hidden',
      }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      {/* Chat area */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        minWidth: 0,
      }}>
        <ChatWindow analysisId={id} onBack={handleBack} />
      </div>
    </motion.div>
  )
}