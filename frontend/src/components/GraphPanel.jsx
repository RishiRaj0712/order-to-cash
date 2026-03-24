import { useRef, useCallback, useState } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { NODE_COLORS } from '../App'
import NodeDetail from './NodeDetail'

export default function GraphPanel({ graphData, highlightedNodes, onNodeClick }) {
  const fgRef = useRef()
  const [hoveredNode, setHoveredNode] = useState(null)
  const [detailNode, setDetailNode]   = useState(null)

  // Draw each node as a colored circle with a label
  const paintNode = useCallback((node, ctx, globalScale) => {
    const isHighlighted = highlightedNodes.has(node.id)
    const isHovered     = hoveredNode?.id === node.id
    const color         = NODE_COLORS[node.type] || '#888780'
    const radius        = isHighlighted ? 10 : isHovered ? 8 : 6

    // Glow ring for highlighted nodes
    if (isHighlighted) {
      ctx.beginPath()
      ctx.arc(node.x, node.y, radius + 4, 0, 2 * Math.PI)
      ctx.fillStyle = color + '40'
      ctx.fill()
    }

    // Main circle
    ctx.beginPath()
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI)
    ctx.fillStyle = isHighlighted ? color : color + 'cc'
    ctx.fill()
    ctx.strokeStyle = '#fff'
    ctx.lineWidth = isHighlighted ? 2.5 : 1.5
    ctx.stroke()

    // Label — only show when zoomed in enough or highlighted
    if (globalScale > 1.5 || isHighlighted || isHovered) {
      const label    = node.label || node.id
      const fontSize = Math.max(3, 12 / globalScale)
      ctx.font       = `${fontSize}px Sans-Serif`
      ctx.textAlign  = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillStyle  = '#1f2937'
      ctx.fillText(label, node.x, node.y + radius + fontSize)
    }
  }, [highlightedNodes, hoveredNode])

  function handleNodeClick(node) {
    setDetailNode(node)
    onNodeClick(node)
  }

  return (
    <div style={{ flex: 1, position: 'relative', background: '#f9fafb', overflow: 'hidden' }}>

      {/* Legend */}
      <div style={{
        position: 'absolute', top: 12, left: 12, zIndex: 10,
        background: '#ffffffee', border: '1px solid #e5e7eb',
        borderRadius: 8, padding: '8px 12px', fontSize: 11
      }}>
        {Object.entries(NODE_COLORS).map(([type, color]) => (
          <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: color }} />
            <span style={{ color: '#374151' }}>{type}</span>
          </div>
        ))}
      </div>

      {/* Node count badge */}
      <div style={{
        position: 'absolute', top: 12, right: 12, zIndex: 10,
        background: '#ffffffee', border: '1px solid #e5e7eb',
        borderRadius: 6, padding: '4px 10px', fontSize: 11, color: '#6b7280'
      }}>
        {graphData.nodes?.length || 0} nodes · {graphData.links?.length || 0} edges
      </div>

      {/* Highlight indicator */}
      {highlightedNodes.size > 0 && (
        <div style={{
          position: 'absolute', bottom: 12, left: 12, zIndex: 10,
          background: '#1D9E75', color: '#fff',
          borderRadius: 6, padding: '6px 12px', fontSize: 12
        }}>
          {highlightedNodes.size} nodes highlighted from chat answer
        </div>
      )}

      <ForceGraph2D
        ref={fgRef}
        graphData={graphData}
        nodeCanvasObject={paintNode}
        nodeCanvasObjectMode={() => 'replace'}
        onNodeClick={handleNodeClick}
        onNodeHover={setHoveredNode}
        linkColor={() => '#d1d5db'}
        linkWidth={1}
        linkDirectionalArrowLength={4}
        linkDirectionalArrowRelPos={1}
        backgroundColor="#f9fafb"
        nodeRelSize={6}
        enableNodeDrag={true}
        enableZoomInteraction={true}
        cooldownTicks={100}
      />

      {/* Node detail popup */}
      {detailNode && (
        <NodeDetail
          node={detailNode}
          onClose={() => setDetailNode(null)}
        />
      )}
    </div>
  )
}