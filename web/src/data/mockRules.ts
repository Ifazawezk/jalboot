import type { Policy } from '../api/types';

// Values the mock states or enforces. Each one must equal the matching key in
// knowledge/rules.json, and src/lib/rules.test.ts fails if they drift apart.
export const MOCK_RULES = {
  policyVersion: '2026.11',
  refundAutomatedLimitQar: 50,
  refundNewAccountLimitQar: 25,
  refundNewAccountAgeDays: 7,
  refundAgentLimitQar: 300,
  refundCardBusinessDays: 7,
  refundCreditMinutes: 15,
  repeatClaimsFrom: 3,
  repeatClaimsWindowDays: 30,
  lateFirstTierMinutes: 20,
  lateFirstTierCreditQar: 5,
  cancelGraceMinutes: 2,
  cancelFoodPreparingPct: 50,
  cancelFoodReadyPct: 100,
  otpMaxFailures: 5,
  otpLockMinutes: 30,
  feeZoneAFoodQar: 5,
  feeZoneCGroceryQar: 15,
  serviceFeePct: 3,
  serviceFeeMinQar: 1,
  serviceFeeMaxQar: 7,
  promoSave20MinSpendQar: 60,
} as const;

export const MOCK_POLICY: Policy = {
  policyVersion: MOCK_RULES.policyVersion,
  currency: 'QAR',
  refund: {
    automatedLimitQar: MOCK_RULES.refundAutomatedLimitQar,
    newAccountAutomatedLimitQar: MOCK_RULES.refundNewAccountLimitQar,
    agentLimitQar: MOCK_RULES.refundAgentLimitQar,
    cardBusinessDays: MOCK_RULES.refundCardBusinessDays,
    creditMinutes: MOCK_RULES.refundCreditMinutes,
  },
};
