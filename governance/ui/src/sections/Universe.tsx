// ═══ قسم أسمر — الكون (الطبقة 1 بالخريطة الهندسية) ═══
// من يدخل؟ النواة بقوانينها الكاملة · الحلقة الخارجية بأقفالها الثلاثة · المصادر الحية.
import { useEffect, useState } from 'react'

interface Ring { core: string[]; outer: string[] }
interface AtomRow { id: number; state?: string; health?: { state?: string; message?: string } | null }

const card: React.CSSProperties = { border: '1px solid var(--glassb)', background: 'var(--glass)', borderRadius: 12, padding: 14 }
const dim: React.CSSProperties = { color: 'var(--dim)', fontSize: 12 }

const SOURCES: [number, string, string][] = [
  [2620, 'مصدر MEXC — WebSocket', 'تيك · عمق 100 · صفقات'],
  [2621, 'مصدر MEXC — REST', 'شموع · OI · تمويل'],
  [2622, 'مصدر Binance', 'علاوة · OI عالمي'],
  [1001, 'مدير الكون', 'الفرز والحلقتان'],
  [1002, 'تغذية السوق', 'بث الرموز المقبولة'],
  [2708, 'سجل الرموز', 'دقة التكة لكل عقد'],
]

export default function Universe() {
  const [ring, setRing] = useState<Ring>({ core: [], outer: [] })
  const [atoms, setAtoms] = useState<Record<number, AtomRow>>({})

  useEffect(() => {
    const load = () => {
      fetch('/gov/mexc/universe', { cache: 'no-store' }).then(r => r.json()).then((u: Ring) => setRing({ core: u.core || [], outer: u.outer || [] })).catch(() => {})
      fetch('/gov/atoms', { cache: 'no-store' }).then(r => r.json())
        .then((d: { atoms?: AtomRow[] }) => {
          const m: Record<number, AtomRow> = {}
          for (const a of d.atoms || []) m[a.id] = a
          setAtoms(m)
        }).catch(() => {})
    }
    load()
    const h = window.setInterval(load, 20000)
    return () => window.clearInterval(h)
  }, [])

  const hstate = (id: number) => atoms[id]?.health?.state
  const hmsg = (id: number) => atoms[id]?.health?.message || ''

  return (
    <div className="section" style={{ display: 'grid', gap: 14, alignContent: 'start' }}>
      <div style={{ ...card, display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <strong style={{ color: 'var(--accent)' }}>الكون — من يدخل؟</strong>
        <span style={dim}>القراءة حق كل عقد · الصفقة امتياز الفلاتر (الخريطة الهندسية)</span>
        <span style={{ flexGrow: 1 }} />
        <span>النواة <b className="num" style={{ color: 'var(--green)' }}>{ring.core.length}</b></span>
        <span>الخارجية <b className="num" style={{ color: 'var(--amber)' }}>{ring.outer.length}</b></span>
        <span style={dim}>تحديث كل ٢٠ث</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 14 }}>
        <div style={card}>
          <div style={{ fontWeight: 700, marginBottom: 8, color: 'var(--green)' }}>النواة — سهر كامل بكل الحواس ({ring.core.length})</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {ring.core.map(s => (
              <span key={s} style={{ border: '1px solid var(--glassb)', borderRadius: 8, padding: '3px 9px', fontSize: 12 }}>{s}</span>
            ))}
            {!ring.core.length ? <span style={dim}>الفرز يجري…</span> : null}
          </div>
        </div>
        <div style={card}>
          <div style={{ fontWeight: 700, marginBottom: 8, color: 'var(--amber)' }}>الحلقة الخارجية — ثلاثة أقفال ({ring.outer.length})</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {ring.outer.map(s => (
              <span key={s} style={{ border: '1px solid var(--glassb)', borderRadius: 8, padding: '3px 9px', fontSize: 12 }}>{s}</span>
            ))}
            {!ring.outer.length ? <span style={dim}>لا أعضاء حالياً</span> : null}
          </div>
          <div style={{ ...dim, marginTop: 8 }}>① بوابة الجلسة بسبريدها الحقيقي · ② رتبة ألف كاملة · ③ نصف الحجم</div>
        </div>
      </div>

      <div style={card}>
        <div style={{ fontWeight: 700, marginBottom: 10 }}>المصادر الحية</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 10 }}>
          {SOURCES.map(([id, name, role]) => {
            const st = hstate(id)
            const color = st === 'healthy' ? 'var(--green)' : st === 'degraded' ? 'var(--amber)' : st ? 'var(--red)' : 'var(--dim)'
            return (
              <div key={id} style={{ border: '1px solid var(--glassb)', borderRadius: 10, padding: 10 }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span style={{ width: 8, height: 8, borderRadius: 8, background: color, display: 'inline-block' }} />
                  <b style={{ fontSize: 13 }}>{id} · {name}</b>
                </div>
                <div style={{ ...dim, marginTop: 4 }}>{role}</div>
                <div style={{ ...dim, marginTop: 2 }}>{hmsg(id).slice(0, 72)}</div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
