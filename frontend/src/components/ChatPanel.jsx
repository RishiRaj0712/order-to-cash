import { useState, useRef, useEffect } from 'react'
import axios from 'axios'

const SUGGESTED_QUESTIONS = [
  "Which products have the most billing documents?",
  "Which customer placed the most orders?",
  "Which sales orders have no delivery?",
  "Trace the flow of billing document 90504298",
  "Show orders that were delivered but not billed",
]

export default function ChatPanel({ apiBase, onHighlight, stats }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Hi! I can help you analyze the Order to Cash process. Ask me anything about orders, deliveries, billing documents, payments, or customers.",
      sql: null,
      node_ids: []
    }
  ])
  const [input, setInput]     = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef             = useRef(null)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function sendMessage(question) {
    const q = (question || input).trim()
    if (!q || loading) return

    // Add user message
    setMessages(prev => [...prev, { role: 'user', content: q }])
    setInput('')
    setLoading(true)

    try {
      const res = await axios.post(`${apiBase}/api/query`, { question: q })
      const { answer, sql, node_ids } = res.data

      // Add assistant message
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: answer,
        sql: sql,
        node_ids: node_ids || []
      }])

      // Highlight nodes in graph if any were returned
      if (node_ids && node_ids.length > 0) {
        onHighlight(node_ids)
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, something went wrong. Please check the backend is running.',
        sql: null,
        node_ids: []
      }])
    } finally {
      setLoading(false)
    }
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div style={{
      width: 360, flexShrink: 0,
      background: '#fff', borderLeft: '1px solid #e5e7eb',
      display: 'flex', flexDirection: 'column', height: '100%'
    }}>

      {/* Header */}
      <div style={{
        padding: '14px 16px', borderBottom: '1px solid #e5e7eb', flexShrink: 0
      }}>
        <div style={{ fontWeight: 600, fontSize: 14, color: '#111' }}>Chat with Graph</div>
        <div style={{ fontSize: 12, color: '#6b7280', marginTop: 2 }}>Order to Cash</div>
      </div>

      {/* Messages */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '12px 14px',
        display: 'flex', flexDirection: 'column', gap: 12
      }}>

        {messages.map((msg, i) => (
          <div key={i} style={{
            display: 'flex',
            flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
            gap: 8, alignItems: 'flex-start'
          }}>

            {/* Avatar */}
            {msg.role === 'assistant' && (
              <div style={{
                width: 28, height: 28, borderRadius: '50%',
                background: '#111', color: '#fff',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 10, fontWeight: 700, flexShrink: 0
              }}>AI</div>
            )}

            {/* Bubble */}
            <div style={{ maxWidth: '82%' }}>
              <div style={{
                background: msg.role === 'user' ? '#111' : '#f3f4f6',
                color: msg.role === 'user' ? '#fff' : '#111',
                borderRadius: msg.role === 'user'
                  ? '16px 16px 4px 16px'
                  : '4px 16px 16px 16px',
                padding: '10px 13px',
                fontSize: 13, lineHeight: 1.5
              }}>
                {msg.content}
              </div>

              {/* SQL accordion */}
              {msg.sql && (
                <details style={{ marginTop: 4 }}>
                  <summary style={{
                    fontSize: 11, color: '#9ca3af', cursor: 'pointer',
                    listStyle: 'none', display: 'flex', alignItems: 'center', gap: 4
                  }}>
                    View SQL query
                  </summary>
                  <pre style={{
                    marginTop: 4, padding: '8px 10px',
                    background: '#1e1e2e', color: '#cdd6f4',
                    borderRadius: 6, fontSize: 10,
                    overflowX: 'auto', whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word', lineHeight: 1.5
                  }}>
                    {msg.sql}
                  </pre>
                </details>
              )}

              {/* Highlighted nodes pill */}
              {msg.node_ids && msg.node_ids.length > 0 && (
                <div style={{
                  marginTop: 4, fontSize: 11, color: '#1D9E75',
                  display: 'flex', alignItems: 'center', gap: 4
                }}>
                  <div style={{
                    width: 6, height: 6, borderRadius: '50%', background: '#1D9E75'
                  }} />
                  {msg.node_ids.length} nodes highlighted in graph
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Loading indicator */}
        {loading && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <div style={{
              width: 28, height: 28, borderRadius: '50%',
              background: '#111', color: '#fff',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 10, fontWeight: 700
            }}>AI</div>
            <div style={{
              background: '#f3f4f6', borderRadius: '4px 16px 16px 16px',
              padding: '10px 13px', fontSize: 13, color: '#6b7280'
            }}>
              Analyzing data...
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Suggested questions — only show when no conversation yet */}
      {messages.length === 1 && !loading && (
        <div style={{ padding: '0 14px 8px', flexShrink: 0 }}>
          <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 6 }}>Try asking:</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {SUGGESTED_QUESTIONS.slice(0, 3).map(q => (
              <button
                key={q}
                onClick={() => sendMessage(q)}
                style={{
                  background: 'none', border: '1px solid #e5e7eb',
                  borderRadius: 6, padding: '6px 10px',
                  fontSize: 11, color: '#374151', cursor: 'pointer',
                  textAlign: 'left', lineHeight: 1.4,
                  transition: 'background 0.15s'
                }}
                onMouseEnter={e => e.target.style.background = '#f9fafb'}
                onMouseLeave={e => e.target.style.background = 'none'}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input area */}
      <div style={{
        padding: '10px 14px', borderTop: '1px solid #e5e7eb',
        flexShrink: 0, display: 'flex', gap: 8
      }}>
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Analyze anything..."
          disabled={loading}
          rows={2}
          style={{
            flex: 1, resize: 'none',
            border: '1px solid #e5e7eb', borderRadius: 8,
            padding: '8px 10px', fontSize: 13,
            fontFamily: 'inherit', outline: 'none',
            background: loading ? '#f9fafb' : '#fff',
            color: '#111'
          }}
        />
        <button
          onClick={() => sendMessage()}
          disabled={loading || !input.trim()}
          style={{
            background: loading || !input.trim() ? '#e5e7eb' : '#111',
            color: loading || !input.trim() ? '#9ca3af' : '#fff',
            border: 'none', borderRadius: 8,
            padding: '0 14px', cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
            fontSize: 13, fontWeight: 500, alignSelf: 'stretch',
            transition: 'background 0.15s'
          }}
        >
          Send
        </button>
      </div>
    </div>
  )
}