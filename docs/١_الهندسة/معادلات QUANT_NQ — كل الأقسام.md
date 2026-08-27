# معادلات QUANT_NQ

**٢٠٢٦-٠٨-٢٥** · كل معادلة منقولة من الكود الحيّ بملفّها وسطرها.
**الرموز:** `vpu` = قيمة الوحدة = `tick_value ÷ tick_size` · `R_B` = ميزانية الأصل · `S` = قوّة الاتجاه · `u` = استهلاك الميزانية.

---

# أ · المخاطر والميزانية

| المعادلة | الصيغة | المصدر |
|---|---|---|
| قيمة الوحدة | `vpu = tick_value ÷ tick_size` | `518/ledger_support.py:158` |
| ربح الرِجل العائم | `floating = (close − entry) × side × volume × vpu` | `518/ledger_support.py:158` |
| كلفة الرِجل | `cost = commission + estimated_close_commission − swap` | `518/ledger_support.py:169` |
| الأثر الاقتصادي للرِجل | `economic = floating − cost` | `518/ledger_support.py:170` |
| الأثر الكلي | `E = Σ economic` | `518/ledger_support.py:176` |
| الصافي | `net_volume = Σ (side × volume)` | `518/ledger_support.py:178` |
| الوزن السعري | `W = Σ (side × volume × entry_price)` | `518/ledger_support.py:179` |
| متوسط الدخول | `average_entry = W ÷ net_volume` | `525/atom.py:82` |
| كلفة محقّقة احتياطية | `fallback_realized_cost = max(0, realized_gross − realized_net)` | `518/ledger_support.py:187` |
| الربح المُبقى الإجمالي | `K_gross = max(0, realized_gross − X)` | `518/ledger_support.py:189` |
| الربح المُبقى | `K = max(0, realized_net − X)` | `518/ledger_support.py:190` |
| الحالة الاقتصادية | `state_net = K + E` | `518/ledger_support.py:191` |
| التعرّض للخسارة | `loss_exposure = max(0, −state_net)` | `518/ledger_support.py:192` |
| السحب المحقّق | `realized_drawdown = max(0, −(realized_gross − X))` | `518/ledger_support.py:202` |
| استهلاك عائم | `u_float = loss_exposure ÷ R_B` | `518/ledger_support.py:203` |
| استهلاك محقّق | `u_realized = realized_drawdown ÷ R_B` | `518/ledger_support.py:204` |
| **الاستهلاك النافذ** | `u = max(u_float, u_realized)` | `518/ledger_support.py:205` |
| التعرّض الاسمي | `notional = |volume| × price × contract_size` | `508/atom.py:120` |
| نسبة التعرّض | `exposure_pct = notional ÷ equity × 100` | `508/atom.py:185` |
| حجز المخاطرة | `Σ reserved + amount ≤ equity × max_reserved_risk_pct ÷ 100` | `516/atom.py:173` |
| الخسارة اليومية التراكمية | `daily_loss_pct += loss_pct` | `516/atom.py:208` |
| نسبة الخسارة من الصفقة | `loss_pct = −(net ÷ capital) × 100` | `517/atom.py:142` |
| صافي نتيجة الصفقة | `net = gross + Σ التكاليف المعلومة` | `517/atom.py:141` |
| كلفة الصفقة الكلّية | `cost_total = net − gross` | `517/atom.py:160` |

---

# ب · التحجيم واللوت

| المعادلة | الصيغة | المصدر |
|---|---|---|
| مبلغ المخاطرة | `risk_amount = equity × risk_per_trade_pct ÷ 100` | `513/atom.py:168` |
| مخاطرة اللوت الواحد | `denom = distance × tick_value ÷ tick_size` | `513/atom.py:169` |
| اللوت الخام | `raw = risk_amount ÷ denom` | `513/atom.py:171` |
| التقريب لخطوة الوسيط | `stepped = round(raw ÷ step) × step` | `513/atom.py:173` |
| **حارس «مو أكثر أبدًا»** | `إذا stepped × denom > risk_amount × 1.01 ⇒ stepped = floor(raw ÷ step) × step` | `513/atom.py:174-175` |
| الحدّ الأدنى | `broker_min = max(min_lot, volume_min)` | `513/atom.py:176` |
| الحدّ الأقصى | `broker_max = min(max_lot, volume_max)` | `513/atom.py:177` |
| اللوت النهائي | `lot = round(min(broker_max, stepped), 6)` | `513/atom.py:180` |
| مسافة الوقف الافتراضية | `default_distance = close × default_stop_pct ÷ 100` | `513/atom.py:220` |
| مسافة وقف الشراء | `distance = close − buy_stop` | `513/atom.py:228` |
| مسافة وقف البيع | `distance = sell_stop − close` | `513/atom.py:232` |
| تقريب الحجم بالتنفيذ | `volume = floor(volume ÷ step + 1e-9) × step` | `584/atom.py:70` |

---

# ج · التعرّض والتحوّط

| المعادلة | الصيغة | المصدر |
|---|---|---|
| **السعة** | `capacity = min(max_target_volume, R_B ÷ (price × stop_frac × vpu))` | `position_delta_recompute.py:204` |
| سقف المخاطرة | `risk_cap = 2 × R_B ÷ (price × stop_frac × vpu)` | `581/atom.py:351` |
| كلفة التحوّط للوحدة | `cost_per_volume = spread_cost + hedge_cost_per_volume` | `581/atom.py:351` |
| سقف الكلفة | `cost_cap = R_B ÷ cost_per_volume` | `581/atom.py:352` |
| **سقف الإجمالي** | `gross_cap = min(max_target, risk_cap, cost_cap)` | `581/atom.py:353` |
| نسبة التعرّض `E(S)` | أعلى عتبة في `bands` لا تتجاوز `S`، مقصوصة `[0,1]` | `581/atom.py:301-304` |
| نسبة التحوّط `H(S)` | أعلى عتبة في `hedge_bands` لا تتجاوز `S`، مقصوصة `[0,1]` | `581/atom.py:307-310` |
| الإجمالي عند تعرّض صفر | `gross = min(current_gross, gross_cap)` | `position_delta_recompute.py:215` |
| الإجمالي عند تعرّض موجب | `gross = min(capacity × E(S), gross_cap)` | `position_delta_recompute.py:218` |
| سقّاطة الضعف | `إذا S < S السابق ⇒ gross = min(gross, gross السابق)` | `position_delta_recompute.py:219-222` |
| **الصافي المطلوب** | `target_net = gross × (1 − H(S)) × (+1 شراء / −1 بيع)` | `position_delta_recompute.py:224-227` |
| رجل الشراء | `target_buy = max(0, (gross + target_net) ÷ 2)` | `position_delta_recompute.py:228` |
| رجل البيع | `target_sell = max(0, (gross − target_net) ÷ 2)` | `position_delta_recompute.py:229` |
| الطوارئ والحجب | `إذا الفلتر لم يمرّ ⇒ E = 0 و H = 1` | `position_delta_recompute.py:209-211` |
| الحياد بمركز قائم | `target_net = 0 · target_buy = target_sell = gross ÷ 2` | `position_delta_recompute.py:176-179` |

## جدول النطاقات النافذ

| `S` | `E(S)` | `H(S)` | `target_net ÷ capacity` |
|---|---|---|---|
| `< 0.20` | `0.0` | `1.0` | `0٪` — والإجمالي محفوظ |
| `0.20 – <0.40` | `0.1` | `0.7` | `3٪` |
| `0.40 – <0.60` | `0.25` | `0.4` | `15٪` |
| `≥ 0.60` | `0.5` | `0.2` | `40٪` |

**المصدر:** `581/manifest.yaml` — `bands` و`hedge_bands`.

---

# د · الفرق والأوامر

| المعادلة | الصيغة | المصدر |
|---|---|---|
| فرق الشراء الخام | `raw_buy = target_buy − current_buy` | `position_delta_recompute.py:54` |
| فرق البيع الخام | `raw_sell = target_sell − current_sell` | `position_delta_recompute.py:55` |
| قصّ الخطوة | `delta = max(−max_step, min(max_step, raw))` | `position_delta_recompute.py:56-57` |
| الصافي المتحرّك | `delta_net = delta_buy − delta_sell` | `position_delta_recompute.py:81` |
| قرار الإمساك | `إذا |delta_buy| < min_volume و |delta_sell| < min_volume ⇒ HOLD` | `position_delta_recompute.py:59-63` |
| قرار التخفيض | `إذا delta < −min_volume ⇒ REDUCE أو REBALANCE` | `position_delta_recompute.py:65-68` |
| قرار التحوّط | `إذا target_net × current_net < 0 ⇒ HEDGE وإلّا ADD` | `position_delta_recompute.py:72` |
| هستيريسيس الدخول | `يُمسك الاتجاه إذا S ≥ s_enter` | `581/atom.py:333` |
| هستيريسيس الخروج | `يُترك الاتجاه إذا S ≤ s_exit` | `581/atom.py:337` |
| الانعكاس عبر الحياد | `لا انقلاب إلّا إذا |current_net| ≤ min_volume و S ≥ s_enter` | `581/atom.py:340-343` |

---

# هـ · الوقف

| المعادلة | الصيغة | المصدر |
|---|---|---|
| **المجال** | `room = R_B + K − commission` | `525/atom.py:79` |
| **مسافة الوقف** | `delta_p = room ÷ (vpu × |v_net|)` | `525/atom.py:80` |
| **سعر الوقف الصلب** | `p_stop = (W + (−R_B − K + commission) ÷ vpu) ÷ v_net` | `525/atom.py:80` |
| شرط الحساب | `|v_net| ≥ min_abs_v_net` وإلّا لا وقف اتجاهي | `525/atom.py:77` |
| المسافة الدنيا القانونية | `min_dist = max(stops_level, freeze_level, hard_floor_points) × point + buffer × point` | `584/atom.py:124` |
| **تصغير الحجم لا توسيع الوقف** | `factor = requested_distance ÷ min_dist` ثمّ `volume = round(volume × factor)` | `584/atom.py:129-130` |
| الهدف | `TP = ref ± reward_risk × min_dist` | `584/atom.py:132` |
| ستوب الكارثة | `price ∓ (price × fallback_stop_frac × catastrophe_stop_multiple)` | `578/manifest.yaml` |
| مضاعف الربح | `r_multiple = profit_distance ÷ risk` | `572/atom.py:88` · `574/atom.py:98` |
| مسافة الربح | `profit_distance = (current − entry)` شراءً · `(entry − current)` بيعًا | `572/atom.py:87` |
| المخاطرة المرجعية | `risk = |entry − stop|` | `572/atom.py:58` · `573/atom.py:83` · `574/atom.py:66` |
| شرط التعادل | `r_multiple ≥ breakeven_at_r ⇒ SL = entry` | `572/atom.py:89-91` |
| شرط التتبّع | `profit_distance ÷ risk ≥ trail_start_r` | `573/atom.py:145` |
| قاعدة التتبّع | `SL = الوقف الهيكلي، ولا يتحرّك إلا لجهة أضيق` | `573/atom.py:93-104` |
| الإغلاق الجزئي | `close_volume = round(volume × partial_fraction)` · `remainder = volume − close_volume` | `574/atom.py:102-103` |

---

# و · الهامش

| المعادلة | الصيغة | المصدر |
|---|---|---|
| الهامش المباشر | `required = volume × margin_initial` | `585/atom.py:69` |
| الهامش المحسوب | `required = volume × contract_size × price ÷ leverage` | `585/atom.py:73` |
| المتاح | `available = free_margin − reserved` | `585/atom.py:99` |
| **الشرط** | `need = required × (1 + margin_buffer_pct)` ويجب `available ≥ need` | `585/atom.py:100` |

---

# ز · التخريج وسلّم الربح

| المعادلة | الصيغة | المصدر |
|---|---|---|
| **مرحلة الربح** | `milestone(k) = R_B × milestone_mult^k` | `524/atom.py:176` |
| **مبلغ التخريج** | `amount = extract_fraction × milestone(k)` | `524/atom.py:177` |
| المرحلة التالية | `next = R_B × milestone_mult^(highest+1)` | `524/atom.py:151` |
| أعلى مرحلة بلغت | أكبر `k` حيث `gross ≥ R_B × mult^k` | `524/atom.py:89-98` |
| شرط التخريج الكامل | `gross ≥ full_target` و`full_target > 0` | `524/atom.py:194` |
| المتاح للتخريج | `available = max(0, realized_net − X)` | `518/atom.py:242` |
| تحديث المخرَج | `X += min(amount, available)` | `518/atom.py:243` |

**السلّم بـ`R_B = 50` و`mult = 2` و`fraction = 0.5`:** `50→25` · `100→50` · `200→100` · `400→200`.

---

# ح · العيار ٠-١٠٠

| المعادلة | الصيغة | المصدر |
|---|---|---|
| التطبيع | `x = clamp(dial, 0, 100) ÷ 100` | `523/atom.py:91` |
| الاستيفاء الخطي | `lerp(low, high, t) = low + (high − low) × t` | `523/atom.py:38` |
| الأفق الزمني | `horizon = lerp(horizon_min_s, horizon_max_s, x^horizon_shape)` | `523/atom.py:94` |
| قوّة الفلترة | `filter_strength = lerp(filter_min, filter_max, x)` | `523/atom.py:95` |
| **مسافة الوقف** | `stop_distance_frac = lerp(stop_min_frac, stop_max_frac, x)` | `523/atom.py:96` |
| إيقاع الإدارة | `mgmt_cadence_s = lerp(cadence_fast_s, cadence_slow_s, x)` | `523/atom.py:97` |
| ميل اللوت | `large إذا x < 0.5 وإلّا small` | `523/atom.py:104` |

---

# ط · القرار

| المعادلة | الصيغة | المصدر |
|---|---|---|
| وزن الدليل | `weight = directional_weight للاتجاهي · context_weight للسياقي` | `453/atom.py:143-147` |
| حصّة الدرجة | `share = clamp(score ÷ 100)` | `453/atom.py:178` |
| **مساهمة الدليل** | `value = weight × share × confidence × quality_factor` | `453/atom.py:181` |
| كتلة المتكلّمين | `spoken_mass = buy_total + sell_total` | `453/atom.py:193` |
| الصافي | `net = buy_total − sell_total` | `453/atom.py:194` |
| **الدرجة** | `score = |net| ÷ spoken_mass × 100` | `453/atom.py:195` |
| **المشاركة** | `participation = spoken_weight ÷ present_weight` | `453/atom.py:196` |
| **القوّة `S`** | `strength = |net| ÷ present_weight` | `453/atom.py:197` |
| حجب المشاركة | `إذا participation < min_participation ⇒ الاتجاه يُجبَر حيادًا` | `453/atom.py:203-205` |
| نطاق الحياد | `إذا |net| ÷ present_weight < neutral_band ⇒ NEUTRAL` | `458` · `manifest` |
| علم التعارض | `إذا الخاسر ÷ الرابح > conflict_ratio ⇒ RESOLVED_WITH_CONFLICT` | `458` · `manifest` |
| معامل السياق | `cf = أصغر context_factor × (entry.strength ÷ 100) × (invalidation.strength ÷ 100)` | `413/atom.py:90-94` |
| الوزن الفعّال | `weight_applied × cf` للجاهزين فقط | `413/atom.py:98-101` |
| **الوزن النشِط** | `active = Σ (weight_applied × cf)` | `413/atom.py:102` |
| قيمة موزونة | `Σ (حقل × w) ÷ active` — و`None` إذا `active ≤ 0` | `413/atom.py:110-113` |
| العمق المجمّع | `Σ (current_depth × weight) ÷ Σ weight` | `413/atom.py:118-121` |
| الجاهزية | `min(100, depth ÷ required_depth × 100)` | `413/atom.py:127-129` |
| **شرط `READY`** | `active ≥ min_active_weight` و`depth ≥ required_depth` و`confidence ≥ confidence_threshold` و`direction ≠ 0` | `413/atom.py:132-138` |
| أهلية الشراء | `direction ≥ buy_min_direction` و`strength ≥ min_strength` و`confidence ≥ min_confidence` و`depth ≥ min_current_depth` | `455` · `manifest` |
| أهلية البيع | `direction ≤ −sell_min_direction` مع الشروط نفسها | `456` · `manifest` |

---

# ي · بطاقة القسم

| المعادلة | الصيغة | المصدر |
|---|---|---|
| تغطية العيّنة | `sample = clip(len(returns) ÷ 24 × 100)` | `section_live.py:281` |
| دليل الحركة | `movement = clip(Σ|return| × 160000)` | `section_live.py:286` |
| اكتمال الوحدات | `units = clip(units_ok ÷ expected_units × 100)` | `section_live.py:290` |
| نسبة الضجيج | `noise_ratio = √variance ÷ max(mean_abs, 1e-9)` | `section_live.py:297` |
| الاستقرار | `stability = clip(100 − noise_ratio × 60)` | `section_live.py:300` |
| السبريد | `spread = clip(100 − average_spread × 200000)` | `section_live.py:303` |
| الاستمرارية | `continuity = clip(100 − max_gap ÷ max(mean_gap, 0.001) × 15)` | `section_live.py:309` |
| الاتّساق | `agreement = clip(100 × (1 − |early − late| ÷ (|early| + |late|)))` | `section_live.py:319` |
| **العمق الحالي** | `0.30×sample + 0.30×movement + 0.25×units + 0.15×continuity` | `section_live.py:334` |
| **الثقة** | `0.40×stability + 0.30×spread + 0.30×agreement` | `section_live.py:338` |
| العمر | `age = max(0, now − source_timestamp)` | `section_live.py:344` |
| الطزاجة | `fresh = age ≤ ttl_s` | `section_live.py:345` |
| التقادم | `(now − source) > STALE_AFTER_S` | `section_contract.py:136` |

---

# ك · بطاقة المحلّل

| المعادلة | الصيغة | المصدر |
|---|---|---|
| الدرجة الاتجاهية | `score = clip(movement × 250000 × sensitivity, −100, 100)` | `live_analysis.py:840` |
| تغطية العيّنة | `sample_evidence = clip(len(returns) ÷ 24 × 100)` | `live_analysis.py:842` |
| دليل الحركة | `movement_evidence = clip(Σ|return| × 160000 × depth_factor)` | `live_analysis.py:844` |
| الاستقرار | `stability_evidence = clip(100 − noise_ratio × 60)` | `live_analysis.py:853` |
| السبريد | `spread_evidence = clip(100 − average_spread × 200000)` | `live_analysis.py:855` |
| المرجع | `reference = max(median(movements), max(average_spread, MOVEMENT_FLOOR))` | `live_analysis.py:858-860` |
| الشذوذ | `abnormality = clip(|movement| ÷ reference × 50)` | `live_analysis.py:869` |
| التماسك | `coherence = clip(|Σ return| ÷ Σ|return| × 100)` | `live_analysis.py:874` |
| التركّز | `concentration = clip((1 − max|return| ÷ Σ|return|) × n ÷ (n−1) × 100)` | `live_analysis.py:876` |
| الاستمرار | `persistence = clip(عدد ≥ baseline ÷ len(movements) × 100)` | `live_analysis.py:883` |
| السلامة | `integrity = (coherence + concentration + persistence) ÷ 3` | `live_analysis.py:886` |
| **القوّة** | `strength = clip(abnormality × integrity ÷ 100)` | `live_analysis.py:887` |
| الاستمرارية | `continuity_evidence = clip(100 − max_gap ÷ max(mean_gap, 0.001) × 15)` | `live_analysis.py:889` |
| دليل الحجم | `volume_evidence = 100 إن وُجد حجم موجب وإلّا 45` | `live_analysis.py:896` |
| **العمق الحالي** | `0.35×sample + 0.30×movement + 0.20×continuity + 0.15×volume` | `live_analysis.py:902` |
| الاتّساق | `agreement = clip(100 × (1 − |early − late| ÷ (|early| + |late|)))` | `live_analysis.py:906` |
| **الثقة** | `0.40×stability + 0.30×spread + 0.30×agreement` | `live_analysis.py:924` |

---

# ل · بطاقة الاستراتيجية والاحتمال

| المعادلة | الصيغة | المصدر |
|---|---|---|
| تغطية العيّنة | `sample = clip(len(returns) ÷ required_ticks × 100)` | `strategy_contract.py:125` |
| دليل الحركة | `movement = clip(Σ|return| × 160000)` | `strategy_contract.py:126` |
| جودة السبريد | `spread_quality = clip(100 − متوسط السبريد النسبي × 200000)` | `strategy_contract.py:136` |
| الثبات | `consistency = clip(100 − √variance ÷ max(mean_abs, 1e-9) × 50)` | `strategy_contract.py:143` |
| **العمق الحالي** | `0.40×sample + 0.25×movement + 0.20×spread_quality + 0.15×consistency` | `strategy_contract.py:147` |
| الوزن الفعّال | `effective = weight × context_factor` إن كانت جاهزة وإلّا `0` | `strategy_contract.py:181` |
| **شرط الجاهزية** | `depth ≥ required_depth` و`confidence ≥ confidence_threshold` و`strength ≥ strength_threshold` | `strategy_contract.py:174-178` |
| وزن متساوٍ للاتجاهيات | `EQUAL_WEIGHT = 100 ÷ عدد الاتجاهيات` | `strategy_contract.py:34` |
| وزن متساوٍ للنماذج | `EQUAL_MODEL_WEIGHT = 100 ÷ عدد النماذج` | `probability_contract.py:33` |
| حدّ الاحتمال | `probability = max(0, min(1, probability))` | `probability_contract.py:176` |
| وزن متساوٍ للمحلّلين | `100 ÷ 15` | `live_analysis.py:51` |
| وزن متساوٍ للأقسام | `100 ÷ 6` | `live_analysis.py:68` |

---

# م · التحليل — الخمسة عشر

| المحلّل | الصيغة | المصدر |
|---|---|---|
| `151` الاتجاه | `alpha = 2 ÷ (period + 1)` · `EMA = alpha × close + (1 − alpha) × EMA` | `151/atom.py:95-96,177` |
| `152` الزخم | `ROC = (close − close[−period−1]) ÷ close[−period−1] × 100` | `152/atom.py:152-156` |
| `152` الاندفاع | `متوسط |close[i] − close[i−1]| على النافذة` | `152/atom.py:158-160` |
| `153` التذبذب | `TR = max(high−low, |high−prev_close|, |low−prev_close|)` | `153/atom.py:161` |
| `153` ATR | `ATR = متوسط TR على atr_window` · `ratio = ATR ÷ ATR الأساس` | `153/atom.py:184-186` |
| `154` الحجم | `ratio = volume ÷ متوسط الحجم` | `154/atom.py:195` |
| `155` السبريد | `exp_ratio = متوسط قصير ÷ متوسط طويل` | `155/atom.py:176` |
| `156` الشموع | `نِسَب الجسم والفتيل: doji_body_ratio · marubozu_body_ratio · pin_wick_ratio` | `156/manifest.yaml` |
| `157` الفجوات | `gap_pct مقابل gap_threshold_pct` | `157/manifest.yaml` |
| `158` الجلسات | `حدود الساعات من الإعداد + utc_offset_hours` | `158/manifest.yaml` |
| `159` أثر الوقت | `week_open_day` · `week_close_day` | `159/manifest.yaml` |
| `160` الارتباط | `r = cov ÷ √(var_x × var_y)` · `ret = (close − prev) ÷ prev` | `160/atom.py:54-66,166` |
| `161` القوّة النسبية | `ret = (close − first) ÷ first` · `percentile = rank ÷ (total − 1)` | `161/atom.py:141-150` |
| `162` السرعة | `speed_pct = |close − prev| ÷ prev × 100` · `ratio = speed ÷ baseline` | `162/atom.py:144-151` |
| `163` التسارع | `ratio = (speed − prev_speed) ÷ baseline` | `163/atom.py:145-154` |
| `164` جودة الحجم | `ratio مقابل low_ratio` · و`volume ≤ 0 ⇒ MISSING` | `164/manifest.yaml` |
| `165` الضوضاء | `efficiency = |close[−1] − close[0]| ÷ Σ|close[i] − close[i−1]|` | `165/atom.py:133-140` |

---

# ن · البنية والسيولة والعمق

| المعادلة | الصيغة | المصدر |
|---|---|---|
| `201` بروز القمة | `span = win_high − win_low` · `prominence = gap ÷ span` | `201/atom.py:128-139` |
| `201` القمة/القاع | `شمعتان كل جهة (lookback = 2)` | `201/manifest.yaml` |
| `204` كسر البنية | `span = swing_high − swing_low` · `frac = |close − level| ÷ span` | `204/atom.py:119-122` |
| `254` الكنس | `فتيلة تتجاوز البركة: high ≥ pool شراءً · low ≤ pool بيعًا` | `254/atom.py:150-151` |
| `255` الفجوة | `ثلاث شموع: gap_bottom = first.high · gap_top = third.low` | `255/atom.py:108-116` |
| `251` مجمّعات السيولة | `confidence = clip(value ÷ SCORE_MAX, 0, 1)` | `251/atom.py:54` |
| `106` اختلال العمق | `imbalance = (bid_volume − ask_volume) ÷ (bid + ask)` | `106/atom.py:110` |
| `261` اتجاه العمق | `direction = clamp(imbalance × 100, −100, +100)` | `261/atom.py:73` |
| `261` عمق العمق | `evidence = min(100, levels × 10)` · `ready = levels ≥ required_levels` | `261/atom.py:74-75` |
| `258` الامتصاص | `absorption_ratio` عتبة الإعداد | `258/manifest.yaml` |

---

# س · الإحصاء

| المعادلة | الصيغة | المصدر |
|---|---|---|
| `301` المتوسط | `mean = Σx ÷ n` | `301/atom.py` |
| `304` التباين | `variance = Σ(x − mean)² ÷ (n − 1)` — **عيّنة** | `304/atom.py:108` |
| `304` الانحراف | `std = √variance` | `304/atom.py:109` |
| `306` معامل الاختلاف | `cv = √variance ÷ |mean|` | `306/atom.py:111` |
| `308` الانحدار | `sxy = Σ(x−x̄)(y−ȳ)` · `sxx = Σ(x−x̄)²` · `slope = sxy ÷ sxx` | `308/atom.py:114-116` |
| `309` معامل التحديد | `r² = sxy² ÷ (sxx × syy)` | `309/atom.py:117` |
| `310` درجة Z | `z = (x[−1] − mean) ÷ std` | `310/atom.py:114` |
| `311` الالتواء | `skew = m3 ÷ (m2 × √m2)` | `311/atom.py:121` |
| `312` التفلطح | `excess = m4 ÷ m2² − 3` | `312/atom.py:121` |
| `313` الشذوذ | `IQR = q3 − q1` · الحدّ `± iqr_multiplier × IQR` | `313/atom.py:112-113` |
| `315` المدى | `high_band` · `low_band` كنسب من المدى | `315/manifest.yaml` |
| `318` مقارنة الفترات | `drift_band` · `vol_band` | `318/manifest.yaml` |
| الثقة الإحصائية | `confidence = count ÷ window_size` | `304/atom.py:110` |
| `358` هيرست | `R/S: النقاط (log size, log متوسط(span ÷ std))` والميل بالانحدار | `358/atom.py:33-48` |

---

# ع · التنفيذ والانحراف والوقت

| المعادلة | الصيغة | المصدر |
|---|---|---|
| **الانزلاق** | `adverse = (filled − asked) × (+1 شراءً / −1 بيعًا)` | `563/atom.py:242` |
| الانزلاق بالنقاط | `slippage_points = adverse ÷ point` | `563/atom.py:251` |
| كلفة الانزلاق | `slippage_cost = adverse × vpu × volume` | `563/atom.py:252` |
| الانزلاق المعاكس | `adverse = max(0, signed ÷ point)` | `560/atom.py:116` |
| نسبة الرفض | `reject_rate = rejects ÷ total` | `560/atom.py:142` |
| متوسط الانزلاق | `adverse_mean = Σ adverse ÷ عدد التنفيذات` | `560/atom.py:156` |
| **انحراف المرجع** | `dev = (mt5_price − ctrader_price) ÷ point` | `582/atom.py:50` |
| نافذة المواءمة | `gap = |a − b|` و`gap > alignment_window_s ⇒ UNALIGNED` | `582/atom.py:50` |
| حكم الانحراف | `|dev| > max_deviation_points ⇒ DIVERGED` وإلّا `SYNCED` | `582/atom.py:50` |
| السبريد عند البوّابة | `spread_points ≤ max_spread_points` | `552` · `manifest` |
| عمر الأمر | `الأمر أقدم من InpMaxCmdAgeSec ⇒ EXPIRED` | `mt5/QUANT_NQ.mq5` |
