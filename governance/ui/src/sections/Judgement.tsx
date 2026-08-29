// ═══ قسم أسمر — الحكم والقرار (الطبقات 4-5 بالخريطة الهندسية) ═══
// النظام يقرر توقيت الصفقة وحده (محرك 8 خطوات) — والتنفيذ لأسمر بضغطة زر.
import { useEffect, useRef, useState } from 'react'
import { useStore } from '../core/store'

interface AtomRow { id: number; state?: string; health?: { state?: string; message?: string } | null }

// ٢٠٢٦-٠٨-٢٩ (ختم NQ): `crypto.decision.signal_card.state` كانت تُنشر من ٢٢٧٧
// **بلا أي مستهلك في الواجهة** — التوصيات تصدر ولا تظهر للمالك إطلاقًا
// (مقيس: صفر ذكر لـsignal_card في كامل ui/src). تُعرض هنا بحقولها كما تصل،
// بلا حساب ولا اشتقاق — الواجهة لا تحسب رقمًا.
interface SignalCard {
  symbol?: string; direction?: string; entry_class?: string; grade?: string; ring?: string
  anchor?: number; entry_price?: number; entry_leg_high?: number; entry_leg_low?: number
  stop_loss?: number; stop_pct?: number
  take_profit?: number; take_profit_source?: string
  take_profit_2?: number; take_profit_2_source?: string
  take_profit_runner?: number | null; take_profit_runner_source?: string | null
  cancel_level?: number; time_stop_candles?: number
  max_risk_usd?: number; reference_equity_usd?: number
  competing_rank?: number; competing_count?: number
  news_fresh?: boolean; news_age_min?: number; gate_margin?: number
  grade_target_profile?: string; timestamp?: number; event_id?: string
}

const num = (v: unknown): string =>
  typeof v === 'number' && isFinite(v)
    ? (Math.abs(v) < 0.001 && v !== 0 ? v.toExponential(3) : String(Number(v.toFixed(8))))
    : '—'

const hhmm = (t?: number): string =>
  typeof t === 'number' ? new Date(t * 1000).toLocaleTimeString('ar-EG-u-nu-latn', { hour12: false }) : '—'

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

  // آخر بطاقة إشارة (حيّة من التيار) + سجلّ دائم من `/gov/decisions`.
  // التيار وحده لا يكفي: البطاقة تُنشر لحظيًّا، فمن يفتح اللوحة بعدها لا يرى شيئًا.
  // السجلّ الدائم يجعل التوصيات باقية بعد إعادة الفتح.
  const card1 = useStore((s) => s.streams['crypto.decision.signal_card.state']) as SignalCard | undefined
  const [log, setLog] = useState<SignalCard[]>([])
  const lastId = useRef<string>('')

  useEffect(() => {
    const load = () => fetch('/gov/decisions?limit=60', { cache: 'no-store' }).then((r) => r.json())
      .then((d: { available?: boolean; decisions?: Record<string, unknown>[] }) => {
        const rows = (d.decisions || []).filter((r) => String(r.stage) === 'APPROVED')
        setLog(rows.map((r) => ({
          symbol: String(r.symbol ?? ''), direction: String(r.direction ?? ''),
          grade: String(r.reason ?? '').split('·')[1]?.trim() || '',
          entry_price: typeof r.take_profit === 'number' ? undefined : undefined,
          stop_loss: typeof r.stop_loss === 'number' ? r.stop_loss : undefined,
          take_profit: typeof r.take_profit === 'number' ? r.take_profit : undefined,
          timestamp: typeof r.decided_at === 'number' ? r.decided_at : undefined,
          event_id: `db-${r.id}`,
        })))
      }).catch(() => {})
    load()
    const h = window.setInterval(load, 20000)
    return () => window.clearInterval(h)
  }, [])

  // بطاقة حيّة جديدة ⇒ تتصدّر السجلّ فورًا بلا انتظار الاستطلاع
  useEffect(() => {
    if (!card1) return
    const id = card1.event_id ?? String(card1.timestamp ?? '')
    if (!id || id === lastId.current) return
    lastId.current = id
    setLog((prev) => [card1, ...prev].slice(0, 60))
  }, [card1])

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

      {/* بطاقة الإشارة الحيّة + سجلّ التوصيات — من ٢٢٧٧ مباشرة */}
      <div style={{ ...card, borderColor: card1 ? 'var(--accent)' : 'var(--glassb)' }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 10, flexWrap: 'wrap' }}>
          <strong style={{ color: 'var(--accent)' }}>بطاقة الإشارة (٢٢٧٧)</strong>
          <span style={{ color: 'var(--dim)', fontSize: 11 }}>توصية — التنفيذ يدويّ على MEXC</span>
          <span style={{ flexGrow: 1 }} />
          <span style={{ color: 'var(--dim)', fontSize: 11 }}>التوصيات المستلمة: <b className="num">{log.length}</b></span>
        </div>

        {!card1 ? (
          <div style={{ color: 'var(--dim)', fontSize: 12 }}>ما وصلت بطاقة بعد — تظهر هنا لحظة إصدارها.</div>
        ) : (
          <>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginBottom: 10 }}>
              <b style={{ fontSize: 17 }}>{card1.symbol}</b>
              <span style={{ padding: '2px 10px', borderRadius: 8, fontWeight: 700,
                background: card1.direction === 'long' ? 'rgba(38,166,154,.25)' : 'rgba(239,83,80,.25)',
                color: card1.direction === 'long' ? 'var(--green)' : 'var(--red)' }}>
                {card1.direction === 'long' ? 'شراء / LONG' : 'بيع / SHORT'}
              </span>
              <span style={{ padding: '2px 8px', borderRadius: 8, border: '1px solid var(--glassb)', fontSize: 12 }}>درجة {card1.grade}</span>
              <span style={{ color: 'var(--dim)', fontSize: 12 }}>{card1.entry_class} · حلقة {card1.ring}</span>
              <span style={{ flexGrow: 1 }} />
              <span style={{ color: 'var(--dim)', fontSize: 11 }}>{hhmm(card1.timestamp)}</span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 8 }}>
              {([
                ['المرساة', num(card1.anchor)],
                ['الدخول', num(card1.entry_price)],
                ['سلّم الدخول', `${num(card1.entry_leg_low)} ← ${num(card1.entry_leg_high)}`],
                ['الوقف', `${num(card1.stop_loss)}  (${num(card1.stop_pct)}%)`],
                ['الهدف ١', `${num(card1.take_profit)}  · ${card1.take_profit_source ?? '—'}`],
                ['الهدف ٢', `${num(card1.take_profit_2)}  · ${card1.take_profit_2_source ?? '—'}`],
                ['الراكض', card1.take_profit_runner == null ? 'لا يوجد' : `${num(card1.take_profit_runner)} · ${card1.take_profit_runner_source ?? ''}`],
                ['الإلغاء', num(card1.cancel_level)],
                ['وقف زمنيّ', `${card1.time_stop_candles ?? '—'} شمعة`],
                ['أقصى مخاطرة', `${num(card1.max_risk_usd)}$ من ${num(card1.reference_equity_usd)}$`],
                ['المتنافسة', `${(card1.competing_rank ?? 0) + 1} من ${card1.competing_count ?? 1}`],
                ['خبر طازج', card1.news_fresh ? `نعم (${num(card1.news_age_min)} د)` : 'لا'],
              ] as [string, string][]).map(([k, v]) => (
                <div key={k} style={{ border: '1px solid var(--glassb)', borderRadius: 8, padding: '6px 9px' }}>
                  <div style={{ color: 'var(--dim)', fontSize: 10.5 }}>{k}</div>
                  <div className="num" style={{ fontSize: 13, fontWeight: 600 }}>{v}</div>
                </div>
              ))}
            </div>
            {card1.grade_target_profile ? (
              <div style={{ color: 'var(--dim)', fontSize: 11, marginTop: 8 }}>ملف الأهداف: {card1.grade_target_profile}</div>
            ) : null}
          </>
        )}

        {log.length > 1 ? (
          <div style={{ marginTop: 12 }}>
            <div style={{ fontWeight: 700, fontSize: 12, marginBottom: 6 }}>سجلّ التوصيات (آخر {log.length})</div>
            <div style={{ display: 'grid', gap: 4 }}>
              {log.map((c, i) => (
                <div key={c.event_id ?? i} style={{ display: 'flex', gap: 10, fontSize: 12, borderBottom: '1px solid var(--glassb)', padding: '3px 0', flexWrap: 'wrap' }}>
                  <span style={{ color: 'var(--dim)', minWidth: 62 }} className="num">{hhmm(c.timestamp)}</span>
                  <b style={{ minWidth: 96 }}>{c.symbol}</b>
                  <span style={{ color: c.direction === 'long' ? 'var(--green)' : 'var(--red)', minWidth: 46 }}>
                    {c.direction === 'long' ? 'شراء' : 'بيع'}
                  </span>
                  <span style={{ color: 'var(--dim)', minWidth: 40 }}>{c.grade}</span>
                  <span className="num" style={{ color: 'var(--dim)' }}>دخول {num(c.entry_price)} · وقف {num(c.stop_loss)}</span>
                </div>
              ))}
            </div>
          </div>
        ) : null}
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
