import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { extname, join } from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  CONVERSATION_EVENT_TYPES,
  DESK_EVENT_TYPES,
  STREAM_EVENT_TYPES,
} from '../api/types';
import { REFUND_SEEDS } from '../data/desk';
import { MOCK_POLICY, MOCK_RULES as M } from '../data/mockRules';
import { buildOrder, serviceFee } from '../data/orders';

// Sits next to web/ for now. Point RULES_JSON at it if the folders move.
const RULES_PATH = process.env.RULES_JSON ?? '../knowledge/rules.json';

interface Rules {
  meta: { policy_version: string };
  refunds: {
    approval_limits_qar: { automated: number; agent: number };
    new_account: { age_days: number; automated_limit_qar: number };
    repeat_claims: { window_days: number; agent_review_from_prior_claims: number };
    timing: { card_business_days: number; credit_minutes: number };
  };
  late_delivery: { tiers: { min_minutes: number; credit_qar: number }[] };
  cancellations: { grace_minutes: number; food: { preparing_charge_pct: number; ready_or_later_charge_pct: number } };
  account: { otp: { max_failures: number; lock_minutes: number } };
  fees: {
    delivery_fee_qar: { A: { food: number }; C: { grocery: number } };
    service_fee: { pct: number; min_qar: number; max_qar: number };
  };
  promos: { codes: { SAVE20: { min_spend_qar: number } } };
}

describe.runIf(existsSync(RULES_PATH))('mock values match knowledge/rules.json', () => {
  const rules = JSON.parse(readFileSync(RULES_PATH, 'utf-8')) as Rules;
  const firstTier = rules.late_delivery.tiers[0];

  it.each([
    ['policyVersion', M.policyVersion, rules.meta.policy_version],
    ['refundAutomatedLimitQar', M.refundAutomatedLimitQar, rules.refunds.approval_limits_qar.automated],
    ['refundNewAccountLimitQar', M.refundNewAccountLimitQar, rules.refunds.new_account.automated_limit_qar],
    ['refundNewAccountAgeDays', M.refundNewAccountAgeDays, rules.refunds.new_account.age_days],
    ['refundAgentLimitQar', M.refundAgentLimitQar, rules.refunds.approval_limits_qar.agent],
    ['refundCardBusinessDays', M.refundCardBusinessDays, rules.refunds.timing.card_business_days],
    ['refundCreditMinutes', M.refundCreditMinutes, rules.refunds.timing.credit_minutes],
    ['repeatClaimsFrom', M.repeatClaimsFrom, rules.refunds.repeat_claims.agent_review_from_prior_claims],
    ['repeatClaimsWindowDays', M.repeatClaimsWindowDays, rules.refunds.repeat_claims.window_days],
    ['lateFirstTierMinutes', M.lateFirstTierMinutes, firstTier?.min_minutes],
    ['lateFirstTierCreditQar', M.lateFirstTierCreditQar, firstTier?.credit_qar],
    ['cancelGraceMinutes', M.cancelGraceMinutes, rules.cancellations.grace_minutes],
    ['cancelFoodPreparingPct', M.cancelFoodPreparingPct, rules.cancellations.food.preparing_charge_pct],
    ['cancelFoodReadyPct', M.cancelFoodReadyPct, rules.cancellations.food.ready_or_later_charge_pct],
    ['otpMaxFailures', M.otpMaxFailures, rules.account.otp.max_failures],
    ['otpLockMinutes', M.otpLockMinutes, rules.account.otp.lock_minutes],
    ['feeZoneAFoodQar', M.feeZoneAFoodQar, rules.fees.delivery_fee_qar.A.food],
    ['feeZoneCGroceryQar', M.feeZoneCGroceryQar, rules.fees.delivery_fee_qar.C.grocery],
    ['serviceFeePct', M.serviceFeePct, rules.fees.service_fee.pct],
    ['serviceFeeMinQar', M.serviceFeeMinQar, rules.fees.service_fee.min_qar],
    ['serviceFeeMaxQar', M.serviceFeeMaxQar, rules.fees.service_fee.max_qar],
    ['promoSave20MinSpendQar', M.promoSave20MinSpendQar, rules.promos.codes.SAVE20.min_spend_qar],
  ])('%s', (_name, mock, actual) => {
    expect(mock).toBe(actual);
  });
});

describe('sample data follows the policy', () => {
  it('serves the policy from the same values', () => {
    expect(MOCK_POLICY.refund.automatedLimitQar).toBe(M.refundAutomatedLimitQar);
    expect(MOCK_POLICY.refund.agentLimitQar).toBe(M.refundAgentLimitQar);
  });

  it('only queues a refund at or under the automated limit when a rule sends it to a person', () => {
    const open = REFUND_SEEDS.filter((r) => r.status === 'pending');
    for (const refund of open) {
      if (refund.amountQar <= M.refundAutomatedLimitQar) {
        expect(refund.risks.length, refund.id).toBeGreaterThan(0);
      }
    }
  });

  it('adds up every sample order, fees included', () => {
    for (const key of ['late', 'missing'] as const) {
      const order = buildOrder(key, 'en', 0);
      const items = order.items.reduce((sum, item) => sum + item.qty * item.priceQar, 0);
      expect(order.totalQar).toBeCloseTo(items + order.feesQar, 2);
    }
    expect(buildOrder('late', 'en', 0).feesQar).toBe(6.62);
    expect(serviceFee(1000)).toBe(M.serviceFeeMaxQar);
    expect(serviceFee(1)).toBe(M.serviceFeeMinQar);
  });
});

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
}

const SOURCE_FILES = [
  ...walk('src').filter((path) => ['.ts', '.tsx', '.css'].includes(extname(path))),
  'index.html',
  'API.md',
].filter((path) => !path.endsWith('.test.ts'));

describe('repository rules', () => {
  const texts = SOURCE_FILES.map((path) => [path, readFileSync(path, 'utf-8')] as const);

  it('has no em dashes or en dashes', () => {
    for (const [path, text] of texts) expect(/[\u2013\u2014]/.test(text), path).toBe(false);
  });

  it('has no hidden characters, which GitHub flags on public files', () => {
    const everything = walk('src')
      .filter((path) => ['.ts', '.tsx', '.css'].includes(extname(path)))
      .concat('index.html', 'API.md', 'e2e/run.mjs');
    const codes = [0x200b, 0x200e, 0x200f, 0x202a, 0x202b, 0x202e, 0x2066, 0x2067, 0x2068, 0x2069, 0xfeff];
    const hidden = new RegExp(`[${String.fromCharCode(...codes)}]`);
    for (const path of everything) expect(hidden.test(readFileSync(path, 'utf-8')), path).toBe(false);
  });

  it('has no emoji', () => {
    for (const [path, text] of texts) expect(/\p{Extended_Pictographic}/u.test(text), path).toBe(false);
  });

  it('has no leftover brand placeholder', () => {
    for (const [path, text] of texts) expect(text.includes('{{BRAND}}'), path).toBe(false);
  });

  it('has no fixed tool list and no hardcoded refund limit in the UI', () => {
    for (const [path, text] of texts) {
      expect(/TOOL_NAMES|KnownTool|AUTO_APPROVE_LIMIT/.test(text), path).toBe(false);
    }
  });

  it('keeps the desk token out of browser storage', () => {
    for (const [path, text] of texts) {
      // API.md is allowed to name it, because it tells people not to use it.
      if (path !== 'API.md') expect(text.includes('sessionStorage'), path).toBe(false);
    }
  });
});

describe('API.md', () => {
  const doc = readFileSync('API.md', 'utf-8');

  it.each([...STREAM_EVENT_TYPES, ...CONVERSATION_EVENT_TYPES, ...DESK_EVENT_TYPES])('documents %s', (name) => {
    expect(doc).toContain(`\`${name}\``);
  });

  it.each([
    'GET /policy',
    'POST /conversations',
    'POST /conversations/{id}/messages',
    'POST /conversations/{id}/verify/start',
    'POST /conversations/{id}/verify/confirm',
    'POST /conversations/{id}/handoff',
    'GET /conversations/{id}/events',
    'POST /desk/session',
    'GET /desk/me',
    'POST /desk/logout',
    'GET /desk/summary',
    'GET /desk/conversations',
    'POST /desk/conversations/{id}/claim',
    'POST /desk/conversations/{id}/reply',
    'GET /desk/refunds',
    'POST /desk/refunds/{id}/decision',
    'GET /desk/audit',
    'GET /desk/metrics/top-issues',
    'GET /desk/metrics/quality',
    'GET /desk/events',
  ])('documents %s', (route) => {
    expect(doc).toContain(`\`${route}`);
  });

  it('documents the desk security rules', () => {
    for (const term of ['jalboot_desk', 'HttpOnly', 'SameSite=Lax', 'X-CSRF-Token', 'csrf_failed']) {
      expect(doc).toContain(term);
    }
  });
});
