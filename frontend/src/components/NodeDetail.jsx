import { NODE_COLORS } from '../App'

// Fields to hide from the detail popup — internal/redundant
const HIDDEN_FIELDS = ['id', 'x', 'y', 'vx', 'vy', 'index', '__indexColor', 'entity']

export default function NodeDetail({ node, onClose }) {
  const color = NODE_COLORS[node.type] || '#888'

  // Get all displayable fields
  const fields = Object.entries(node).filter(
    ([k, v]) => !HIDDEN_FIELDS.includes(k) && v !== '' && v !== null && v !== undefined
  )

  return (
    <div style={{
      position: 'absolute', top: 60, left: 12, zIndex: 20,
      background: '#fff', border: '1px solid #e5e7eb',
      borderRadius: 10, padding: 16, width: 280,
      boxShadow: '0 4px 20px rgba(0,0,0,0.12)',
      maxHeight: '70vh', overflowY: 'auto'
    }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <div style={{
          width: 12, height: 12, borderRadius: '50%', background: color, flexShrink: 0
        }} />
        <div style={{ fontWeight: 600, fontSize: 14, color: '#111', flex: 1 }}>
          {node.label || node.id}
        </div>
        <button
          onClick={onClose}
          style={{
            border: 'none', background: 'none', cursor: 'pointer',
            fontSize: 16, color: '#9ca3af', padding: 0, lineHeight: 1
          }}
        >×</button>
      </div>

      {/* Entity type badge */}
      <div style={{
        display: 'inline-block',
        background: color + '20',
        color: color,
        borderRadius: 4, padding: '2px 8px',
        fontSize: 11, fontWeight: 500, marginBottom: 12
      }}>
        {node.type}
      </div>

      {/* Fields */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {fields.map(([key, value]) => {
          if (key === 'type' || key === 'label') return null
          return (
            <div key={key} style={{
              display: 'flex', justifyContent: 'space-between',
              fontSize: 12, gap: 8
            }}>
              <span style={{ color: '#6b7280', flexShrink: 0 }}>
                {key.replace(/([A-Z])/g, ' $1').toLowerCase()}
              </span>
              <span style={{
                color: '#111', textAlign: 'right', wordBreak: 'break-all',
                fontWeight: value === 'C' || value === 'True' ? 500 : 400
              }}>
                {String(value)}
              </span>
            </div>
          )
        })}
      </div>

      {/* Additional info hint */}
      <div style={{
        marginTop: 12, paddingTop: 10,
        borderTop: '1px solid #f3f4f6',
        fontSize: 11, color: '#9ca3af', fontStyle: 'italic'
      }}>
        Additional fields hidden for readability
      </div>
    </div>
  )
}