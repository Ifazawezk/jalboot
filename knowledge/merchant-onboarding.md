---
id: merchant-onboarding
title: "Merchant onboarding"
title_ar: "انضمام التجار"
audience: merchant
verticals: [food, grocery, pharmacy]
languages: [en, ar]
version: 1
effective_from: "2026-11-01"
fictional: true
sections:
  - id: MOB-01
    title: "Who can join and what is needed"
    title_ar: "من يمكنه الانضمام وما المطلوب"
    visibility: public
    tags: [merchants, onboarding]
    rule_keys: [merchant_onboarding.licence_min_remaining_days]
  - id: MOB-02
    title: "Onboarding steps and fees"
    title_ar: "خطوات الانضمام والرسوم"
    visibility: public
    tags: [merchants, onboarding, fees]
    rule_keys: [merchant_onboarding.document_review_business_days, merchant_onboarding.site_check_business_days, merchant_onboarding.go_live_target_business_days, merchant_onboarding.activation_fee_qar, merchant_onboarding.device_deposit_qar, merchant_onboarding.device_deposit_return_days]
  - id: MOB-03
    title: "Commission and contract"
    title_ar: "العمولة والعقد"
    visibility: public
    tags: [merchants, contract]
    rule_keys: [merchant_onboarding.commission_pct, merchant_onboarding.min_term_months, merchant_onboarding.termination_notice_days, merchant_onboarding.probation_days]
  - id: MOB-04
    title: "Listing and performance standards"
    title_ar: "معايير العرض والأداء"
    visibility: public
    tags: [merchants, performance, edge-case]
    rule_keys: [merchant_onboarding.max_price_markup_pct, merchant_onboarding.acceptance_timeout_minutes, merchant_onboarding.performance, merchant_onboarding.licence_expiry_notice_days]
---

# Merchant onboarding

<div lang="ar" dir="rtl">

# انضمام التجار

</div>

## MOB-01: Who can join and what is needed

Restaurants, grocery stores and pharmacies in Zones A to D can apply. Food merchants deliver only to Zones A to C. These are Jalboot requirements:

- A trade licence with at least 60 days left before it expires.
- A bank account in the same business name.
- Food and grocery: a current food safety certificate.
- Pharmacies: a current pharmacy licence and a pharmacist on duty during all opening hours.
- Full menu or product list with prices and photos.
- Food: allergen details for every item.

Controlled medicines cannot be listed.

<div lang="ar" dir="rtl">

### من يمكنه الانضمام وما المطلوب

يمكن للمطاعم ومحال البقالة والصيدليات في المناطق من A إلى D التقدم بطلب. ويقتصر توصيل تجار الطعام على المناطق من A إلى C. وفيما يلي متطلبات جالبوت:

- رخصة تجارية بقي على انتهائها 60 يومًا على الأقل.
- حساب مصرفي باسم النشاط التجاري نفسه.
- الطعام والبقالة: شهادة سارية لسلامة الغذاء.
- الصيدليات: رخصة صيدلية سارية ووجود صيدلي مناوب طوال ساعات العمل.
- قائمة كاملة بالأصناف والأسعار والصور.
- الطعام: تفاصيل مسببات الحساسية لكل صنف.

ولا يجوز عرض الأدوية الخاضعة للرقابة.

</div>

## MOB-02: Onboarding steps and fees

| Step | Target |
|---|---|
| Document review | 3 business days |
| Site and quality check | 5 business days |
| Go live, from a complete application | 10 business days |

The clock starts when all documents are in. A missing document pauses it.

- **Activation fee:** QAR 500, paid on signing. It is refunded in full if Jalboot rejects the merchant at the site check. It is not refunded after go-live.
- **Device deposit:** QAR 300 for the order tablet. It is returned within 30 days after the device comes back in working order.

<div lang="ar" dir="rtl">

### خطوات الانضمام والرسوم

| الخطوة | المدة المستهدفة |
|---|---|
| مراجعة المستندات | 3 أيام عمل |
| الفحص الميداني وفحص الجودة | 5 أيام عمل |
| بدء التشغيل من تاريخ اكتمال الطلب | 10 أيام عمل |

تبدأ المدة عند اكتمال جميع المستندات، ويوقفها أي مستند ناقص.

- **رسم التفعيل:** 500 ر.ق تُدفع عند التوقيع، وتُرد كاملة إذا رفضت جالبوت التاجر عند الفحص الميداني، ولا تُرد بعد بدء التشغيل.
- **تأمين الجهاز:** 300 ر.ق مقابل جهاز الطلبات اللوحي، ويُعاد خلال 30 يومًا من إرجاع الجهاز بحالة تشغيل سليمة.

</div>

## MOB-03: Commission and contract

| Merchant type | Commission |
|---|---|
| Food | 22% |
| Grocery | 12% |
| Pharmacy | 8% |

The minimum term is 6 months. After that, either side can end the contract with 30 days' written notice in the merchant portal. The first 90 days after go-live are a probation period, and a reserve applies during that time (MPO-05).

<div lang="ar" dir="rtl">

### العمولة والعقد

| نوع التاجر | العمولة |
|---|---|
| طعام | 22% |
| بقالة | 12% |
| صيدلية | 8% |

الحد الأدنى لمدة العقد 6 أشهر، ويمكن بعدها لأي من الطرفين إنهاؤه بإشعار كتابي مدته 30 يومًا عبر بوابة التجار. وتُعد أول 90 يومًا بعد بدء التشغيل فترة تجربة، ويُطبق خلالها مبلغ الضمان (MPO-05).

</div>

## MOB-04: Listing and performance standards

- App prices can be at most 10% above in-store prices.
- A merchant has 3 minutes to accept an order. After that, the order is cancelled and counts as a merchant cancellation.

**Reviewed over the rolling 30 days:**

| Measure | Standard |
|---|---|
| Acceptance rate | At least 90% |
| Merchant cancellation rate | At most 3% |
| Customer rating | At least 3.8 |

Missing a standard leads to a written improvement plan. Jalboot sends a reminder 30 days before a licence expires. If it expires, the listing is paused the same day until a valid licence is uploaded.

<div lang="ar" dir="rtl">

### معايير العرض والأداء

- لا يجوز أن تزيد الأسعار في التطبيق على أسعار المتجر بأكثر من 10%.
- أمام التاجر 3 دقائق لقبول الطلب، وبعدها يُلغى الطلب ويُحسب إلغاءً من جانب التاجر.

**تُراجع المعايير الآتية خلال 30 يومًا متحركة:**

| المقياس | المعيار |
|---|---|
| معدل القبول | 90% على الأقل |
| معدل الإلغاء من جانب التاجر | 3% على الأكثر |
| تقييم العملاء | 3.8 على الأقل |

ويؤدي عدم استيفاء أي معيار إلى خطة تحسين مكتوبة. وترسل جالبوت تذكيرًا قبل 30 يومًا من انتهاء الرخصة، فإذا انتهت أُوقف العرض في اليوم نفسه حتى رفع رخصة سارية.

</div>
