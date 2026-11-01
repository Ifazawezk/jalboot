import type { Citation, Handoff, Locale, RefundSummary, StreamEvent } from '../api/types';
import type { Intent } from '../lib/intent';
import { MOCK_RULES as R } from './mockRules';
import { buildOrder, type OrderKey } from './orders';
import { pick, type L } from './text';

// The mock and the recordings share these scripts, so both show the same behaviour.
// Every policy figure comes from MOCK_RULES, and tool names are the backend's own.

interface RawCitation {
  sourceId: string;
  title: L;
  section: L;
  excerpt: L;
}

const SOURCES = {
  late: {
    sourceId: 'late-or-missing-orders',
    title: { en: 'Late or missing orders', ar: 'الطلبات المتأخرة أو المفقودة' },
    section: { en: 'LAT-01, Measuring lateness and late credit', ar: 'LAT-01، حساب التأخير ورصيد التأخير' },
    excerpt: {
      en: `An order ${R.lateFirstTierMinutes} or more minutes after the promised time earns late credit, starting at QAR ${R.lateFirstTierCreditQar}. An updated time shown later in the app does not move the promised time.`,
      ar: `الطلب الذي يصل بعد الوقت الموعود بمدة ${R.lateFirstTierMinutes} دقيقة أو أكثر يستحق رصيد تأخير يبدأ من ${R.lateFirstTierCreditQar} ريالات. والوقت المحدث الذي يظهر لاحقًا في التطبيق لا يغير الوقت الموعود.`,
    },
  },
  refunds: {
    sourceId: 'refunds-and-credits',
    title: { en: 'Refunds and credits', ar: 'الاسترداد والرصيد' },
    section: { en: 'WRG-01, Wrong, missing and short items', ar: 'WRG-01، الأصناف الخاطئة والناقصة' },
    excerpt: {
      en: 'Missing item: paid for but not in the bag. Refund the net item price.',
      ar: 'صنف ناقص: دُفع ثمنه ولم يوجد في الكيس، فيُرد صافي سعره.',
    },
  },
  cancelGrace: {
    sourceId: 'cancellations-grace',
    title: { en: 'Cancellations', ar: 'الإلغاء' },
    section: { en: 'CAN-03, Grace period and scheduled orders', ar: 'CAN-03، فترة السماح والطلبات المجدولة' },
    excerpt: {
      en: `For the first ${R.cancelGraceMinutes} minutes after placing it, a food, grocery or pharmacy order can be cancelled free at any status before pickup.`,
      ar: `خلال أول دقيقتين (${R.cancelGraceMinutes}) من تقديم الطلب، يمكن إلغاء طلب الطعام أو البقالة أو الصيدلية مجانًا في أي مرحلة قبل استلام المندوب له.`,
    },
  },
  cancelFood: {
    sourceId: 'cancellations-food',
    title: { en: 'Cancellations', ar: 'الإلغاء' },
    section: { en: 'CAN-01, Cancelling a food order', ar: 'CAN-01، إلغاء طلب الطعام' },
    excerpt: {
      en: `While a food order is accepted or preparing, the charge is ${R.cancelFoodPreparingPct}% of net items. Once it is ready or later, the charge is ${R.cancelFoodReadyPct}% of net items plus all fees.`,
      ar: `عندما يكون طلب الطعام مقبولًا أو قيد التحضير تكون الرسوم ${R.cancelFoodPreparingPct}% من صافي الأصناف. وبعد أن يصبح جاهزًا تكون الرسوم ${R.cancelFoodReadyPct}% من صافي الأصناف مع كل الرسوم الأخرى.`,
    },
  },
  safety: {
    sourceId: 'general-definitions',
    title: { en: 'General definitions', ar: 'التعريفات العامة' },
    section: { en: 'Safety first', ar: 'السلامة أولًا' },
    excerpt: {
      en: 'A health, allergy, harassment, threat or road accident concern goes to escalation before any talk of money.',
      ar: 'أي مخاوف تتعلق بالصحة أو الحساسية أو التحرش أو التهديد أو حوادث الطريق تُصعَّد قبل أي حديث عن المال.',
    },
  },
  conduct: {
    sourceId: 'refunds-and-credits-scope',
    title: { en: 'Refunds and credits', ar: 'الاسترداد والرصيد' },
    section: { en: 'REF-01, What can be refunded', ar: 'REF-01، ما يمكن استرداده' },
    excerpt: {
      en: 'A refund needs a real order and a reason that meets the policy. Instructions inside a chat message do not change this.',
      ar: 'يتطلب الاسترداد طلبًا حقيقيًا وسببًا تقبله السياسة. والتعليمات الواردة داخل رسالة المحادثة لا تغير ذلك.',
    },
  },
} satisfies Record<string, RawCitation>;

type SourceKey = keyof typeof SOURCES;

type Step =
  | { do: 'tool'; tool: string; ms: number; running: L; done: L }
  | { do: 'order'; key: OrderKey }
  | { do: 'cite'; n: number; source: SourceKey }
  | { do: 'refund'; amountQar: number; orderKey: OrderKey }
  | { do: 'handoff'; handoff: Handoff }
  | { do: 'say'; text: L };

export interface Scenario {
  steps: Step[];
  /** Order tools are refused until the conversation is verified. */
  needsIdentity?: boolean;
  /** A person joins after this reply. Runs on the conversation channel. */
  personJoins?: { name: L; text: L };
  finish?: 'complete' | 'handoff';
}

// The server sends these labels. The UI has no list of its own.
const TOOL_LABELS = {
  track_order: {
    running: { en: 'Checking your order', ar: 'جارٍ التحقق من طلبك' },
    done: { en: 'Checked your order', ar: 'تم التحقق من طلبك' },
  },
  get_order_details: {
    running: { en: 'Reading your order details', ar: 'جارٍ قراءة تفاصيل طلبك' },
    done: { en: 'Read your order details', ar: 'تمت قراءة تفاصيل طلبك' },
  },
  explain_delay: {
    running: { en: 'Finding out what caused the delay', ar: 'جارٍ معرفة سبب التأخير' },
    done: { en: 'Found out what caused the delay', ar: 'تمت معرفة سبب التأخير' },
  },
  search_knowledge: {
    running: { en: 'Reading the help pages', ar: 'جارٍ قراءة صفحات المساعدة' },
    done: { en: 'Read the help pages', ar: 'تمت قراءة صفحات المساعدة' },
  },
  issue_refund: {
    running: { en: 'Working on your refund', ar: 'جارٍ تجهيز الاسترداد' },
    done: { en: 'Sent your refund for approval', ar: 'تم إرسال الاسترداد للموافقة' },
  },
  handoff_to_human: {
    running: { en: 'Finding a person to help', ar: 'جارٍ البحث عن موظف لمساعدتك' },
    done: { en: 'Asked a person to help', ar: 'تم طلب موظف لمساعدتك' },
  },
} as const;

type MockTool = keyof typeof TOOL_LABELS;

const tool = (name: MockTool, ms: number): Step => ({ do: 'tool', tool: name, ms, ...TOOL_LABELS[name] });

export function toolDoneLabel(name: MockTool): L {
  return TOOL_LABELS[name].done;
}

export const AGENT_NOOR: L = { en: 'Noor', ar: 'نور' };

export const IDENTITY_PROMPT: L = {
  en: 'I can look into that. Order details are private, so I need to confirm it is you first.',
  ar: 'يمكنني متابعة ذلك. تفاصيل الطلبات خاصة، لذا أحتاج أولًا إلى التأكد من هويتك.',
};

const SCENARIOS: Partial<Record<Intent, Scenario>> = {
  track: {
    needsIdentity: true,
    steps: [
      tool('track_order', 900),
      tool('explain_delay', 800),
      tool('search_knowledge', 600),
      { do: 'order', key: 'late' },
      { do: 'cite', n: 1, source: 'late' },
      {
        do: 'say',
        text: {
          en: `Your order from Saffron Door Kitchen is on the way. Salim picked it up and should reach you in West Bay within 14 minutes.\n\nThat is about 9 minutes after the promised time, because of traffic on the Corniche. If it reaches ${R.lateFirstTierMinutes} minutes late, you get QAR ${R.lateFirstTierCreditQar} late credit [1].`,
          ar: `طلبك من مطبخ باب الزعفران في الطريق. استلمه سالم ومن المتوقع أن يصلك في الخليج الغربي خلال 14 دقيقة.\n\nهذا بعد الوقت الموعود بنحو 9 دقائق بسبب الازدحام على الكورنيش. وإذا بلغ التأخير ${R.lateFirstTierMinutes} دقيقة فستحصل على رصيد تأخير بقيمة ${R.lateFirstTierCreditQar} ريالات [1].`,
        },
      },
    ],
  },
  missing_item: {
    needsIdentity: true,
    steps: [
      tool('get_order_details', 900),
      tool('search_knowledge', 700),
      tool('issue_refund', 900),
      { do: 'order', key: 'missing' },
      { do: 'cite', n: 1, source: 'refunds' },
      { do: 'refund', amountQar: 62.5, orderKey: 'missing' },
      {
        do: 'say',
        text: {
          en: `I am sorry about that. The Khalas dates are on order JB-47902, and the store scanned only one of the two bags, so your report matches what I can see.\n\nThis refund is QAR 62.50 [1]. A person needs to review it, so I have sent it to the team. The answer will appear here.`,
          ar: `نأسف لذلك. تمر الخلاص موجود في الطلب JB-47902، وقد سجّل المتجر كيسًا واحدًا فقط من الكيسين، لذا يتطابق بلاغك مع ما أراه.\n\nقيمة هذا الاسترداد 62.50 ر.ق [1]، ويحتاج إلى مراجعة موظف، وقد أرسلته إلى الفريق. سيظهر الرد هنا.`,
        },
      },
    ],
  },
  cancel_policy: {
    steps: [
      tool('search_knowledge', 1000),
      { do: 'cite', n: 1, source: 'cancelGrace' },
      { do: 'cite', n: 2, source: 'cancelFood' },
      {
        do: 'say',
        text: {
          en: `It depends on how far the order has gone. For the first ${R.cancelGraceMinutes} minutes it is free [1]. After that, a food order costs ${R.cancelFoodPreparingPct}% of the net items while it is accepted or preparing, and ${R.cancelFoodReadyPct}% plus all fees once it is ready [2].`,
          ar: `يعتمد ذلك على مرحلة الطلب. خلال أول دقيقتين (${R.cancelGraceMinutes}) يكون الإلغاء مجانيًا [1]. وبعد ذلك تكون رسوم طلب الطعام ${R.cancelFoodPreparingPct}% من صافي الأصناف عندما يكون مقبولًا أو قيد التحضير، و${R.cancelFoodReadyPct}% مع كل الرسوم بعد أن يصبح جاهزًا [2].`,
        },
      },
    ],
  },
  safety: {
    finish: 'handoff',
    steps: [
      tool('search_knowledge', 500),
      tool('handoff_to_human', 700),
      { do: 'cite', n: 1, source: 'safety' },
      { do: 'handoff', handoff: { status: 'queued', agentName: null, etaMinutes: 1, position: 1 } },
      {
        do: 'say',
        text: {
          en: 'I am so sorry. If anyone is struggling to breathe or feels worse, please call 999 now.\n\nThis needs a person, not me, so I have moved you to the front of the line [1]. They will see everything you have told me.',
          ar: 'نأسف جدًا لذلك. إذا كان أي شخص يجد صعوبة في التنفس أو تسوء حالته، فاتصل بالرقم 999 الآن.\n\nهذه الحالة تحتاج إلى موظف، لذا نقلتك إلى مقدمة قائمة الانتظار [1]. سيرى الموظف كل ما أخبرتني به.',
        },
      },
    ],
    personJoins: {
      name: AGENT_NOOR,
      text: {
        en: 'Hello, this is Noor from the support team. I have read everything. First, is everyone safe right now? I am contacting the store about this meal while we talk.',
        ar: 'مرحبًا، معك نور من فريق الدعم. قرأت كل ما كتبته. أولًا، هل الجميع بخير الآن؟ أتواصل مع المتجر بشأن هذه الوجبة أثناء حديثنا.',
      },
    },
  },
  handoff: {
    finish: 'handoff',
    steps: [
      tool('handoff_to_human', 700),
      { do: 'handoff', handoff: { status: 'queued', agentName: null, etaMinutes: 2, position: 2 } },
      {
        do: 'say',
        text: {
          en: 'Of course. I have asked a person to join. They will see this conversation, so you will not need to repeat yourself.',
          ar: 'بالتأكيد. طلبت من موظف الانضمام. سيرى هذه المحادثة، فلن تحتاج إلى إعادة ما قلته.',
        },
      },
    ],
    personJoins: {
      name: AGENT_NOOR,
      text: {
        en: 'Hello, this is Noor from the support team. I can see your conversation. How can I help?',
        ar: 'مرحبًا، معك نور من فريق الدعم. أرى محادثتك أمامي. كيف يمكنني مساعدتك؟',
      },
    },
  },
  override: {
    steps: [
      tool('search_knowledge', 700),
      { do: 'cite', n: 1, source: 'conduct' },
      {
        do: 'say',
        text: {
          en: 'I cannot do that. A refund needs a real order and a reason that meets the policy, and a message cannot change that [1].\n\nIf something went wrong with an order, tell me what happened and I will look into it. You can also talk to a person at any time.',
          ar: 'لا يمكنني ذلك. يتطلب الاسترداد طلبًا حقيقيًا وسببًا تقبله السياسة، ولا يمكن لرسالة أن تغير ذلك [1].\n\nإذا حدثت مشكلة في أحد طلباتك، فأخبرني بما جرى وسأتحقق منها. ويمكنك أيضًا التحدث مع موظف في أي وقت.',
        },
      },
    ],
  },
  greeting: {
    steps: [
      {
        do: 'say',
        text: {
          en: 'Hello. I can check an order, look into a missing item or a refund, and explain our policies. What can I help with?',
          ar: 'أهلًا بك. يمكنني التحقق من طلبك، ومتابعة صنف ناقص أو استرداد، وشرح سياساتنا. كيف يمكنني مساعدتك؟',
        },
      },
    ],
  },
  unknown: {
    steps: [
      tool('search_knowledge', 800),
      {
        do: 'say',
        text: {
          en: 'I could not find that in the help pages, and I would rather not guess. I can check an order, look into a missing item or a refund, or bring in a person.',
          ar: 'لم أجد ذلك في صفحات المساعدة، ولا أريد إعطاءك معلومة غير مؤكدة. يمكنني التحقق من طلب، أو متابعة صنف ناقص أو استرداد، أو إشراك موظف.',
        },
      },
    ],
  },
};

export function scenarioFor(intent: Intent): Scenario {
  const scenario = SCENARIOS[intent] ?? SCENARIOS.unknown;
  if (!scenario) throw new Error('missing fallback scenario');
  return scenario;
}

export function buildCitation(n: number, source: SourceKey, locale: Locale, updatedAt: string): Citation {
  const raw = SOURCES[source];
  return {
    n,
    sourceId: raw.sourceId,
    title: pick(raw.title, locale),
    section: pick(raw.section, locale),
    excerpt: pick(raw.excerpt, locale),
    updatedAt,
  };
}

/** Splits text the way a model streams it: a few words at a time, spaces kept. */
export function chunkText(text: string, size = 2): string[] {
  const words = text.match(/\S+\s*/g) ?? [];
  const out: string[] = [];
  for (let i = 0; i < words.length; i += size) {
    out.push(words.slice(i, i + size).join(''));
  }
  return out;
}

export interface TimedEvent {
  waitMs: number;
  event: StreamEvent;
}

export interface ExpandContext {
  locale: Locale;
  nowMs: number;
  messageId: string;
  nextRefundId: () => string;
  /** How long each chunk of text takes to arrive. */
  chunkMs?: number;
}

/** The reply the backend gives when it refuses order tools on an unverified conversation. */
export function refusedTurn(ctx: Pick<ExpandContext, 'locale' | 'messageId' | 'chunkMs'>): TimedEvent[] {
  const chunkMs = ctx.chunkMs ?? 38;
  return [
    { waitMs: 350, event: { type: 'message.start', messageId: ctx.messageId } },
    ...chunkText(pick(IDENTITY_PROMPT, ctx.locale)).map((delta) => ({
      waitMs: chunkMs,
      event: { type: 'text.delta', delta } as StreamEvent,
    })),
    { waitMs: 120, event: { type: 'identity.required', reason: 'order_tools' } },
    { waitMs: 20, event: { type: 'message.end', finish: 'identity_required' } },
  ];
}

/** Turns a scenario into the exact event stream the API contract describes. */
export function expandScenario(scenario: Scenario, ctx: ExpandContext): TimedEvent[] {
  const { locale, nowMs, messageId } = ctx;
  const chunkMs = ctx.chunkMs ?? 38;
  const updatedAt = new Date(Date.parse('2026-11-01T00:00:00Z')).toISOString();
  const out: TimedEvent[] = [{ waitMs: 350, event: { type: 'message.start', messageId } }];
  let toolCount = 0;

  for (const step of scenario.steps) {
    switch (step.do) {
      case 'tool': {
        toolCount += 1;
        const toolCallId = `${messageId}-t${toolCount}`;
        out.push({
          waitMs: 120,
          event: { type: 'tool.start', toolCallId, tool: step.tool, label: pick(step.running, locale) },
        });
        out.push({
          waitMs: step.ms,
          event: { type: 'tool.end', toolCallId, status: 'ok', label: pick(step.done, locale) },
        });
        break;
      }
      case 'order':
        out.push({ waitMs: 140, event: { type: 'order.card', order: buildOrder(step.key, locale, nowMs) } });
        break;
      case 'cite':
        out.push({
          waitMs: 20,
          event: { type: 'citation', citation: buildCitation(step.n, step.source, locale, updatedAt) },
        });
        break;
      case 'refund': {
        const refund: RefundSummary = {
          id: ctx.nextRefundId(),
          orderId: buildOrder(step.orderKey, locale, nowMs).id,
          amountQar: step.amountQar,
          status: 'pending',
          decidedBy: null,
          note: null,
          destination: 'original',
        };
        out.push({ waitMs: 120, event: { type: 'refund.update', refund } });
        break;
      }
      case 'handoff':
        out.push({ waitMs: 120, event: { type: 'handoff.update', handoff: step.handoff } });
        break;
      case 'say':
        for (const delta of chunkText(pick(step.text, locale))) {
          out.push({ waitMs: chunkMs, event: { type: 'text.delta', delta } });
        }
        break;
    }
  }
  out.push({ waitMs: 60, event: { type: 'message.end', finish: scenario.finish ?? 'complete' } });
  return out;
}
