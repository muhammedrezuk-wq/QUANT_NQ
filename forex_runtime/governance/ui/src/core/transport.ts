import { getApiKey } from './auth'
// طبقة النقل (١٤ §٣): اتصال واحد ببثّ النواة (WS) + عميل قراءة (REST عبر خادم الحوكمة).
// إعادة اتصال تلقائية عند الانقطاع؛ لا CORS (الـREST يمرّ بخادم الحوكمة، نفس الأصل).

// عنوان النواة من عنوان الصفحة نفسها — محليًّا يبقى 127.0.0.1، وعن بعد (Tailscale) يصير عنوان الجهاز تلقائيًّا
// مسارَّان بالتناوب عند كل محاولة:
//  ١) /gov/ws/core — مرشِد الحوكمة (نفس الأصل): لا يحتاج مفتاح (الخادم يحمله
//     من بيئته)، وشغّال عن بُعد حتى لو كان 8010 مقفولًا على الجهاز فقط.
//  ٢) :8010 مباشرة — احتياطًا إن كان المرشِد غائبًا (خادم قديم)، مع مفتاح
//     النواة إن كان عندنا.
const _secure = window.location.protocol === 'https:'
const _host = window.location.host || '127.0.0.1:8090'
// المرشِد يستعمل host (مع المنفذ) لأنّه على أصل الصفحة؛ والنواة تستعمل hostname لأنّ منفذها 8010 يُلحق.
const _hostname = window.location.hostname || '127.0.0.1'
const RELAY_WS = `${_secure ? 'wss' : 'ws'}://${_host}/gov/ws/core`
const CORE_WS = `${_secure ? 'wss' : 'ws'}://${_hostname}:8010/ws/events`

export type WsMsg =
  | { type: 'snapshot'; atoms: unknown[]; metrics: unknown }
  | { type: 'event'; name: string; payload: unknown }

/** يفتح اتصالًا واحدًا ببثّ النواة (المرشِد أولًا، المباشر احتياطًا)، يعيد
 *  الاتصال تلقائيًّا بالتناوب بين المسارين. يرجّع دالة إيقاف. */
export function connectWs(
  onMsg: (m: WsMsg) => void,
  onStatus: (open: boolean) => void,
): () => void {
  let ws: WebSocket | null = null
  let stopped = false
  let attempt = 0

  const open = () => {
    if (stopped) return
    const viaRelay = attempt % 2 === 0
    let next: WebSocket
    try {
      if (viaRelay) {
        next = new WebSocket(RELAY_WS)
      } else {
        const key = getApiKey()
        const encoded = key ? btoa(unescape(encodeURIComponent(key))).replace(/=+$/g, '').replace(/\+/g, '-').replace(/\//g, '_') : ''
        next = encoded ? new WebSocket(CORE_WS, ['quant-nq', `quant-nq-key.${encoded}`]) : new WebSocket(CORE_WS)
      }
    } catch {
      attempt += 1
      setTimeout(open, 2000)
      return
    }
    ws = next
    ws.onopen = () => onStatus(true)
    ws.onmessage = (e) => {
      try { onMsg(JSON.parse(e.data as string) as WsMsg) } catch { /* رسالة غير صالحة تُتجاهل */ }
    }
    ws.onclose = () => { onStatus(false); if (!stopped) { attempt += 1; setTimeout(open, 2000) } }
    ws.onerror = () => { try { ws?.close() } catch { /* تجاهل */ } }
  }
  open()
  return () => { stopped = true; try { ws?.close() } catch { /* تجاهل */ } }
}

/** قراءة عبر خادم الحوكمة (يقرأ النواة ويترجم للعربي). */
export async function govGet<T>(path: string): Promise<T> {
  const r = await fetch(path)
  if (!r.ok) throw new Error(String(r.status))
  return (await r.json()) as T
}

/** كتابة/أمر عبر بوّابة الحوكمة (تمرّر لخُطّاف النواة). */
export function govPost(path: string): Promise<Response> {
  return fetch(path, { method: 'POST' })
}
