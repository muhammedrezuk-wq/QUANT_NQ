// ═══ قسم أسمر — الحكم والقرار (الطبقات 4-5 بالخريطة الهندسية) ═══
// النظام يقرر توقيت الصفقة وحده (محرك 8 خطوات) — والتنفيذ لأسمر بضغطة زر.
import { useEffect, useState } from 'react'

interface AtomRow { id: number; state?: string; health?: { state?: string; message?: string } | null }

const card: React.CSSProperties = { border: '1px solid var(--glassb)', background: 'var(--glass)', borderRadius: 12, padding: 14 }

const JUDGES: [number, string, string][] = [
  [2270, 'رخصة الاتجاه', 'مرآة VWAP: لونغ/شورت/لا شيء'],
  [2271, 'حالة القيمة', 'POC/VAH/VAL: إطار التوازن'],
  [2272, 'كسور الأمس', 'تتبع الكسر وإعادة الاختبار'],
  [2274, 'مصنّف الدخول', 'الأصناف ① رفض · ② إعادة اختبار · ③ وقود-كسر'],
  [2273, 'محكمة الزناد', 'تصويت 5 حواس: تأكيد/فيتو'],
  [2275, 'محرك المخاطر', 'ميزانية + حد يومي + سلّم المتنافسة'],
  [2276, 'محرك القرار', 'decision.approved.state — عرض فقط'],
  [2860, 'مفتاح إيقاف التكيّف', 'قاطع التعديلات الذاتية'],
]

export default function Judgement() {
  const [atoms, setAtoms] = useState<Record<number, AtomRow>>({})
  useEffect(() => {
    const load = () => fetch('/gov/atoms', { cache: 'no-store' }).then(r => r.json())
      .then((d: { atoms?: AtomRow[] }) => {
        const m: Record<number, AtomRow> = {}
        for (const a of d.atoms || []) m[a.id] = a
        setAtoms(m)
      }).catch(() => {})
    load()
    const h = window.setInterval(load, 20000)
    return () => window.clearInterval(h)
  }, [])

  const dot = (id: number) => {
    const st = atoms[id]?.health?.state
    return st === 'healthy' ? 'var(--green)' : st === 'degraded' ? 'var(--amber)' : st ? 'var(--red)' : 'var(--dim)'
  }
  const msg = (id: number) => (atoms[id]?.health?.message || '').slice(0, 70)

  return (
    <div className="section" style={{ display: 'grid', gap: 14, alignContent: 'start' }}>
      <div style={{ ...card, display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <strong style={{ color: 'var(--accent)' }}>الحكم والقرار — هل تُلغى؟</strong>
        <span style={{ color: 'var(--dim)', fontSize: 12 }}>النظام داخل حلقة القرار وحده · أسمر خارجها — تنفيذ فقط (MEXC)</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 10 }}>
        {JUDGES.map(([id, name, role]) => (
          <div key={id} style={{ border: '1px solid var(--glassb)', borderRadius: 10, padding: 10, display: 'grid', gap: 3 }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span style={{ width: 8, height: 8, borderRadius: 8, background: dot(id), display: 'inline-block' }} />
              <b style={{ fontSize: 13 }}>{id} · {name}</b>
            </div>
            <div style={{ color: 'var(--dim)', fontSize: 11, paddingInlineStart: 16 }}>{role}</div>
            <div style={{ color: 'var(--dim)', fontSize: 11, paddingInlineStart: 16 }}>{msg(id) || '—'}</div>
          </div>
        ))}
      </div>

      <div style={card}>
        <div style={{ fontWeight: 700, marginBottom: 6 }}>محرك الاستراتيجية — 8 خطوات (رسمية)</div>
        <div style={{ color: 'var(--dim)', fontSize: 12, lineHeight: 1.9 }}>
          ① عضوية الحلقة (1001) → ② البوابة الاقتصادية (2156: ≥3× كلفة تمر · 2-3× درجة أولى · &lt;2× لا تداول)
          → ③ رخصة المرآة (2151 VWAP + 2155 + 2152 + 2159) → ④ رتبة ألف/باء (2159) → ⑤ عقيدة المستويات (الحواس 01-05)
          → ⑥ فحص الموضع → ⑦ الأصناف الثلاثة (07 + 10 + 11 + 12) → ⑧ لحظة التفعيل: محكمة الزناد (15+09+14+12+17) — أغلبية تنفيذ · فيتو إلغاء.
        </div>
        <div style={{ marginTop: 10, padding: 10, borderRadius: 8, border: '1px solid var(--glassb)', fontSize: 12 }}>
          عند صدور <b>بطاقة قرار</b> (decision.approved.state): تُعرض هنا أرقامها كاملة —
          والتنفيذ بيد أسمر من تبويب <b style={{ color: 'var(--accent)' }}>MEXC</b> (نسخ حرفي · حدود اليوم · الفيتو الأخير).
        </div>
      </div>
    </div>
  )
}
