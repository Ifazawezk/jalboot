import type { Locale } from '../api/types';

export const ORDER_STEPS = ['placed', 'getting_ready', 'on_the_way', 'delivered'] as const;
export type OrderStep = (typeof ORDER_STEPS)[number];

const STEP_BY_STATUS: Record<string, OrderStep> = {
  placed: 'placed',
  accepted: 'placed',
  preparing: 'getting_ready',
  ready: 'getting_ready',
  picking: 'getting_ready',
  packed: 'getting_ready',
  driver_assigned: 'getting_ready',
  picked_up: 'on_the_way',
  on_the_way: 'on_the_way',
  delivered: 'delivered',
};

/**
 * Each vertical has its own status path, and the card shows the same four steps for all
 * of them. Returns null for an order that stopped, such as a cancelled one.
 */
export function orderStep(status: string): OrderStep | null {
  return STEP_BY_STATUS[status] ?? null;
}

/** The line under the store name. Arabic cards leave out a name with no Arabic form. */
export function orderPlace(parts: (string | null | undefined)[], locale: Locale): string {
  return parts.filter(Boolean).join(locale === 'ar' ? '، ' : ', ');
}
