// السوق (٨٥٢) — أسعار الرموز الحيّة حسب الرمز (بثّ market.tick، مُجمَّع بالمحرّك).
import { useEffect, useState } from 'react'
import { useStore } from '../core/store'
import Connection from './Connection'
// تفاصيل الذرّات والإعدادات تبقى في «الاتصال» و«الذرات»؛ السوق يعرض
// واجهة القراءة المفهومة فقط، لا الحمولة الخام القادمة من النواة.

const fmt = (n: number) => n.toLocaleString('ar-EG-u-nu-latn', { maximumFractionDigits: 2, minimumFractionDigits: 2 })

function ageText(ts: number, now: number): { text: string; color: string } {
  // طوابع الناقل بالثواني و Date.now() بالميلي ثانية — بلا هذا التطبيع كان
  // العمر يُحسب من فجر 1970 فيظهر «ساكت منذ ~29 مليون دقيقة» والسعر حيّ.
  const tsMs = ts > 1e11 ? ts : ts * 1000
  const s = Math.max(0, (now - tsMs) / 1000)
  if (s < 3) return { text: 'حيّ الآن', color: 'var(--green)' }
  if (s < 15) return { text: `آخر تكّة قبل ${Math.round(s)} ث`, color: 'var(--green)' }
  if (s < 60) return { text: `آخر تكّة قبل ${Math.round(s)} ث`, color: 'var(--amber)' }
  return { text: `ساكت منذ ${Math.round(s / 60)} د`, color: 'var(--red)' }
}

export default function Market() {
  const market = useStore((s) => s.market)
  const rows = Object.entries(market).sort((a, b) => a[0].localeCompare(b[0]))
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(t)
  }, [])
  if (rows.length === 0) {
    // بند ١٠ (ورقة ٩٩): بدل الفراغ — حالة ذرّات التغذية التي تجيب الأسعار نفسها
    return (
      <div className="section">
        <div className="empty">جارِ استقبال أسعار السوق من النواة…</div>
        <div className="ss dim" style={{ marginTop: 10 }}>عند وصول أول تكّة ستظهر الرموز والأسعار هنا بشكل مبسّط.</div>
      </div>
    )
  }
  return (
    <div className="section">
      <div className="ss dim" style={{ marginBottom: 10 }}>
        {rows.length} رمز يبثّ حيًّا الآن — كل رمز مضاف هنا يظهر تلقائيًّا فور وصول أوّل تكّة له من الوسيط.
      </div>
      <div className="cards">
        {rows.map(([sym, p]) => {
          const age = ageText(p.ts, now)
          return (
            <div className="scard" key={sym}>
              <div className="st">{sym}</div>
              <div className="sv num">{fmt((p.bid + p.ask) / 2)}</div>
              <div className="ss num">شراء {fmt(p.ask)} · بيع {fmt(p.bid)} · فرق {fmt(p.ask - p.bid)}</div>
              <div className="ss" style={{ color: age.color, marginTop: 4 }}>{age.text}</div>
            </div>
          )
        })}
      </div>
      <div style={{ marginTop: 14 }}>
        <Connection embedded />
      </div>
    </div>
  )
}
