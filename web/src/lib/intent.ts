// Keyword intent matching for the mock only. The real backend replaces this.

export type Intent =
  | 'track'
  | 'missing_item'
  | 'cancel_policy'
  | 'handoff'
  | 'safety'
  | 'override'
  | 'greeting'
  | 'unknown';

/** Folds common Arabic spelling variants and strips diacritics before matching. */
export function normalizeText(text: string): string {
  return text
    .toLowerCase()
    .replace(/[\u064B-\u0652\u0640]/g, '')
    .replace(/[\u0622\u0623\u0625]/g, '\u0627')
    .replace(/\u0649/g, '\u064A')
    .replace(/\u0629/g, '\u0647');
}

// Order matters: a message that mentions an order and an allergy is a safety case.
const RULES: { intent: Intent; words: string[] }[] = [
  {
    intent: 'override',
    words: ['ignore your', 'ignore all', 'ignore previous', 'system prompt', 'تجاهل', 'انس التعليمات'],
  },
  {
    intent: 'safety',
    words: ['allerg', 'hospital', 'food poison', 'choking', 'حساسية', 'مستشفى', 'تسمم'],
  },
  {
    intent: 'handoff',
    words: ['a person', 'human', 'real agent', 'someone', 'موظف', 'شخص', 'إنسان'],
  },
  {
    intent: 'missing_item',
    words: ['missing', 'wrong item', 'not in the bag', 'refund', 'ناقص', 'نقص', 'مفقود', 'استرداد', 'استرجاع'],
  },
  {
    intent: 'cancel_policy',
    words: ['cancel', 'fee', 'policy', 'إلغاء', 'ألغي', 'رسوم', 'سياسة'],
  },
  {
    intent: 'track',
    words: ['where', 'order', 'track', 'late', 'أين', 'وين', 'طلب', 'تتبع', 'متأخر', 'تأخر'],
  },
  { intent: 'greeting', words: ['hello', 'hi ', 'hey', 'salam', 'مرحبا', 'السلام', 'أهلا'] },
];

const FOLDED_RULES = RULES.map((rule) => ({
  intent: rule.intent,
  words: rule.words.map(normalizeText),
}));

export function classifyIntent(text: string): Intent {
  const folded = `${normalizeText(text).trim()} `;
  if (folded.trim() === '') return 'unknown';
  for (const rule of FOLDED_RULES) {
    if (rule.words.some((word) => folded.includes(word))) return rule.intent;
  }
  return 'unknown';
}
