---
id: refunds-and-credits
title: "Refunds and credits"
title_ar: "الاسترداد والرصيد"
audience: customer
verticals: [food, grocery, pharmacy, parcel]
languages: [en, ar]
version: 1
effective_from: "2026-11-01"
fictional: true
sections:
  - id: REF-01
    title: "What can be refunded"
    title_ar: "ما الذي يمكن استرداده"
    visibility: public
    tags: [eligibility]
    rule_keys: []
  - id: REF-02
    title: "Reporting windows"
    title_ar: "مهل الإبلاغ"
    visibility: public
    tags: [windows, edge-case]
    rule_keys: [refunds.windows_hours, payments.duplicate_charge.window_days, parcels.damage_window_hours, parcels.claim_window_days]
  - id: REF-03
    title: "How the refund amount is calculated"
    title_ar: "كيف يُحسب مبلغ الاسترداد"
    visibility: public
    tags: [calculation, edge-case]
    rule_keys: [refunds.full_refund_conversion_pct]
  - id: REF-04
    title: "Where the money goes and how long it takes"
    title_ar: "إلى أين يعود المبلغ وكم يستغرق"
    visibility: public
    tags: [destination, edge-case]
    rule_keys: [refunds.timing, credit_wallet.max_balance_qar, credit_wallet.returned_value_min_validity_days]
  - id: REF-05
    title: "Approval limits and repeat claims"
    title_ar: "حدود الموافقة وتكرار المطالبات"
    visibility: internal
    tags: [approval, abuse, edge-case]
    rule_keys: [refunds.approval_limits_qar, refunds.new_account, refunds.repeat_claims, refunds.trust_review]
  - id: REF-06
    title: "Photo evidence"
    title_ar: "الإثبات بالصور"
    visibility: public
    tags: [evidence, edge-case]
    rule_keys: [refunds.photo]
  - id: REF-07
    title: "Goodwill credit"
    title_ar: "رصيد الترضية"
    visibility: public
    tags: [credit, edge-case]
    rule_keys: [goodwill, compensation_credit_cap_per_order_qar]
  - id: REF-08
    title: "Credit wallet rules"
    title_ar: "قواعد محفظة الرصيد"
    visibility: public
    tags: [credit]
    rule_keys: [credit_wallet.max_balance_qar, goodwill.expiry_days]
  - id: REF-09
    title: "Worked examples"
    title_ar: "أمثلة محسوبة"
    visibility: public
    tags: [examples, edge-case]
    rule_keys: []
---

# Refunds and credits

<div lang="ar" dir="rtl">

# الاسترداد والرصيد

</div>

## REF-01: What can be refunded

A customer can ask for a refund when:

- An item is missing, wrong, damaged, spoiled or expired.
- The order did not arrive, or the merchant or Jalboot cancelled it.
- The same order was charged twice.
- A food quality complaint meets WRG-05.

No refund applies when:

- The customer changed their mind after delivery.
- The issue is taste or portion size and the item matched its description.
- Delivery failed for a reason on the customer's side (LAT-05), or the customer entered the wrong address.
- The report came after the window in REF-02.

<div lang="ar" dir="rtl">

### ما الذي يمكن استرداده

يحق للعميل طلب الاسترداد في الحالات الآتية:

- إذا كان أحد الأصناف ناقصًا أو خاطئًا أو تالفًا أو فاسدًا أو منتهي الصلاحية.
- إذا لم يصل الطلب، أو ألغاه التاجر أو جالبوت.
- إذا خُصم مبلغ الطلب نفسه مرتين.
- إذا استوفت شكوى جودة الطعام شروط WRG-05.

ولا يُرد المبلغ في الحالات الآتية:

- إذا غيّر العميل رأيه بعد التسليم.
- إذا تعلق الأمر بالمذاق أو حجم الحصة وكان الصنف مطابقًا لوصفه.
- إذا تعذر التسليم لسبب يعود إلى العميل (LAT-05)، أو أدخل العميل عنوانًا خاطئًا.
- إذا ورد البلاغ بعد انتهاء المهلة المحددة في REF-02.

</div>

## REF-02: Reporting windows

Unless the table says otherwise, the window starts at `delivered_at`.

| Issue | Window |
|---|---|
| Restaurant food: missing, wrong or damaged | 24 hours |
| Restaurant food: quality other than temperature | 24 hours |
| Restaurant food: arrived at the wrong temperature | 2 hours |
| Grocery: shelf-stable items | 48 hours |
| Grocery: chilled or frozen items | 6 hours |
| Expired product, grocery or pharmacy | 7 days (168 hours) |
| Pharmacy: wrong or damaged product | 48 hours |
| Pharmacy: cold-chain product | 2 hours |
| Allergen mismatch | 72 hours |
| Foreign object in food | 72 hours |
| Broken tamper seal | 24 hours |
| Suspected foodborne illness | 7 days (168 hours) |
| Marked delivered but not received | 24 hours |
| Late delivery credit | 24 hours |
| Parcel damage | 72 hours |
| Lost parcel | 14 days after `promised_at` |
| Duplicate charge | 30 days after the charge date |

When two rows fit, use the more specific row. An expired yogurt is an expired product (7 days), not a chilled item (6 hours), as long as the date on the label shows it had expired at delivery.

<div lang="ar" dir="rtl">

### مهل الإبلاغ

تبدأ المهلة من لحظة `delivered_at` ما لم يذكر الجدول غير ذلك.

| المشكلة | المهلة |
|---|---|
| طعام المطاعم: صنف ناقص أو خاطئ أو تالف | 24 ساعة |
| طعام المطاعم: الجودة في غير ما يتعلق بالحرارة | 24 ساعة |
| طعام المطاعم: وصل بدرجة حرارة غير مناسبة | ساعتان (2) |
| البقالة: الأصناف التي تُحفظ على الرف | 48 ساعة |
| البقالة: الأصناف المبردة أو المجمدة | 6 ساعات |
| منتج منتهي الصلاحية، من البقالة أو الصيدلية | 7 أيام (168 ساعة) |
| الصيدلية: منتج خاطئ أو تالف | 48 ساعة |
| الصيدلية: منتج يتطلب حفظًا مبردًا | ساعتان (2) |
| عدم تطابق معلومات الحساسية | 72 ساعة |
| جسم غريب في الطعام | 72 ساعة |
| ختم أمان مكسور | 24 ساعة |
| اشتباه في تسمم غذائي | 7 أيام (168 ساعة) |
| طلب مسجل كمسلَّم ولم يصل | 24 ساعة |
| رصيد التأخير | 24 ساعة |
| تلف الطرد | 72 ساعة |
| فقدان الطرد | 14 يومًا بعد `promised_at` |
| خصم مكرر | 30 يومًا بعد تاريخ الخصم |

وإذا انطبق صفان على الحالة، يؤخذ بالأكثر تحديدًا. فعلبة الزبادي منتهية الصلاحية تُعامل معاملة المنتج منتهي الصلاحية (7 أيام) لا الصنف المبرد (6 ساعات)، ما دام التاريخ المدون عليها يثبت انتهاء صلاحيتها وقت التسليم.

</div>

## REF-03: How the refund amount is calculated

1. **Item refund:** net item price (GEN-03) multiplied by the affected quantity.
2. **70% rule:** if the listed prices of all affected items reach 70% or more of the item subtotal, treat the claim as a full-order refund. Exactly 70% converts. 69.99% does not. Quality claims (WRG-05), missed modifiers (WRG-02) and rejected grocery substitutes (GRC-04) do not count toward the 70%.
3. **Delivery fee:** refunded only when nothing was delivered, on a full-order refund, or in the top late tier (LAT-01).
4. **Service, small order, peak and weather fees:** refunded only on a full-order refund or when nothing was delivered.
5. **Tip:** refunded only when nothing was delivered. If the wrong order arrived, the driver still completed a delivery, so the tip stays with the driver.
6. **Cap:** refunds on one order can never exceed the amount paid. Parcel cover payouts (PCL-03) are compensation, not refunds, so this cap does not limit them.

<div lang="ar" dir="rtl">

### كيف يُحسب مبلغ الاسترداد

1. **استرداد الصنف:** صافي سعر الصنف (GEN-03) مضروبًا في الكمية المتأثرة.
2. **قاعدة 70%:** إذا بلغت الأسعار المعروضة لجميع الأصناف المتأثرة 70% أو أكثر من إجمالي الأصناف، تُعامل المطالبة معاملة الاسترداد الكامل للطلب. فبلوغ 70% تمامًا يكفي للتحويل، أما 69.99% فلا يكفي. ولا تدخل في هذه النسبة شكاوى الجودة (WRG-05) ولا الخيارات التي لم تُنفذ (WRG-02) ولا البدائل المرفوضة في البقالة (GRC-04).
3. **رسوم التوصيل:** تُرد فقط إذا لم يُسلَّم شيء، أو عند الاسترداد الكامل، أو في أعلى شريحة من شرائح التأخير (LAT-01).
4. **رسوم الخدمة والطلب الصغير والذروة والطقس:** تُرد فقط عند الاسترداد الكامل أو إذا لم يُسلَّم شيء.
5. **الإكرامية:** تُرد فقط إذا لم يُسلَّم شيء. فإذا وصل طلب خاطئ، يكون المندوب قد أتم التوصيل، فتبقى الإكرامية له.
6. **الحد الأقصى:** لا يجوز أن يتجاوز مجموع المبالغ المردودة في الطلب الواحد المبلغ المدفوع. أما تعويض تغطية الطرود (PCL-03) فهو تعويض لا استرداد، فلا يخضع لهذا الحد.

</div>

## REF-04: Where the money goes and how long it takes

- **Card or mobile wallet:** back to the same method, up to 7 business days. The customer can choose refund credit instead, which arrives within 15 minutes.
- **Cash on delivery:** refund credit only, within 15 minutes. Jalboot never returns physical cash.
- **Mixed payment:** return money in this order: card, mobile wallet or cash part first, then refund credit, then goodwill credit, then points.
- **Returned goodwill credit and points:** the new expiry is the later of the original expiry and 30 days after the return date.
- **Wallet limit:** if refund credit would push the balance over QAR 2,000, the excess goes to the original card or mobile wallet. On a cash order, a support agent handles the excess.
- A refund never goes to a different card.

<div lang="ar" dir="rtl">

### إلى أين يعود المبلغ وكم يستغرق

- **البطاقة أو المحفظة الإلكترونية:** يعود المبلغ إلى الوسيلة نفسها خلال مدة أقصاها 7 أيام عمل. ويمكن للعميل أن يختار بدلًا من ذلك رصيد الاسترداد الذي يصل خلال 15 دقيقة.
- **الدفع نقدًا عند الاستلام:** يكون الرد في صورة رصيد استرداد فقط خلال 15 دقيقة، ولا تعيد جالبوت النقد مطلقًا.
- **الدفع المختلط:** يُرد المبلغ بالترتيب الآتي: جزء البطاقة أو المحفظة الإلكترونية أو النقد أولًا، ثم رصيد الاسترداد، ثم رصيد الترضية، ثم النقاط.
- **رصيد الترضية والنقاط المعادة:** تكون صلاحيتها الجديدة هي الأبعد من بين الصلاحية الأصلية و30 يومًا من تاريخ الإعادة.
- **حد المحفظة:** إذا كان رصيد الاسترداد سيرفع الرصيد فوق 2,000 ر.ق، يعود الفائض إلى البطاقة أو المحفظة الإلكترونية الأصلية. أما في الطلب النقدي فيتولى موظف الدعم معالجة الفائض.
- لا يُرد المبلغ إلى بطاقة أخرى في أي حال.

</div>

## REF-05: Approval limits and repeat claims

Internal rule. Do not quote these numbers to customers.

Who may approve depends on the total value on the order: refunds already paid, plus compensation credit already issued, plus the new amount.

| Level | Total value on the order |
|---|---|
| Automated support | Up to QAR 50 |
| Support agent | Up to QAR 300 |
| Supervisor | Up to QAR 1,500 |
| Finance lead | Above QAR 1,500 |

An amount exactly at a limit stays at that level. For an account younger than 7 days, the automated limit is QAR 25.

**Always a person, at any amount:** pharmacy refunds, safety cases, parcel claims and not-received cases that have proof of delivery.

**Confirmed duplicate charge (PAY-03):** automated support can approve up to QAR 300. This is separate from the limits above, because the money was never owed.

**Not received (LAT-04):** only 2 refunds are allowed in the rolling 90 days. The next case goes to a Trust review, even if there is no proof of delivery.

**Reused photo (REF-06):** a photo already used on another claim sends the case to a Trust review.

**Repeat claims:** send the claim to a support agent if the customer already has 3 or more approved claims in the rolling 30 days, or if this claim would take approved refunds in the rolling 30 days above QAR 300.

**Trust review:** with 8 or more approved claims in the rolling 90 days, pause refunds on the account and open a Trust review. It takes up to 5 business days.

**Not counted as claims:** cancellations by the merchant or Jalboot, confirmed duplicate charges, late credit and safety cases. A declined claim is not counted either. Safety cases continue during a Trust review.

<div lang="ar" dir="rtl">

### حدود الموافقة وتكرار المطالبات

قاعدة داخلية: لا تُذكر هذه الأرقام للعملاء.

تتوقف صلاحية الموافقة على إجمالي القيمة في الطلب، أي ما سبق رده، مضافًا إليه ما صدر من رصيد تعويضي، ثم المبلغ الجديد.

| المستوى | إجمالي القيمة في الطلب |
|---|---|
| الدعم الآلي | حتى 50 ر.ق |
| موظف الدعم | حتى 300 ر.ق |
| المشرف | حتى 1,500 ر.ق |
| مسؤول الشؤون المالية | أكثر من 1,500 ر.ق |

المبلغ الذي يساوي الحد تمامًا يبقى ضمن ذلك المستوى. وإذا كان عمر الحساب أقل من 7 أيام، يكون حد الدعم الآلي 25 ر.ق.

**ما يتولاه موظف دائمًا مهما كان المبلغ:** عمليات استرداد الصيدلية، وحالات السلامة، ومطالبات الطرود، وحالات عدم الاستلام التي يوجد فيها إثبات تسليم.

**الخصم المكرر المؤكد (PAY-03):** يمكن للدعم الآلي الموافقة على ما يصل إلى 300 ر.ق. وهذا الحد منفصل عن الحدود أعلاه، لأن المبلغ لم يكن مستحقًا أصلًا.

**عدم الاستلام (LAT-04):** لا يُسمح إلا بعمليتي استرداد (2) خلال 90 يومًا متحركة، وتُحال الحالة التالية إلى مراجعة فريق الثقة حتى لو لم يوجد إثبات تسليم.

**الصورة المعاد استخدامها (REF-06):** إذا كانت الصورة قد استُخدمت في مطالبة أخرى، تُحال الحالة إلى مراجعة فريق الثقة.

**تكرار المطالبات:** تُحال المطالبة إلى موظف الدعم إذا كان لدى العميل 3 مطالبات معتمدة أو أكثر خلال 30 يومًا متحركة، أو إذا كانت هذه المطالبة سترفع مجموع المبالغ المعتمدة في الفترة نفسها فوق 300 ر.ق.

**مراجعة فريق الثقة:** عند وجود 8 مطالبات معتمدة أو أكثر خلال 90 يومًا متحركة، يُوقف الاسترداد على الحساب وتُفتح مراجعة يتولاها فريق الثقة، وتستغرق مدة أقصاها 5 أيام عمل.

**ما لا يُحسب مطالبة:** عمليات الإلغاء من جانب التاجر أو جالبوت، والخصم المكرر المؤكد، ورصيد التأخير، وحالات السلامة. ولا تُحسب كذلك المطالبة المرفوضة. وتستمر معالجة حالات السلامة أثناء مراجعة فريق الثقة.

</div>

## REF-06: Photo evidence

| Claim | Photo |
|---|---|
| Wrong, damaged or spoiled item, or a quality claim, worth more than QAR 30 | Required |
| The same claims at QAR 30 or less | Not required |
| Foreign object, expired product, broken seal, parcel damage | Always required |
| Missing item, order not delivered, duplicate charge, late delivery | Not required |

Claim value is the total net amount the customer asks for in that report, not the listed price.

The report must be made inside the window. The photo can follow up to 24 hours after the report, even if the window has ended by then. With no photo after 24 hours, the claim closes. A photo already used on another claim is not accepted, and a person reviews the case.

<div lang="ar" dir="rtl">

### الإثبات بالصور

| المطالبة | الصورة |
|---|---|
| صنف خاطئ أو تالف أو فاسد، أو شكوى جودة، بقيمة تزيد على 30 ر.ق | مطلوبة |
| المطالبات نفسها بقيمة 30 ر.ق أو أقل | غير مطلوبة |
| جسم غريب، أو منتج منتهي الصلاحية، أو ختم مكسور، أو طرد تالف | مطلوبة دائمًا |
| صنف ناقص، أو طلب لم يُسلَّم، أو خصم مكرر، أو تأخر في التوصيل | غير مطلوبة |

وقيمة المطالبة هي إجمالي المبلغ الصافي الذي يطلبه العميل في ذلك البلاغ، لا السعر المعروض.

يجب تقديم البلاغ داخل المهلة، ويجوز إرسال الصورة خلال 24 ساعة من البلاغ حتى لو انتهت المهلة في هذه الأثناء. فإذا مرت 24 ساعة دون صورة، تُغلق المطالبة. وإذا كانت الصورة قد استُخدمت في مطالبة أخرى، فلا تُقبل ويراجع موظف الحالة.

</div>

## REF-07: Goodwill credit

Goodwill credit is a gesture, not a right.

- Automated support can give up to QAR 10 on an order. A support agent can give more, within the caps below.
- All compensation credit on one order, of every type, cannot exceed QAR 30. Example: if a QAR 20 late credit is issued, at most QAR 10 of goodwill credit can follow.
- A customer can receive at most QAR 60 of goodwill credit under this section in the rolling 30 days. Late credit, expired item credit, cancellation credit and referral rewards do not count toward this QAR 60.
- Goodwill credit is never added to a full-order refund.
- Automated support cannot give goodwill credit on a claim outside its window. A support agent can.
- No goodwill credit during a Trust review.
- Goodwill credit expires 90 days after it is issued.

<div lang="ar" dir="rtl">

### رصيد الترضية

رصيد الترضية لفتة من الشركة، وليس حقًا للعميل.

- يمكن للدعم الآلي منح ما يصل إلى 10 ر.ق في الطلب الواحد، ويمكن لموظف الدعم منح أكثر من ذلك في حدود السقوف أدناه.
- لا يجوز أن يتجاوز مجموع الرصيد التعويضي في الطلب الواحد، بجميع أنواعه، 30 ر.ق. فإذا صدر رصيد تأخير بقيمة 20 ر.ق مثلًا، لا يتبقى لرصيد الترضية سوى 10 ر.ق على الأكثر.
- الحد الأقصى لما يحصل عليه العميل من رصيد الترضية بموجب هذا القسم 60 ر.ق خلال 30 يومًا متحركة، ولا يدخل في هذا الحد رصيد التأخير ورصيد الصنف منتهي الصلاحية ورصيد الإلغاء ومكافآت الإحالة.
- لا يضاف رصيد الترضية إلى الاسترداد الكامل للطلب في أي حال.
- لا يمنح الدعم الآلي رصيد ترضية عن مطالبة خارج مهلتها، ويجوز ذلك لموظف الدعم.
- لا يُمنح رصيد ترضية أثناء مراجعة فريق الثقة.
- تنتهي صلاحية رصيد الترضية بعد 90 يومًا من إصداره.

</div>

## REF-08: Credit wallet rules

Jalboot Credit has two types:

- **Refund credit:** money returned from an order. It does not expire.
- **Goodwill credit:** includes late credit, expired item credit, cancellation credit and referral rewards. It expires after 90 days.

Checkout uses goodwill credit first, soonest expiry first, then refund credit. The wallet balance cannot exceed QAR 2,000. Credit can pay for items and fees, but not for tips or Plus membership. Credit cannot be transferred to another account. It cannot be withdrawn, except refund credit when an account is deleted (PRV-04).

<div lang="ar" dir="rtl">

### قواعد محفظة الرصيد

لرصيد جالبوت نوعان:

- **رصيد الاسترداد:** الأموال المعادة من الطلبات، ولا تنتهي صلاحيته.
- **رصيد الترضية:** يشمل رصيد التأخير ورصيد الصنف منتهي الصلاحية ورصيد الإلغاء ومكافآت الإحالة، وتنتهي صلاحيته بعد 90 يومًا.

عند الدفع يُستخدم رصيد الترضية أولًا، ويبدأ بالأقرب انتهاءً، ثم رصيد الاسترداد. ولا يجوز أن يتجاوز رصيد المحفظة 2,000 ر.ق. ويمكن استخدام الرصيد لسداد قيمة الأصناف والرسوم، لا الإكرامية ولا اشتراك Plus. ولا يُنقل الرصيد إلى حساب آخر، ولا يُسحب، إلا رصيد الاسترداد عند حذف الحساب (PRV-04).

</div>

## REF-09: Worked examples

Base order for examples 1 and 2: burger QAR 40, fries QAR 20, juice QAR 40, so the item subtotal is QAR 100. Code takes 20% (QAR 20). Delivery fee QAR 8, service fee QAR 3, tip QAR 5. Amount paid: QAR 96.

1. **Fries missing.** Net price is 20 x (1 - 20/100) = QAR 16.00. Refund QAR 16.00. Fees and tip stay. No photo is needed.
2. **Burger and juice wrong.** Affected listed prices are QAR 80 of QAR 100, which is 80%, so the 70% rule applies. Full-order refund: 96 - 5 tip = QAR 91.00.
3. **Small order, very late.** Item subtotal QAR 20, delivery fee QAR 5, delivered 65 minutes late. Tier credit is QAR 20, capped at 30% of QAR 20 = QAR 6.00. Delivery fee QAR 5 is refunded as well. Total value QAR 11.00.
4. **Mixed payment.** Paid QAR 50 by card and QAR 30 with refund credit. A QAR 60 refund returns QAR 50 to the card and QAR 10 as refund credit.
5. **Credit already issued.** On the base order, a QAR 10 late credit was issued. The whole order then turns out to be someone else's. Full-order refund: 96 - 5 - 10 = QAR 81.00.

<div lang="ar" dir="rtl">

### أمثلة محسوبة

الطلب الأساسي للمثالين 1 و2: برجر 40 ر.ق، وبطاطس 20 ر.ق، وعصير 40 ر.ق، فيكون إجمالي الأصناف 100 ر.ق. ويخصم الرمز 20% (20 ر.ق). رسوم التوصيل 8 ر.ق، ورسوم الخدمة 3 ر.ق، والإكرامية 5 ر.ق. المبلغ المدفوع 96 ر.ق.

1. **البطاطس ناقصة.** صافي السعر 20 x (1 - 20/100) = 16.00 ر.ق، فيُرد 16.00 ر.ق وتبقى الرسوم والإكرامية. ولا يلزم إرفاق صورة.
2. **البرجر والعصير خاطئان.** الأسعار المتأثرة 80 ر.ق من 100 ر.ق، أي 80%، فتنطبق قاعدة 70%. الاسترداد الكامل: 96 - 5 إكرامية = 91.00 ر.ق.
3. **طلب صغير تأخر كثيرًا.** إجمالي الأصناف 20 ر.ق، ورسوم التوصيل 5 ر.ق، وتأخر التسليم 65 دقيقة. رصيد الشريحة 20 ر.ق، لكنه لا يتجاوز 30% من 20 ر.ق، أي 6.00 ر.ق. وتُرد رسوم التوصيل البالغة 5 ر.ق كذلك، فتكون القيمة الإجمالية 11.00 ر.ق.
4. **دفع مختلط.** دُفع 50 ر.ق بالبطاقة و30 ر.ق من رصيد الاسترداد. عند رد 60 ر.ق، يعود 50 ر.ق إلى البطاقة و10 ر.ق في صورة رصيد استرداد.
5. **رصيد صدر سابقًا.** صدر عن الطلب الأساسي رصيد تأخير بقيمة 10 ر.ق، ثم تبيّن أن الطلب كله يخص عميلًا آخر. الاسترداد الكامل: 96 - 5 - 10 = 81.00 ر.ق.

</div>
