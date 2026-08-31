import { getApiKey } from './auth'
// طبقة النقل (١٤ §٣): اتصال واحد ببثّ النواة (WS) + عميل قراءة (REST عبر خادم الحوكمة).
// إعادة اتصال تلقائية عند الانقطاع؛ لا CORS (الـREST يمرّ بخادم الحوكمة، نفس الأصل).

// عنوان النواة من عنوان الصفحة نفسها — محليًّا يبقى 127.0.0.1، وعن بعد (Tailscale) يصير عنوان الجهاز تلقائيًّا
// مسار واحد ثابت ومباشر إلى النواة لتفادي التذبذب الناتج عن التبديل بين
// المرشِد والمسار المباشر. المصادقة تتم عبر subprotocol لأن المتصفح لا يسمح
// بإضافة X-API-Key إلى مصافحة WebSocket.
const _secure = window.location.protocol === 'https:'
const _host = window.location.host || '127.0.0.1:8090'
// المرشِد يستعمل host (مع المنفذ) لأنّه على أصل الصفحة؛ والنواة تستعمل hostname لأنّ منفذها 8010 يُلحق.
const _hostname = window.location.hostname || '127.0.0.1'
const RELAY_WS = `${_secure ? 'wss' : 'ws'}://${_host}/gov/ws/core`

// منفذ النواة يتبع السوق المختار (كوكي QUANT_MARKET الذي يضبطه الهبّ عند التبديل):
// فوركس 8010 · كريبتو 8020. كان مثبّتًا على 8010، فالمسار المباشر (كل محاولة
// فردية بالتناوب) كان يجلب ذرّات الفوركس ولو كانت اللوحة على الكريبتو —
// فتختلط 226 ذرّة فوركس بـ33 ذرّة كريبتو تناوبًا (عطل مقاس 2026-08-29).
// يُحسب عند كل محاولة اتصال لا مرّة واحدة، كي يتبع التبديل فورًا.
const CORE_PORTS: Record<string, number> = { forex: 8010, crypto: 8020 }
// ٢٠٢٦-٠٨-٣١ (ختم NQ): اسم الكوكي صار مرقّمًا بمنفذ اللوحة في `unified_hub.py`
// لأنّ المتصفّح لا يفصل الكوكي بالمنفذ، فكان تبديلٌ في لوحة الكريبتو يقلب لوحة
// الفوركس كريبتو أيضًا. نقرأ هنا نفس الاسم المرقّم بمنفذ الصفحة الحاليّة، وإلّا
// انكسرت تغذية لوحة الكريبتو (كانت ستقرأ نواة الفوركس 8010 دائمًا).
// الافتراض عند غياب الكوكي يتبع منفذ الصفحة لا الفوركس دائمًا.
const UI_PORT_MARKET: Record<string, string> = { '8090': 'forex', '8091': 'crypto' }
const _coreWs = (): string => {
  const uiPort = window.location.port || '8090'
  const re = new RegExp(`(?:^|;\\s*)QUANT_MARKET_${uiPort}=(forex|crypto)`)
  const m = re.exec(document.cookie)
  const market = m ? m[1] : (UI_PORT_MARKET[uiPort] ?? 'forex')
  const port = CORE_PORTS[market] ?? 8010
  return `${_secure ? 'wss' : 'ws'}://${_hostname}:${port}/ws/events`
}

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
  let reconnectTimer: number | undefined
  let downTimer: number | undefined

  // لا نعلن الانقطاع من أول إغلاق عابر: ننتظر 10 ثوانٍ. هذا يمنع وميض
  // الشاشة عند إعادة تشغيل النواة أو عند تبدّل الشبكة للحظات.
  // ٢٠٢٦-٠٨-٣١ (أمر المالك «صلحهم»): كان يُصفّر المؤقّت ويعيد تسليحه عند كل
  // إغلاق. وبما أنّ إعادة المحاولة كل ٢ ثانية (أقصر من العشر)، كان كل فشل
  // يمسح العدّاد قبل أن يصل — فلم يُعلَن الانقطاع ولا مرّة: تبقى `conn='live'`
  // فيبقى الشريط أخضر «كل الحرّاس سليمون» ولا يظهر شريط التجميد، والنواة ميتة
  // (مقاس حيًّا: النواة مطفأة والكونسول يكرّر ERR_CONNECTION_REFUSED واللوحة
  // خضراء). الآن يُسلَّح مرّة واحدة ويُترك يصل؛ و`markUp()` وحده يلغيه إن عاد
  // الاتصال خلال العشر ثوانٍ — فتبقى نيّة «لا وميض عند إعادة تشغيل قصيرة».
  const markDownDebounced = () => {
    if (downTimer !== undefined) return
    downTimer = window.setTimeout(() => { if (!stopped && ws?.readyState !== WebSocket.OPEN) onStatus(false) }, 10000)
  }
  const markUp = () => {
    if (downTimer !== undefined) { window.clearTimeout(downTimer); downTimer = undefined }
    onStatus(true)
  }

  const open = () => {
    if (stopped) return
    let next: WebSocket
    try {
      const key = getApiKey()
      const encoded = key ? btoa(unescape(encodeURIComponent(key))).replace(/=+$/g, '').replace(/\+/g, '-').replace(/\//g, '_') : ''
      const coreUrl = _coreWs()
      next = encoded ? new WebSocket(coreUrl, ['quant-nq', `quant-nq-key.${encoded}`]) : new WebSocket(coreUrl)
    } catch {
      markDownDebounced()
      reconnectTimer = window.setTimeout(open, 2000)
      return
    }
    ws = next
    ws.onopen = () => markUp()
    ws.onmessage = (e) => {
      try { onMsg(JSON.parse(e.data as string) as WsMsg) } catch { /* رسالة غير صالحة تُتجاهل */ }
    }
    ws.onclose = () => {
      markDownDebounced()
      if (!stopped) reconnectTimer = window.setTimeout(open, 2000)
    }
    ws.onerror = () => { try { ws?.close() } catch { /* تجاهل */ } }
  }
  open()
  return () => {
    stopped = true
    if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer)
    if (downTimer !== undefined) window.clearTimeout(downTimer)
    try { ws?.close() } catch { /* تجاهل */ }
  }
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
