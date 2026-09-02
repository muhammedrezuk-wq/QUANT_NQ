# قياس `exec_chart` — sqlite مؤقّت، لا وسيط حي

**التاريخ:** 2026-09-03 01:40
**أين:** هذا الصندوق · ليس محطّة المالك

| الحالة | المصدر الذي رجع | العدد |
|---|---|---|
| `copyrates_v2` 5×M1 | `ea_copyrates` | 5 |
| `copyrates_v2` 3×M5 | `ea_copyrates` | 3 |
| تجميع تِكّات TF 180 | `ea_agg` | >0 |
| 5 تِكّات / 5 ثوانٍ | `ea_ticks` | مسار حيّ |
| GBPUSD بلا صفوف | `none` | 0 |

`python3 -m py_compile governance/server.py` → COMPILE_OK.

**لم يُقس:** مطابقة نافذة MetaTrader حيّة · بناء Vite · ترجمة EA على ويندوز.
