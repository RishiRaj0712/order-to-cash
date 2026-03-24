import { useState, useEffect } from 'react'
import axios from 'axios'
import GraphPanel from './components/GraphPanel'
import ChatPanel from './components/ChatPanel'
import API_BASE from './config'

const API = API_BASE
// Color mapping for each entity type — used by both graph and NodeDetail
export const NODE_COLORS = {
  Customer:        '#378ADD',
  SalesOrder:      '#1D9E75',
  Product:         '#888780',
  Delivery:        '#7F77DD',
  BillingDocument: '#D85A30',
  JournalEntry:    '#BA7517',
  Payment:         '#639922',
}

export default function App() {
  const [graphData, setGraphData]           = useState({ nodes: [], edges: [] })
  const [loading, setLoading]               = useState(true)
  const [error, setError]                   = useState(null)
  const [highlightedNodes, setHighlightedNodes] = useState(new Set())
  const [selectedNode, setSelectedNode]     = useState(null)
  const [stats, setStats]                   = useState(null)

  // Fetch graph data and stats when app loads
  useEffect(() => {
    Promise.all([
      axios.get(`${API}/api/graph`),
      axios.get(`${API}/api/stats`)
    ])
      .then(([graphRes, statsRes]) => {
        // react-force-graph expects 'links' not 'edges'
        const raw = graphRes.data
        setGraphData({
          nodes: raw.nodes,
          links: raw.edges
        })
        setStats(statsRes.data)
        setLoading(false)
      })
      .catch(err => {
        setError('Cannot connect to backend. Make sure FastAPI is running on port 8000.')
        setLoading(false)
        console.error(err)
      })
  }, [])

  // Called by ChatPanel when an answer arrives with node IDs
  function handleHighlight(nodeIds) {
    setHighlightedNodes(new Set(nodeIds))
    // Clear highlight after 8 seconds
    setTimeout(() => setHighlightedNodes(new Set()), 8000)
  }

  if (loading) return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      height: '100vh', flexDirection: 'column', gap: 16
    }}>
      <div style={{ fontSize: 18, color: '#555' }}>Loading Order-to-Cash graph...</div>
      <div style={{ fontSize: 13, color: '#999' }}>Connecting to backend at localhost:8000</div>
    </div>
  )

  if (error) return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      height: '100vh', flexDirection: 'column', gap: 16, padding: 40
    }}>
      <div style={{ fontSize: 18, color: '#d85a30', fontWeight: 500 }}>Connection Error</div>
      <div style={{ fontSize: 14, color: '#666', textAlign: 'center' }}>{error}</div>
      <code style={{ fontSize: 12, background: '#f0f0f0', padding: '8px 16px', borderRadius: 6 }}>
        cd backend && uvicorn main:app --reload --port 8000
      </code>
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>

      {/* ── Navbar ── */}
      <div style={{
        height: 48, background: '#fff', borderBottom: '1px solid #e5e7eb',
        display: 'flex', alignItems: 'center', padding: '0 20px',
        gap: 8, flexShrink: 0
      }}>
        <span style={{ color: '#9ca3af', fontSize: 14 }}>Mapping</span>
        <span style={{ color: '#9ca3af', fontSize: 14 }}>/</span>
        <span style={{ fontSize: 14, fontWeight: 600, color: '#111' }}>Order to Cash</span>
        {stats && (
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 16 }}>
            {[
              ['Nodes', stats.graph_nodes],
              ['Edges', stats.graph_edges],
              ['Orders', stats.sales_order_headers],
              ['Customers', stats.business_partners],
            ].map(([label, val]) => (
              <div key={label} style={{ fontSize: 12, color: '#6b7280' }}>
                <span style={{ fontWeight: 600, color: '#374151' }}>{val}</span> {label}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Main panels ── */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <GraphPanel
          graphData={graphData}
          highlightedNodes={highlightedNodes}
          selectedNode={selectedNode}
          onNodeClick={setSelectedNode}
        />
        <ChatPanel
          apiBase={API}
          onHighlight={handleHighlight}
          stats={stats}
        />
      </div>

    </div>
  )
}