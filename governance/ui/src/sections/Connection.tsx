// الاتصال (859) — منصّة ميتاتريدر 5 + الجسور + اللوحة↔النواة (بثّ: platform.terminal_state + حالة الجسور).
import { useStore } from '../core/store'

interface Term { account_id: string; connected: boolean; trade_allowed: boolean; expert_allowed: boolean }
const BRIDGES: Array<[number, string]> = [
  [618, 'مصدر جسر ميتاتريدر 5'], [601, 'كاتب جسر الدماغ'], [611, 'قارئ الصفقات'],
  [613, 'تغذية السوق'], [619, 'حالة الحساب'], [609, 'مزامنة المراكز'],
]

export default function Connection({ embedded = false }: { embedded?: boolean }) {
  const term = useStore((s) => s.streams['platform.terminal_state']) as Term | undefined
  const atoms = useStore((s) => s.atoms)
  const conn = useStore((s) => s.conn)
  const yn = (b?: boolean) => (b ? 'نعم' : 'لا')
  return (
    <div className={embedded ? undefined : 'section'} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="cards">
        {/* بند 6 (دفتر 97): وسم صريح لكل رقم حساب — هذا حساب «التنفيذ»؛
            حساب سي-تريدر (بيانات فقط، لا تنفيذ عليه أبدًا) ظاهر بقسم «التحليل» */}
        <div className="scard"><div className="st">منصّة ميتاتريدر 5</div><div className={`sv ${term?.connected ? 'green' : 'red'}`}>{term?.connected ? 'متّصلة' : '—'}</div><div className="ss">حساب التنفيذ {term?.account_id ?? '—'} — عليه تُفتح الصفقات فعليًّا</div></div>
        <div className="scard"><div className="st">التداول مسموح</div><div className={`sv ${term?.trade_allowed ? 'green' : 'red'}`}>{term ? yn(term.trade_allowed) : '—'}</div></div>
        <div className="scard"><div className="st">الإكسبرت مسموح</div><div className={`sv ${term?.expert_allowed ? 'green' : 'red'}`}>{term ? yn(term.expert_allowed) : '—'}</div></div>
        <div className="scard"><div className="st">اللوحة ↔ النواة</div><div className={`sv ${conn === 'live' ? 'green' : 'red'}`}>{conn === 'live' ? 'متّصلة' : 'مقطوعة'}</div></div>
      </div>
      <div className="loglist" style={{ flex: 1 }}>
        {BRIDGES.map(([id, name]) => {
          const a = atoms[id]
          return (
            <div className="logrow" key={id}>
              <span className="ln">{name}</span>
              <span className="dim num">#{id}</span>
              <span className={`${a?.color ?? 'grey'}`} style={{ marginInlineStart: 'auto' }}>● {a?.label_ar ?? 'غير محمّلة'}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
