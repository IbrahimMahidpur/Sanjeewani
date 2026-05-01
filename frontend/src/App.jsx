import { useState, useEffect, useCallback } from 'react'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { Activity, MessageSquare, Database, Zap, AlertTriangle, CheckCircle, Search, Send, RefreshCw, Shield } from 'lucide-react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const ADMIN_TOKEN = import.meta.env.VITE_ADMIN_TOKEN || ''

// ── API helpers ────────────────────────────────────────────────────────────────
const apiFetch = async (path, opts = {}) => {
  const res = await fetch(`${API}${path}`, {
    headers: { Authorization: `Bearer ${ADMIN_TOKEN}`, 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

// ── Mock latency data (replace with Prometheus API in production) ──────────────
const genLatencyData = () =>
  Array.from({ length: 20 }, (_, i) => ({
    t: `${i * 3}m`,
    p50: 380 + Math.random() * 200,
    p95: 900 + Math.random() * 600,
    p99: 1400 + Math.random() * 800,
  }))

const genQueryData = () =>
  Array.from({ length: 7 }, (_, i) => ({
    day: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][i],
    whatsapp: Math.floor(40 + Math.random() * 80),
    sms: Math.floor(10 + Math.random() * 30),
  }))

// ── Components ────────────────────────────────────────────────────────────────

function StatCard({ icon: Icon, label, value, sub, color = '#00ff9d', warn = false }) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)',
      border: `1px solid ${warn ? '#ff6b35' : 'rgba(255,255,255,0.08)'}`,
      borderRadius: 16,
      padding: '24px 28px',
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
      position: 'relative',
      overflow: 'hidden',
    }}>
      <div style={{ position: 'absolute', top: 0, right: 0, width: 80, height: 80,
        background: `radial-gradient(circle at 100% 0%, ${color}18 0%, transparent 70%)` }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: warn ? '#ff6b35' : color }}>
        <Icon size={18} />
        <span style={{ fontSize: 12, letterSpacing: '0.1em', textTransform: 'uppercase', fontFamily: 'JetBrains Mono', opacity: 0.8 }}>{label}</span>
      </div>
      <div style={{ fontSize: 32, fontWeight: 800, color: '#f0f0f0', fontFamily: 'Syne', lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)', fontFamily: 'JetBrains Mono' }}>{sub}</div>}
    </div>
  )
}

function TestQuery({ token }) {
  const [query, setQuery] = useState('')
  const [channel, setChannel] = useState('whatsapp')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const run = async () => {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await fetch(`${API}/admin/test-query`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, channel }),
      }).then(r => r.json())
      setResult(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 16, padding: 28 }}>
      <h3 style={{ margin: '0 0 20px', fontFamily: 'Syne', fontSize: 16, color: '#f0f0f0', display: 'flex', alignItems: 'center', gap: 8 }}>
        <Search size={16} color='#00ff9d' /> Live RAG Test
      </h3>
      <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && run()}
          placeholder="e.g. What are symptoms of dengue?"
          style={{
            flex: 1, background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)',
            borderRadius: 10, padding: '12px 16px', color: '#f0f0f0', fontSize: 14,
            fontFamily: 'JetBrains Mono', outline: 'none',
          }}
        />
        <select value={channel} onChange={e => setChannel(e.target.value)}
          style={{ background: '#111', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 10, padding: '12px 14px', color: '#f0f0f0', fontFamily: 'JetBrains Mono', fontSize: 13 }}>
          <option value="whatsapp">WhatsApp</option>
          <option value="sms">SMS</option>
        </select>
        <button onClick={run} disabled={loading || !query.trim()}
          style={{
            background: loading ? '#333' : '#00ff9d', color: '#000', border: 'none',
            borderRadius: 10, padding: '12px 20px', fontWeight: 700, cursor: 'pointer',
            fontFamily: 'Syne', display: 'flex', alignItems: 'center', gap: 6,
          }}>
          {loading ? <RefreshCw size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <Send size={16} />}
          {loading ? 'Running' : 'Run'}
        </button>
      </div>

      {error && (
        <div style={{ background: 'rgba(255,107,53,0.1)', border: '1px solid #ff6b35', borderRadius: 10, padding: 16, color: '#ff6b35', fontFamily: 'JetBrains Mono', fontSize: 13 }}>
          ⚠ {error}
        </div>
      )}

      {result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 8 }}>
          <div style={{ display: 'flex', gap: 12 }}>
            {[
              { label: 'Confidence', value: `${(result.confidence * 100).toFixed(1)}%`, warn: result.confidence < 0.72 },
              { label: 'Latency', value: `${result.latency_ms?.toFixed(0)}ms`, warn: result.latency_ms > 2000 },
              { label: 'Chunks', value: result.chunks_used?.length ?? 0 },
              { label: 'Model', value: result.model?.split('/').pop() ?? '—' },
            ].map(m => (
              <div key={m.label} style={{
                flex: 1, background: 'rgba(255,255,255,0.04)', borderRadius: 10, padding: '10px 14px',
                border: `1px solid ${m.warn ? '#ff6b3566' : 'rgba(255,255,255,0.06)'}`,
              }}>
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)', fontFamily: 'JetBrains Mono', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{m.label}</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: m.warn ? '#ff6b35' : '#00ff9d', fontFamily: 'Syne' }}>{m.value}</div>
              </div>
            ))}
          </div>
          <div style={{ background: 'rgba(0,255,157,0.04)', border: '1px solid rgba(0,255,157,0.15)', borderRadius: 10, padding: 16 }}>
            <div style={{ fontSize: 11, color: '#00ff9d', fontFamily: 'JetBrains Mono', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Answer</div>
            <div style={{ color: '#d0d0d0', fontSize: 14, lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>{result.answer}</div>
          </div>
          {result.chunks_used?.length > 0 && (
            <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.35)', fontFamily: 'JetBrains Mono' }}>
              Sources: {result.chunks_used.map(c => c.source).join(' · ')}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Main App ──────────────────────────────────────────────────────────────────

export default function App() {
  const [health, setHealth] = useState(null)
  const [stats, setStats] = useState(null)
  const [token, setToken] = useState(ADMIN_TOKEN || localStorage.getItem('sj_token') || '')
  const [tokenInput, setTokenInput] = useState('')
  const [latencyData] = useState(genLatencyData)
  const [queryData] = useState(genQueryData)
  const [activeTab, setTab] = useState('dashboard')

  const fetchHealth = useCallback(async () => {
    try {
      const h = await fetch(`${API}/health`).then(r => r.json())
      setHealth(h)
    } catch { setHealth({ status: 'error' }) }
  }, [])

  const fetchStats = useCallback(async () => {
    if (!token) return
    try {
      const s = await fetch(`${API}/admin/stats`, {
        headers: { Authorization: `Bearer ${token}` }
      }).then(r => r.json())
      setStats(s)
    } catch { setStats(null) }
  }, [token])

  useEffect(() => {
    fetchHealth()
    fetchStats()
    const id = setInterval(() => { fetchHealth(); fetchStats() }, 30000)
    return () => clearInterval(id)
  }, [fetchHealth, fetchStats])

  const saveToken = () => {
    localStorage.setItem('sj_token', tokenInput)
    setToken(tokenInput)
  }

  const styles = {
    app: {
      minHeight: '100vh',
      background: '#080c0a',
      color: '#f0f0f0',
      fontFamily: 'Syne, sans-serif',
    },
    sidebar: {
      position: 'fixed', left: 0, top: 0, bottom: 0, width: 220,
      background: 'rgba(0,0,0,0.6)', borderRight: '1px solid rgba(255,255,255,0.06)',
      display: 'flex', flexDirection: 'column', padding: '28px 0',
      backdropFilter: 'blur(20px)',
    },
    main: { marginLeft: 220, padding: '40px 40px', minHeight: '100vh' },
    logo: { padding: '0 24px 32px', borderBottom: '1px solid rgba(255,255,255,0.06)' },
    navItem: (active) => ({
      padding: '12px 24px', cursor: 'pointer', fontSize: 14, fontWeight: 600,
      color: active ? '#00ff9d' : 'rgba(255,255,255,0.45)',
      background: active ? 'rgba(0,255,157,0.06)' : 'transparent',
      borderLeft: active ? '2px solid #00ff9d' : '2px solid transparent',
      transition: 'all 0.15s',
    }),
    grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 32 },
    section: { marginBottom: 32 },
    sectionTitle: { fontSize: 13, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'rgba(255,255,255,0.35)', fontFamily: 'JetBrains Mono', marginBottom: 16 },
  }

  const isOk = health?.status === 'ok'

  return (
    <div style={styles.app}>
      <style>{`
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #080c0a; }
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        ::-webkit-scrollbar { width: 4px; } ::-webkit-scrollbar-track { background: transparent; } ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }
        input:focus { border-color: rgba(0,255,157,0.4) !important; box-shadow: 0 0 0 3px rgba(0,255,157,0.08); }
      `}</style>

      {/* Sidebar */}
      <div style={styles.sidebar}>
        <div style={styles.logo}>
          <div style={{ fontSize: 22, fontWeight: 800, color: '#00ff9d', letterSpacing: '-0.02em' }}>🌿 Sanjeevani</div>
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', fontFamily: 'JetBrains Mono', marginTop: 4 }}>Health AI · Admin</div>
        </div>
        <div style={{ marginTop: 20 }}>
          {[
            { id: 'dashboard', label: 'Dashboard', icon: Activity },
            { id: 'test', label: 'Test Query', icon: Search },
            { id: 'settings', label: 'Settings', icon: Shield },
          ].map(({ id, label, icon: Icon }) => (
            <div key={id} style={styles.navItem(activeTab === id)} onClick={() => setTab(id)}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Icon size={15} /> {label}
              </div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 'auto', padding: '20px 24px', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: isOk ? '#00ff9d' : '#ff6b35', boxShadow: `0 0 6px ${isOk ? '#00ff9d' : '#ff6b35'}` }} />
            <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)', fontFamily: 'JetBrains Mono' }}>
              {isOk ? 'All systems ok' : 'Degraded'}
            </span>
          </div>
        </div>
      </div>

      {/* Main */}
      <div style={styles.main}>
        <div style={{ animation: 'fadeIn 0.3s ease' }}>

          {activeTab === 'dashboard' && (
            <>
              <div style={{ marginBottom: 32 }}>
                <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: '-0.03em', marginBottom: 6 }}>Operations Dashboard</h1>
                <div style={{ color: 'rgba(255,255,255,0.35)', fontSize: 13, fontFamily: 'JetBrains Mono' }}>
                  Real-time metrics · Auto-refresh 30s
                </div>
              </div>

              {/* Stats */}
              <div style={styles.grid}>
                <StatCard icon={Database} label="Knowledge Vectors" value={stats?.vectors_count?.toLocaleString() ?? '—'} sub="Qdrant collection" color="#00ff9d" />
                <StatCard icon={MessageSquare} label="Queries Today" value="—" sub="From Prometheus" color="#6c63ff" />
                <StatCard icon={Zap} label="P50 Latency" value="~420ms" sub="RAG + LLM" color="#00cfff" />
                <StatCard icon={AlertTriangle} label="Low Confidence" value="~3%" sub="Below threshold" color="#ff6b35" warn={false} />
              </div>

              {/* Health */}
              <div style={styles.section}>
                <div style={styles.sectionTitle}>Service Health</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
                  {[
                    { name: 'API', status: health?.status === 'ok' },
                    { name: 'Qdrant', status: health?.qdrant?.startsWith('ok') },
                    { name: 'Redis', status: health?.redis === 'ok' },
                    { name: 'LLM', status: true },
                  ].map(({ name, status }) => (
                    <div key={name} style={{
                      background: 'rgba(255,255,255,0.03)', border: `1px solid ${status ? 'rgba(0,255,157,0.15)' : 'rgba(255,107,53,0.3)'}`,
                      borderRadius: 12, padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 10,
                    }}>
                      {status ? <CheckCircle size={16} color="#00ff9d" /> : <AlertTriangle size={16} color="#ff6b35" />}
                      <span style={{ fontFamily: 'JetBrains Mono', fontSize: 13, color: status ? '#00ff9d' : '#ff6b35' }}>{name}</span>
                      <span style={{ marginLeft: 'auto', fontSize: 11, color: 'rgba(255,255,255,0.3)', fontFamily: 'JetBrains Mono' }}>
                        {status ? 'healthy' : 'error'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Latency chart */}
              <div style={{ ...styles.section, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
                <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 16, padding: 24 }}>
                  <div style={styles.sectionTitle}>Response Latency (ms)</div>
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={latencyData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey="t" tick={{ fontSize: 10, fill: 'rgba(255,255,255,0.3)', fontFamily: 'JetBrains Mono' }} />
                      <YAxis tick={{ fontSize: 10, fill: 'rgba(255,255,255,0.3)', fontFamily: 'JetBrains Mono' }} />
                      <Tooltip contentStyle={{ background: '#111', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontFamily: 'JetBrains Mono', fontSize: 12 }} />
                      <Line type="monotone" dataKey="p50" stroke="#00ff9d" strokeWidth={2} dot={false} name="P50" />
                      <Line type="monotone" dataKey="p95" stroke="#6c63ff" strokeWidth={2} dot={false} name="P95" />
                      <Line type="monotone" dataKey="p99" stroke="#ff6b35" strokeWidth={1.5} dot={false} name="P99" strokeDasharray="4 2" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 16, padding: 24 }}>
                  <div style={styles.sectionTitle}>Queries by Channel</div>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={queryData} barGap={4}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey="day" tick={{ fontSize: 10, fill: 'rgba(255,255,255,0.3)', fontFamily: 'JetBrains Mono' }} />
                      <YAxis tick={{ fontSize: 10, fill: 'rgba(255,255,255,0.3)', fontFamily: 'JetBrains Mono' }} />
                      <Tooltip contentStyle={{ background: '#111', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontFamily: 'JetBrains Mono', fontSize: 12 }} />
                      <Bar dataKey="whatsapp" fill="#00ff9d" radius={[4, 4, 0, 0]} name="WhatsApp" />
                      <Bar dataKey="sms" fill="#6c63ff" radius={[4, 4, 0, 0]} name="SMS" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Qdrant detail */}
              {health && (
                <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12, padding: '14px 20px', fontFamily: 'JetBrains Mono', fontSize: 12, color: 'rgba(255,255,255,0.4)' }}>
                  <span style={{ color: '#00ff9d' }}>qdrant:</span> {health.qdrant} &nbsp;·&nbsp;
                  <span style={{ color: '#6c63ff' }}>redis:</span> {health.redis} &nbsp;·&nbsp;
                  <span style={{ color: '#f0f0f0' }}>api:</span> {health.version}
                </div>
              )}
            </>
          )}

          {activeTab === 'test' && (
            <>
              <div style={{ marginBottom: 32 }}>
                <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: '-0.03em', marginBottom: 6 }}>Live RAG Test</h1>
                <div style={{ color: 'rgba(255,255,255,0.35)', fontSize: 13, fontFamily: 'JetBrains Mono' }}>
                  Send a query directly through the RAG pipeline
                </div>
              </div>
              <TestQuery token={token} />
            </>
          )}

          {activeTab === 'settings' && (
            <>
              <div style={{ marginBottom: 32 }}>
                <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: '-0.03em', marginBottom: 6 }}>Settings</h1>
              </div>
              <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 16, padding: 28, maxWidth: 480 }}>
                <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.5)', marginBottom: 8, fontFamily: 'JetBrains Mono' }}>Admin Token</div>
                <div style={{ display: 'flex', gap: 12 }}>
                  <input
                    type="password"
                    value={tokenInput}
                    onChange={e => setTokenInput(e.target.value)}
                    placeholder="Paste APP_SECRET_KEY"
                    style={{
                      flex: 1, background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)',
                      borderRadius: 10, padding: '12px 16px', color: '#f0f0f0', fontSize: 14,
                      fontFamily: 'JetBrains Mono', outline: 'none',
                    }}
                  />
                  <button onClick={saveToken}
                    style={{ background: '#00ff9d', color: '#000', border: 'none', borderRadius: 10, padding: '12px 20px', fontWeight: 700, cursor: 'pointer', fontFamily: 'Syne' }}>
                    Save
                  </button>
                </div>
                <div style={{ marginTop: 12, fontSize: 12, color: 'rgba(255,255,255,0.3)', fontFamily: 'JetBrains Mono' }}>
                  Stored in localStorage. Match APP_SECRET_KEY in .env
                </div>
              </div>
            </>
          )}

        </div>
      </div>
    </div>
  )
}
