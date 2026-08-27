// السوق (٨٥٢) — أسعار الرموز الحيّة حسب الرمز (بثّ market.tick، مُجمَّع بالمحرّك).
import { useEffect, useState } from 'react'
import { useStore } from '../core/store'
import { SectionAtomsHealth, SectionConfigTable } from '../components/SectionAtoms'

// بوّابة التغذية أخطر مكان بالمشروع: منها يدخل كل سعر يُبنى عليه قرار. فحالتها
// ومفاتيحها تُعرضان بالصفحة نفسها — لا إعداد محفور بالكود لا يصله المالك.
const FEED_NOTE = 'السعر يجي من هدول: سي-تريدر عبر FIX مباشرة (622) · ميتاتريدر 5 (618)'
  + ' · ياهو (620). سكوتها = ما في تكّات. والجسر القديم (617) أُرشف بيد المالك.'

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
      <div className="section chartsec">
        <div className="empty">جارِ استقبال أسعار السوق من نواتك…</div>
        <SectionAtomsHealth ids={[622, 618, 620]} title="ذرّات تغذية الأسعار — حالتها الحيّة الآن"
          note={FEED_NOTE} />
        <SectionConfigTable from={600} to={650} title="🔌 مفاتيح بوّابة التغذية — كل إعداد معلن بذرّته" />
      </div>
    )
  }
  return (
    <div className="section">
      <div className="ss dim" style={{ marginBottom: 10 }}>
        {rows.length} رمز يبثّ حيًّا الآن — كل رمز مضاف هنا يظهر تلقائيًّا فور وصول أوّل تكّة له من الوسيط.
      </div>
      <SectionAtomsHealth ids={[622, 618, 620]} title="ذرّات تغذية الأسعار — حالتها الحيّة الآن"
        note={FEED_NOTE} />
      <SectionConfigTable from={600} to={650} title="🔌 مفاتيح بوّابة التغذية — كل إعداد معلن بذرّته" />
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
    </div>
  )
}
