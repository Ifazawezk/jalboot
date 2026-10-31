---
id: pharmacy-orders-and-prescriptions
title: "Pharmacy orders and prescriptions"
title_ar: "طلبات الصيدلية والوصفات الطبية"
audience: customer
verticals: [pharmacy]
languages: [en, ar]
version: 1
effective_from: "2026-11-01"
fictional: true
sections:
  - id: PHR-01
    title: "What support can and cannot do"
    title_ar: "ما يمكن للدعم فعله وما لا يمكنه"
    visibility: public
    tags: [pharmacy, safety, boundaries]
    rule_keys: []
  - id: PHR-02
    title: "Prescriptions"
    title_ar: "الوصفات الطبية"
    visibility: public
    tags: [pharmacy, prescriptions, edge-case]
    rule_keys: [pharmacy.min_age, pharmacy.prescription_max_age_days, pharmacy.prescription_review_minutes, pharmacy.prescription_reuploads]
  - id: PHR-03
    title: "Substitutions and quantity limits"
    title_ar: "البدائل وحدود الكميات"
    visibility: public
    tags: [pharmacy, edge-case]
    rule_keys: [pharmacy.substitution_consent_minutes, pharmacy.otc_max_packs_per_item]
  - id: PHR-04
    title: "Delivery and handover"
    title_ar: "التوصيل والتسليم"
    visibility: public
    tags: [pharmacy, delivery, edge-case]
    rule_keys: [pharmacy.min_age, pharmacy.cold_chain_max_delivery_minutes]
  - id: PHR-05
    title: "Returns and refunds"
    title_ar: "الإرجاع والاسترداد"
    visibility: public
    tags: [pharmacy, refunds, edge-case]
    rule_keys: [refunds.windows_hours.pharmacy_standard, refunds.windows_hours.pharmacy_cold_chain, refunds.windows_hours.expired_product, pharmacy.min_shelf_life_days]
---

# Pharmacy orders and prescriptions

<div lang="ar" dir="rtl">

# طلبات الصيدلية والوصفات الطبية

</div>

## PHR-01: What support can and cannot do

Pharmacy orders are filled by partner pharmacies, each with a pharmacist on duty. Jalboot support handles orders, payments and delivery only.

Support does not give medical advice. It does not comment on doses, whether a product suits someone, how products interact, side effects, or which product to use instead. For those questions, the customer should use the "Ask a pharmacist" option in the app or speak to a doctor.

If a customer describes a reaction, a possible wrong dose, or anything urgent, stop the order flow. Tell them to contact local emergency services or a doctor, then follow SAF-02.

**Product classes:**

| Class | Rule |
|---|---|
| Over the counter | Sold without a prescription, within the limits in PHR-03 |
| Prescription | Needs an approved prescription (PHR-02) |
| Cold chain | Needs refrigeration. Can be either class above (PHR-04) |
| Controlled | Not sold through Jalboot |

<div lang="ar" dir="rtl">

### ما يمكن للدعم فعله وما لا يمكنه

تتولى صيدليات شريكة تجهيز طلبات الصيدلية، ويوجد في كل منها صيدلي مناوب. ويقتصر دور دعم جالبوت على الطلبات والمدفوعات والتوصيل.

ولا يقدم الدعم أي نصيحة طبية، فلا يعلق على الجرعات أو مدى ملاءمة منتج ما لشخص معين أو تداخل المنتجات أو الأعراض الجانبية أو المنتج البديل. ولهذه الأسئلة يمكن للعميل استخدام خيار "اسأل الصيدلي" في التطبيق أو مراجعة الطبيب.

وإذا وصف العميل تفاعلًا سلبيًا أو احتمال تناول جرعة خاطئة أو أي أمر عاجل، يتوقف مسار الطلب، ويُطلب منه التواصل مع خدمات الطوارئ المحلية أو الطبيب، ثم يُتبع SAF-02.

**فئات المنتجات:**

| الفئة | القاعدة |
|---|---|
| دون وصفة | تُباع دون وصفة طبية في حدود PHR-03 |
| بوصفة طبية | تتطلب وصفة معتمدة (PHR-02) |
| سلسلة التبريد | تتطلب حفظًا مبردًا، وقد تكون من أي من الفئتين السابقتين (PHR-04) |
| خاضعة للرقابة | لا تُباع عبر جالبوت |

</div>

## PHR-02: Prescriptions

- The customer must be at least 18 years old to order prescription items.
- The prescription must be dated within the last 30 days at upload.
- The patient name must match the account holder or a dependant saved on the account.
- A pharmacist reviews it within 30 minutes during pharmacy opening hours.
- Up to 2 re-uploads are allowed on one order if an image is unclear. After that, the order is cancelled.
- A prescription upload covers one order. A repeat supply needs a new upload.

**If the prescription is rejected,** the customer gets a full refund including all fees and tip. There is no cancellation charge and no cancellation credit.

Only a pharmacist can approve or reject a prescription. Support cannot change, approve or override that decision.

<div lang="ar" dir="rtl">

### الوصفات الطبية

- يجب ألا يقل عمر العميل عن 18 عامًا لطلب الأصناف التي تُصرف بوصفة طبية.
- يجب أن يكون تاريخ الوصفة ضمن آخر 30 يومًا عند رفعها.
- يجب أن يطابق اسم المريض اسم صاحب الحساب أو أحد المعالين المسجلين في الحساب.
- يراجع الصيدلي الوصفة خلال 30 دقيقة أثناء ساعات عمل الصيدلية.
- يُسمح بإعادة الرفع مرتين (2) كحد أقصى في الطلب الواحد إذا كانت الصورة غير واضحة، ثم يُلغى الطلب بعد ذلك.
- يغطي رفع الوصفة طلبًا واحدًا، ويحتاج تكرار الصرف إلى رفعها من جديد.

**إذا رُفضت الوصفة،** يحصل العميل على استرداد كامل يشمل جميع الرسوم والإكرامية، دون رسوم إلغاء ودون رصيد إلغاء.

ولا يعتمد الوصفة أو يرفضها إلا الصيدلي، ولا يستطيع الدعم تعديل هذا القرار أو اعتماده أو تجاوزه.

</div>

## PHR-03: Substitutions and quantity limits

- Pharmacy items are never substituted automatically, whatever the customer's grocery settings say.
- Only a pharmacist can propose an alternative. The customer must agree in the app within 15 minutes. Without agreement, the item is removed and refunded.
- Support never suggests an alternative product.
- Over-the-counter items are limited to 3 packs per product per order. A pharmacist can set a lower limit. Support cannot raise it.
- Jalboot does not process insurance claims.

<div lang="ar" dir="rtl">

### البدائل وحدود الكميات

- لا تُستبدل أصناف الصيدلية تلقائيًا أبدًا، مهما كانت إعدادات البقالة لدى العميل.
- لا يقترح البديل إلا الصيدلي، وعلى العميل الموافقة عبر التطبيق خلال 15 دقيقة، وإلا أُزيل الصنف ورُدت قيمته.
- لا يقترح الدعم أي منتج بديل في أي حال.
- تقتصر الأصناف التي تُباع دون وصفة على 3 عبوات لكل منتج في الطلب الواحد. ويجوز للصيدلي تحديد عدد أقل، ولا يستطيع الدعم زيادته.
- لا تعالج جالبوت مطالبات التأمين.

</div>

## PHR-04: Delivery and handover

- **Prescription items:** handed in person to someone aged 18 or over, with a handover code. They are never left at the door.
- **Over-the-counter items:** can be left at the door if the customer chose this, unless they are cold chain.
- **Cold-chain items:** Zones A, B and C only. Delivered within 60 minutes of pickup, in a cooled bag, and in person.
- **Zone D:** pharmacy delivery is available, but not for cold-chain items.

If nobody suitable is there to receive the order, LAT-05 applies.

<div lang="ar" dir="rtl">

### التوصيل والتسليم

- **الأصناف التي تُصرف بوصفة:** تُسلَّم يدًا بيد لشخص لا يقل عمره عن 18 عامًا مع رمز تسليم، ولا تُترك عند الباب.
- **الأصناف التي تُباع دون وصفة:** يمكن تركها عند الباب إذا اختار العميل ذلك، ما لم تكن من أصناف سلسلة التبريد.
- **أصناف سلسلة التبريد:** في المناطق A وB وC فقط، وتُسلَّم خلال 60 دقيقة من الاستلام من الصيدلية، في حقيبة مبردة ويدًا بيد.
- **المنطقة D:** يتوفر فيها توصيل الصيدلية، لكن دون أصناف سلسلة التبريد.

وإذا لم يوجد من يصلح لاستلام الطلب، ينطبق LAT-05.

</div>

## PHR-05: Returns and refunds

Medicines cannot be returned for a change of mind, or because the customer no longer needs them, or once opened. The only exceptions are below.

| Reason | Window |
|---|---|
| Wrong product or damaged seal | 48 hours |
| Cold-chain product problem | 2 hours |
| Expired at delivery | 7 days (168 hours) |
| Less than 90 days of shelf life left at delivery | 48 hours |
| Recall notice from the pharmacy | Any time during the notice |

- A support agent handles every pharmacy refund, with a pharmacist check, at any amount. Automated support does not approve them, even at low value.
- The customer should not use a wrong product. They should keep it safe until the pharmacy arranges collection.
- The expired item credit in GRC-05 is for grocery orders only and does not apply here.

<div lang="ar" dir="rtl">

### الإرجاع والاسترداد

لا تُعاد الأدوية بسبب تغيّر رأي العميل، أو لعدم حاجته إليها، أو بعد فتحها. والاستثناءات الوحيدة مذكورة أدناه.

| السبب | المهلة |
|---|---|
| منتج خاطئ أو ختم تالف | 48 ساعة |
| مشكلة في منتج من سلسلة التبريد | ساعتان (2) |
| منتهي الصلاحية عند التسليم | 7 أيام (168 ساعة) |
| بقي من صلاحيته أقل من 90 يومًا عند التسليم | 48 ساعة |
| إشعار سحب من الصيدلية | في أي وقت أثناء سريان الإشعار |

- يتولى موظف الدعم كل عملية استرداد في الصيدلية، بعد تحقق الصيدلي، مهما كان المبلغ. ولا يوافق عليها الدعم الآلي حتى لو كانت قيمتها قليلة.
- على العميل عدم استخدام المنتج الخاطئ، والاحتفاظ به في مكان آمن حتى ترتب الصيدلية استلامه.
- رصيد الصنف منتهي الصلاحية الوارد في GRC-05 خاص بطلبات البقالة ولا ينطبق هنا.

</div>
