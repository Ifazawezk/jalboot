import type { Refund, RefundDecision, RefundStatus, RefundSummary } from '../api/types';
import type { MessageKey } from '../i18n/en';

// Limits are not defined here. They come from GET /policy, and each Refund says who may
// decide it. This is only the shortest reason that still tells a customer something.
export const MIN_REJECT_NOTE = 8;

export function isOpen(status: RefundStatus): boolean {
  return status === 'pending';
}

/** Flagged refunds first, then oldest first, so the riskiest and longest waits lead. */
export function sortQueue(refunds: Refund[]): Refund[] {
  return refunds
    .filter((r) => isOpen(r.status))
    .sort(
      (a, b) =>
        Number(b.risks.length > 0) - Number(a.risks.length > 0) ||
        Date.parse(a.requestedAt) - Date.parse(b.requestedAt),
    );
}

export function decidedOnly(refunds: Refund[]): Refund[] {
  return refunds
    .filter((r) => !isOpen(r.status))
    .sort((a, b) => Date.parse(b.decidedAt ?? '') - Date.parse(a.decidedAt ?? ''));
}

/** What the customer's refund card says. Timed means the server gave the timings. */
export function refundBodyKey(refund: RefundSummary, timed: boolean): MessageKey {
  if (refund.status === 'pending') return 'refund.body.pending';
  if (refund.status === 'rejected') return 'refund.body.rejected';
  if (refund.destination === 'credit') return 'refund.body.credit';
  return timed ? 'refund.body.doneTimed' : 'refund.body.done';
}

export type DecisionProblem = 'note_required' | null;

export function checkDecision(action: RefundDecision['action'], note: string): DecisionProblem {
  if (action === 'reject' && note.trim().length < MIN_REJECT_NOTE) return 'note_required';
  return null;
}

/** Where keyboard focus goes after a decision: the next open refund, else the one before. */
export function nextFocusAfter(queue: Refund[], decidedId: string): string | null {
  const index = queue.findIndex((r) => r.id === decidedId);
  if (index === -1) return queue[0]?.id ?? null;
  return queue[index + 1]?.id ?? queue[index - 1]?.id ?? null;
}

export function applyDecision(
  refund: Refund,
  decision: RefundDecision,
  agentName: string,
  at: string,
): Refund {
  return {
    ...refund,
    status: decision.action === 'approve' ? 'approved' : 'rejected',
    decidedBy: agentName,
    decidedAt: at,
    note: decision.note.trim() || null,
    version: refund.version + 1,
  };
}
