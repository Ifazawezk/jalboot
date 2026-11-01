import type {
  ActorKind,
  AuditAction,
  LiveState,
  Locale,
  Priority,
  RefundReason,
  RefundStatus,
  TranscriptAuthor,
  WindowDays,
} from '../api/types';
import { MOCK_RULES as R } from './mockRules';
import { AGENT_NOOR, toolDoneLabel } from './scenarios';
import type { L } from './text';

// Invented sample data for the support desk. Times are minutes before the moment
// the page loads, so the desk always looks like a shift in progress.

export const AGENT_KHALID: L = { en: 'Khalid', ar: 'خالد' };

export interface RawEntry {
  id: string;
  minutesAgo: number;
  author: TranscriptAuthor;
  name: L | null;
  /** Transcripts stay in the customer's own language, whichever language the desk uses. */
  text: string;
  tools: L[];
  sources: L[];
}

export interface RawConversation {
  id: string;
  customer: L;
  locale: Locale;
  state: LiveState;
  priority: Priority;
  verified: boolean;
  summary: L;
  orderId: string | null;
  agentName: L | null;
  startedMinutesAgo: number;
  updatedMinutesAgo: number;
  waitingMinutes: number | null;
  transcript: RawEntry[];
}

const entry = (
  id: string,
  minutesAgo: number,
  author: TranscriptAuthor,
  text: string,
  extra: Partial<Pick<RawEntry, 'name' | 'tools' | 'sources'>> = {},
): RawEntry => ({
  id,
  minutesAgo,
  author,
  text,
  name: extra.name ?? null,
  tools: extra.tools ?? [],
  sources: extra.sources ?? [],
});

const T = {
  order: toolDoneLabel('track_order'),
  details: toolDoneLabel('get_order_details'),
  delay: toolDoneLabel('explain_delay'),
  help: toolDoneLabel('search_knowledge'),
  refund: toolDoneLabel('issue_refund'),
  person: toolDoneLabel('handoff_to_human'),
};

const GENERAL: L = { en: 'General definitions', ar: 'التعريفات العامة' };
const REFUNDS: L = { en: 'Refunds and credits', ar: 'الاسترداد والرصيد' };
const LATE: L = { en: 'Late or missing orders', ar: 'الطلبات المتأخرة أو المفقودة' };
const PAYMENTS: L = { en: 'Payments and failed charges', ar: 'المدفوعات وعمليات الخصم الفاشلة' };
const PROMOS: L = { en: 'Promo codes and loyalty', ar: 'الرموز الترويجية والولاء' };

export const CONVERSATIONS: RawConversation[] = [
  {
    id: 'cv-1044',
    customer: { en: 'Mariam', ar: 'مريم' },
    locale: 'ar',
    state: 'waiting',
    priority: 'high',
    verified: true,
    summary: {
      en: 'Reports an allergic reaction after a meal',
      ar: 'تبلغ عن تحسس بعد تناول وجبة',
    },
    orderId: 'JB-48117',
    agentName: null,
    startedMinutesAgo: 6,
    updatedMinutesAgo: 2,
    waitingMinutes: 2.3,
    transcript: [
      entry('m1', 6, 'customer', 'ابني ظهر عليه طفح جلدي بعد أكل الوجبة، وقد طلبت بدون مكسرات.'),
      entry(
        'm2',
        5,
        'bot',
        'نأسف جدًا لذلك. إذا كان يجد صعوبة في التنفس فيُرجى الاتصال بالرقم 999 الآن. نقلتك إلى مقدمة قائمة الانتظار لموظف.',
        { tools: [T.order, T.help, T.person], sources: [GENERAL] },
      ),
      entry('m3', 2, 'customer', 'هو بخير الآن، لكن أريد أن أعرف ماذا كان في الوجبة.'),
    ],
  },
  {
    id: 'cv-1046',
    customer: { en: 'Fatima', ar: 'فاطمة' },
    locale: 'ar',
    state: 'waiting',
    priority: 'normal',
    verified: true,
    summary: { en: 'Charged twice for one order', ar: 'خُصم المبلغ مرتين لطلب واحد' },
    orderId: 'JB-48102',
    agentName: null,
    startedMinutesAgo: 12,
    updatedMinutesAgo: 5,
    waitingMinutes: 5.7,
    transcript: [
      entry('f1', 12, 'customer', 'تم خصم 64 ريال مرتين من بطاقتي لنفس الطلب.'),
      entry(
        'f2',
        11,
        'bot',
        'أرى عملية واحدة ناجحة في طلبك، لكن لا يمكنني رؤية كشف البطاقة. سأحول هذا إلى موظف ليتأكد.',
        { tools: [T.details, T.help, T.person], sources: [PAYMENTS] },
      ),
    ],
  },
  {
    id: 'cv-1045',
    customer: { en: 'Omar', ar: 'عمر' },
    locale: 'en',
    state: 'agent',
    priority: 'normal',
    verified: true,
    summary: { en: 'Received the wrong dish', ar: 'وصل طبق خاطئ' },
    orderId: 'JB-48090',
    agentName: AGENT_NOOR,
    startedMinutesAgo: 19,
    updatedMinutesAgo: 1,
    waitingMinutes: null,
    transcript: [
      entry('o1', 19, 'customer', 'I ordered the prawn platter and got grilled hammour instead.'),
      entry(
        'o2',
        18,
        'bot',
        'The store confirms the swap. I have filed the refund and asked a person to review it.',
        { tools: [T.order, T.person] },
      ),
      entry('o3', 9, 'agent', 'Hi Omar, this is Noor. I am looking at your refund now.', {
        name: AGENT_NOOR,
      }),
      entry('o4', 1, 'customer', 'Thank you. Will it go back to my card?'),
    ],
  },
  {
    id: 'cv-1042',
    customer: { en: 'Aisha', ar: 'عائشة' },
    locale: 'ar',
    state: 'bot',
    priority: 'normal',
    verified: true,
    summary: { en: 'Refund for missing dates sent for approval', ar: 'استرداد تمر ناقص أُرسل للموافقة' },
    orderId: 'JB-47902',
    agentName: null,
    startedMinutesAgo: 8,
    updatedMinutesAgo: 4,
    waitingMinutes: null,
    transcript: [
      entry('a1', 8, 'customer', 'علبة التمر ناقصة من طلبي.'),
      entry(
        'a2',
        7,
        'bot',
        'تمر الخلاص موجود في الطلب JB-47902، وقد سجّل المتجر كيسًا واحدًا فقط من الكيسين. أرسلت استرداد 62.50 ر.ق إلى الفريق للموافقة.',
        { tools: [T.details, T.help, T.refund], sources: [REFUNDS] },
      ),
    ],
  },
  {
    id: 'cv-1043',
    customer: { en: 'Hassan', ar: 'حسن' },
    locale: 'en',
    state: 'bot',
    priority: 'normal',
    verified: true,
    summary: { en: 'Asking where a late order is', ar: 'يسأل عن طلب متأخر' },
    orderId: 'JB-48213',
    agentName: null,
    startedMinutesAgo: 3,
    updatedMinutesAgo: 1,
    waitingMinutes: null,
    transcript: [
      entry('h1', 3, 'customer', 'Where is my order? It should have been here by now.'),
      entry(
        'h2',
        2,
        'bot',
        'Your order from Saffron Door Kitchen is on the way. Salim should reach you within 14 minutes.',
        { tools: [T.order, T.delay], sources: [LATE] },
      ),
    ],
  },
  {
    id: 'cv-1047',
    customer: { en: 'Yousef', ar: 'يوسف' },
    locale: 'en',
    state: 'bot',
    priority: 'normal',
    verified: false,
    summary: { en: 'Promo code rejected at checkout', ar: 'رُفض رمز الخصم عند الدفع' },
    orderId: null,
    agentName: null,
    startedMinutesAgo: 2,
    updatedMinutesAgo: 0.5,
    waitingMinutes: null,
    transcript: [
      entry('y1', 2, 'customer', 'My promo code SAVE20 says it is not valid.'),
      entry(
        'y2',
        1,
        'bot',
        `That code needs a minimum spend of QAR ${R.promoSave20MinSpendQar}, and your basket is QAR 48. Adding QAR ${R.promoSave20MinSpendQar - 48} more will make it work.`,
        { tools: [T.help], sources: [PROMOS] },
      ),
    ],
  },
];

export interface RawRefund {
  id: string;
  orderId: string;
  conversationId: string;
  customer: L;
  store: L;
  amountQar: number;
  status: RefundStatus;
  reason: RefundReason;
  summary: L;
  requestedMinutesAgo: number;
  decidedMinutesAgo: number | null;
  decidedBy: L | null;
  note: L | null;
  recommendation: 'approve' | 'review' | 'reject';
  evidence: { label: L; value: L; simulated?: boolean }[];
  policy: { title: L; section: L };
  risks: L[];
}

const money = (amount: number): L => ({
  en: `QAR ${amount.toFixed(2)}`,
  ar: `${amount.toFixed(2)} ر.ق`,
});

const ORDER_VALUE: L = { en: 'Order value', ar: 'قيمة الطلب' };
const STORE_RECORD: L = { en: 'Store record', ar: 'سجل المتجر' };
const PRIOR_CLAIMS: L = {
  en: `Approved claims in the last ${R.repeatClaimsWindowDays} days`,
  ar: `مطالبات موافق عليها في آخر ${R.repeatClaimsWindowDays} يومًا`,
};
const ACCOUNT_AGE: L = { en: 'Account age', ar: 'عمر الحساب' };
const PHOTO: L = { en: 'Customer photo', ar: 'صورة العميل' };
// Customers cannot upload photos, so a photo row can only ever be demo data.
const SIMULATED_PHOTO: L = {
  en: 'Simulated flag on a demo order. Customers cannot upload photos, so no real photo exists.',
  ar: 'علامة محاكاة في طلب تجريبي. لا يمكن للعملاء رفع الصور، فلا توجد صورة حقيقية.',
};

const APPROVAL_POLICY = {
  title: REFUNDS,
  section: { en: 'REF-05, Approval limits and repeat claims', ar: 'REF-05، حدود الموافقة وتكرار المطالبات' },
};
const WRONG_ITEM_POLICY = {
  title: { en: 'Wrong items', ar: 'الأصناف الخاطئة' },
  section: { en: 'WRG-01, Wrong, missing and short items', ar: 'WRG-01، الأصناف الخاطئة والناقصة' },
};
const QUALITY_POLICY = {
  title: { en: 'Wrong items', ar: 'الأصناف الخاطئة' },
  section: { en: 'WRG-05, Food quality complaints', ar: 'WRG-05، شكاوى جودة الطعام' },
};

export const REFUND_SEEDS: RawRefund[] = [
  {
    id: 'RF-2097',
    orderId: 'JB-48021',
    conversationId: 'cv-1038',
    customer: { en: 'Abdulla', ar: 'عبدالله' },
    store: { en: 'Madinat Greens Market', ar: 'سوق مدينة الخضار' },
    amountQar: 342,
    status: 'pending',
    reason: 'wrong_item',
    summary: {
      en: 'A full catering order went to the wrong address. Too large for a support agent to approve.',
      ar: 'طلب ضيافة كامل وصل إلى عنوان خاطئ. المبلغ أكبر مما يوافق عليه موظف الدعم.',
    },
    requestedMinutesAgo: 26,
    decidedMinutesAgo: null,
    decidedBy: null,
    note: null,
    recommendation: 'review',
    evidence: [
      { label: ORDER_VALUE, value: money(342) },
      { label: STORE_RECORD, value: { en: 'Delivered to a different area', ar: 'سُلّم في منطقة أخرى' } },
      { label: PRIOR_CLAIMS, value: { en: 'None', ar: 'لا يوجد' } },
    ],
    policy: APPROVAL_POLICY,
    risks: [],
  },
  {
    id: 'RF-2096',
    orderId: 'JB-48033',
    conversationId: 'cv-1039',
    customer: { en: 'Yara', ar: 'يارا' },
    store: { en: 'Saffron Door Kitchen', ar: 'مطبخ باب الزعفران' },
    amountQar: 29,
    status: 'pending',
    reason: 'quality',
    summary: {
      en: `Says the rice, priced at QAR 58, arrived undercooked. The customer already has ${R.repeatClaimsFrom} approved claims in the last ${R.repeatClaimsWindowDays} days, so a person decides.`,
      ar: `تقول إن الأرز، وسعره 58 ر.ق، وصل غير ناضج. لدى العميلة ${R.repeatClaimsFrom} مطالبات موافق عليها خلال آخر ${R.repeatClaimsWindowDays} يومًا، لذا يقرر موظف.`,
    },
    requestedMinutesAgo: 22,
    decidedMinutesAgo: null,
    decidedBy: null,
    note: null,
    recommendation: 'review',
    evidence: [
      { label: ORDER_VALUE, value: money(66) },
      { label: PHOTO, value: SIMULATED_PHOTO, simulated: true },
      { label: PRIOR_CLAIMS, value: { en: String(R.repeatClaimsFrom), ar: String(R.repeatClaimsFrom) } },
    ],
    policy: QUALITY_POLICY,
    risks: [
      {
        en: `${R.repeatClaimsFrom} approved claims in ${R.repeatClaimsWindowDays} days`,
        ar: `${R.repeatClaimsFrom} مطالبات موافق عليها خلال ${R.repeatClaimsWindowDays} يومًا`,
      },
    ],
  },
  {
    id: 'RF-2091',
    orderId: 'JB-47902',
    conversationId: 'cv-1042',
    customer: { en: 'Aisha', ar: 'عائشة' },
    store: { en: 'Madinat Greens Market', ar: 'سوق مدينة الخضار' },
    amountQar: 62.5,
    status: 'pending',
    reason: 'missing_item',
    summary: {
      en: 'Khalas dates missing. The store scanned one of two bags, which fits the report.',
      ar: 'تمر الخلاص ناقص. سجّل المتجر كيسًا واحدًا من كيسين، وهذا يتفق مع البلاغ.',
    },
    requestedMinutesAgo: 7,
    decidedMinutesAgo: null,
    decidedBy: null,
    note: null,
    recommendation: 'approve',
    evidence: [
      { label: ORDER_VALUE, value: money(110.79) },
      { label: STORE_RECORD, value: { en: 'One of two bags scanned', ar: 'سجّل كيسًا واحدًا من كيسين' } },
      { label: PRIOR_CLAIMS, value: { en: 'None', ar: 'لا يوجد' } },
    ],
    policy: APPROVAL_POLICY,
    risks: [],
  },
  {
    id: 'RF-2094',
    orderId: 'JB-48090',
    conversationId: 'cv-1045',
    customer: { en: 'Omar', ar: 'عمر' },
    store: { en: 'Wakrah Fish Table', ar: 'مائدة سمك الوكرة' },
    amountQar: 62.25,
    status: 'pending',
    reason: 'wrong_item',
    summary: {
      en: 'Received grilled hammour instead of the prawn platter. Store confirmed the swap.',
      ar: 'استلم هامورًا مشويًا بدل طبق الروبيان. أكد المتجر حدوث الخطأ.',
    },
    requestedMinutesAgo: 14,
    decidedMinutesAgo: null,
    decidedBy: null,
    note: null,
    recommendation: 'approve',
    evidence: [
      { label: ORDER_VALUE, value: money(132.75) },
      { label: STORE_RECORD, value: { en: 'Store confirmed the mistake', ar: 'أكد المتجر الخطأ' } },
      { label: PHOTO, value: SIMULATED_PHOTO, simulated: true },
      { label: PRIOR_CLAIMS, value: { en: '1', ar: '1' } },
    ],
    policy: WRONG_ITEM_POLICY,
    risks: [],
  },
  {
    id: 'RF-2093',
    orderId: 'JB-48075',
    conversationId: 'cv-1036',
    customer: { en: 'Hamad', ar: 'حمد' },
    store: { en: 'Lusail Lantern Grill', ar: 'مشويات فانوس لوسيل' },
    amountQar: 46,
    status: 'pending',
    reason: 'missing_item',
    summary: {
      en: 'Mixed grill missing. The account is new, so the lower automated limit applies.',
      ar: 'طبق المشاوي المشكلة ناقص. الحساب جديد، لذا ينطبق الحد الآلي الأقل.',
    },
    requestedMinutesAgo: 31,
    decidedMinutesAgo: null,
    decidedBy: null,
    note: null,
    recommendation: 'review',
    evidence: [
      { label: ORDER_VALUE, value: money(92) },
      { label: STORE_RECORD, value: { en: 'No packing record', ar: 'لا يوجد سجل تغليف' } },
      { label: ACCOUNT_AGE, value: { en: '3 days', ar: '3 أيام' } },
    ],
    policy: APPROVAL_POLICY,
    risks: [
      {
        en: `Account younger than ${R.refundNewAccountAgeDays} days`,
        ar: `عمر الحساب أقل من ${R.refundNewAccountAgeDays} أيام`,
      },
    ],
  },
  {
    id: 'RF-2088',
    orderId: 'JB-47790',
    conversationId: 'cv-1031',
    customer: { en: 'Salma', ar: 'سلمى' },
    store: { en: 'Corniche Citrus Juice', ar: 'عصائر حمضيات الكورنيش' },
    amountQar: 68,
    status: 'approved',
    reason: 'missing_item',
    summary: { en: 'A family juice order did not arrive.', ar: 'لم يصل طلب العصائر العائلي.' },
    requestedMinutesAgo: 95,
    decidedMinutesAgo: 80,
    decidedBy: AGENT_KHALID,
    note: { en: 'Store confirmed by phone.', ar: 'أكد المتجر ذلك هاتفيًا.' },
    recommendation: 'approve',
    evidence: [],
    policy: APPROVAL_POLICY,
    risks: [],
  },
  {
    id: 'RF-2085',
    orderId: 'JB-47711',
    conversationId: 'cv-1028',
    customer: { en: 'Nasser', ar: 'ناصر' },
    store: { en: 'Lusail Lantern Grill', ar: 'مشويات فانوس لوسيل' },
    amountQar: 74,
    status: 'rejected',
    reason: 'quality',
    summary: { en: 'Requested a full refund with no photo.', ar: 'طلب استردادًا كاملًا بدون صورة.' },
    requestedMinutesAgo: 140,
    decidedMinutesAgo: 120,
    decidedBy: AGENT_KHALID,
    note: {
      en: 'No photo was sent, so we could not confirm the problem.',
      ar: 'لم تُرسل صورة، فلم نتمكن من تأكيد المشكلة.',
    },
    recommendation: 'reject',
    evidence: [],
    policy: QUALITY_POLICY,
    risks: [],
  },
];

export interface RawAudit {
  id: string;
  minutesAgo: number;
  actorKind: ActorKind;
  actorName: L;
  action: AuditAction;
  target: string;
  detail: L;
}

const BOT: L = { en: 'Automated support', ar: 'الدعم الآلي' };
const SYSTEM: L = { en: 'System', ar: 'النظام' };

const audit = (
  id: string,
  minutesAgo: number,
  actorKind: ActorKind,
  actorName: L,
  action: AuditAction,
  target: string,
  detail: L,
): RawAudit => ({ id, minutesAgo, actorKind, actorName, action, target, detail });

const proposed = (id: string, minutesAgo: number, amount: number, order: string, refund: string): RawAudit =>
  audit(id, minutesAgo, 'bot', BOT, 'refund.proposed', refund, {
    en: `QAR ${amount.toFixed(2)} for order ${order}`,
    ar: `${amount.toFixed(2)} ر.ق للطلب ${order}`,
  });

export const AUDIT_SEEDS: RawAudit[] = [
  audit('au-48', 1, 'bot', BOT, 'tool.called', 'JB-48213', {
    en: 'Looked up the rider for this order',
    ar: 'بحث عن مندوب هذا الطلب',
  }),
  audit('au-47', 2, 'bot', BOT, 'handoff.requested', 'cv-1044', {
    en: 'Allergic reaction reported, sent to the front of the line',
    ar: 'بلاغ عن تحسس، نُقل إلى مقدمة القائمة',
  }),
  audit('au-46', 4, 'bot', BOT, 'guardrail.blocked', 'cv-1041', {
    en: 'A message told the system to ignore its rules and refund QAR 500. Nothing was changed.',
    ar: 'طلبت رسالة تجاهل القواعد واسترداد 500 ريال. لم يتغير شيء.',
  }),
  audit('au-49', 5, 'system', SYSTEM, 'identity.verified', 'cv-1043', {
    en: 'Customer confirmed by a code sent to their number',
    ar: 'تم تأكيد العميل برمز أُرسل إلى رقمه',
  }),
  proposed('au-45', 7, 62.5, 'JB-47902', 'RF-2091'),
  audit('au-44', 7, 'bot', BOT, 'tool.called', 'JB-47902', {
    en: 'Read the store packing record',
    ar: 'قرأ سجل تغليف المتجر',
  }),
  audit('au-43', 9, 'agent', AGENT_NOOR, 'agent.replied', 'cv-1045', {
    en: 'Told the customer the rider is going back',
    ar: 'أبلغ العميل بعودة المندوب',
  }),
  audit('au-42', 10, 'agent', AGENT_NOOR, 'handoff.joined', 'cv-1045', {
    en: 'Took over from automated support',
    ar: 'تولى المحادثة من الدعم الآلي',
  }),
  audit('au-41', 12, 'bot', BOT, 'refund.auto_approved', 'RF-2090', {
    en: 'QAR 12.00 for order JB-47988',
    ar: '12.00 ر.ق للطلب JB-47988',
  }),
  proposed('au-40', 14, 62.25, 'JB-48090', 'RF-2094'),
  audit('au-39', 17, 'bot', BOT, 'tool.called', 'JB-48102', {
    en: 'Checked the payment status',
    ar: 'تحقق من حالة الدفع',
  }),
  proposed('au-38', 22, 29, 'JB-48033', 'RF-2096'),
  proposed('au-50', 26, 342, 'JB-48021', 'RF-2097'),
  proposed('au-37', 31, 46, 'JB-48075', 'RF-2093'),
  audit('au-36', 44, 'bot', BOT, 'guardrail.blocked', 'cv-1033', {
    en: 'Asked for another customer’s address. Refused.',
    ar: 'طُلب عنوان عميل آخر، فرُفض الطلب.',
  }),
  audit('au-35', 80, 'agent', AGENT_KHALID, 'refund.approved', 'RF-2088', {
    en: 'QAR 68.00. Store confirmed by phone.',
    ar: '68.00 ر.ق. أكد المتجر ذلك هاتفيًا.',
  }),
  proposed('au-34', 95, 68, 'JB-47790', 'RF-2088'),
  audit('au-33', 120, 'agent', AGENT_KHALID, 'refund.rejected', 'RF-2085', {
    en: 'QAR 74.00. No photo was sent.',
    ar: '74.00 ر.ق. لم تُرسل صورة.',
  }),
  proposed('au-32', 140, 74, 'JB-47711', 'RF-2085'),
];

const ISSUES: { id: string; label: L; perWeek: number; change: number }[] = [
  { id: 'where_is_order', label: { en: 'Where is my order', ar: 'أين طلبي' }, perWeek: 412, change: 6 },
  { id: 'missing_items', label: { en: 'Missing or wrong items', ar: 'أصناف ناقصة أو خاطئة' }, perWeek: 268, change: -4 },
  { id: 'refund_status', label: { en: 'Refund status', ar: 'حالة الاسترداد' }, perWeek: 197, change: 11 },
  { id: 'late_credit', label: { en: 'Late delivery credit', ar: 'رصيد التأخير' }, perWeek: 144, change: -9 },
  { id: 'promo_codes', label: { en: 'Promo code problems', ar: 'مشكلات الرموز الترويجية' }, perWeek: 96, change: 23 },
  { id: 'double_charge', label: { en: 'Charged twice', ar: 'خصم مكرر' }, perWeek: 58, change: 2 },
  { id: 'address_change', label: { en: 'Changing the address', ar: 'تغيير العنوان' }, perWeek: 41, change: -12 },
];

export function issuesFor(windowDays: WindowDays): { id: string; label: L; count: number; changePct: number }[] {
  const scale = windowDays / 7;
  return ISSUES.map((issue, i) => ({
    id: issue.id,
    label: issue.label,
    count: Math.round(issue.perWeek * scale * (1 - (i % 3) * 0.01 * (scale - 1))),
    changePct: Math.round(issue.change * (windowDays === 7 ? 1 : windowDays === 14 ? 0.8 : 0.6)),
  })).sort((a, b) => b.count - a.count);
}

/** Small repeatable wobble, so the sample trends look real and never change between loads. */
function wobble(seed: number): number {
  const x = Math.sin(seed * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

export function trendFor(seed: number, days: number, base: number, spread: number, drift: number): number[] {
  return Array.from({ length: days }, (_, i) => {
    const progress = days > 1 ? i / (days - 1) : 1;
    const noise = (wobble(seed + i) - 0.5) * spread;
    return Number((base + drift * (progress - 1) + noise * (i === days - 1 ? 0 : 1)).toFixed(1));
  });
}

export const QUALITY_BASE = {
  resolved: { label: { en: 'Resolved without a person', ar: 'حُلّت بدون موظف' }, value: 71.4, delta: 2.6 },
  tiles: [
    { id: 'handoff', label: { en: 'Moved to a person', ar: 'حُوّلت إلى موظف' }, value: 18.2, delta: -1.3, unit: 'percent', higherIsBetter: false, spread: 3 },
    { id: 'first_reply', label: { en: 'Median first reply', ar: 'وسيط أول رد' }, value: 3.2, delta: -0.4, unit: 'seconds', higherIsBetter: false, spread: 0.8 },
    { id: 'rating', label: { en: 'Customer rating', ar: 'تقييم العملاء' }, value: 4.4, delta: 0.1, unit: 'score', higherIsBetter: true, spread: 0.3 },
    { id: 'cited', label: { en: 'Answers with a source', ar: 'إجابات لها مصدر' }, value: 96.1, delta: 0.7, unit: 'percent', higherIsBetter: true, spread: 1.6 },
    { id: 'overturned', label: { en: 'Refund advice overruled', ar: 'توصيات استرداد عُدّلت' }, value: 2.1, delta: 0.3, unit: 'percent', higherIsBetter: false, spread: 0.9 },
  ],
} as const;
