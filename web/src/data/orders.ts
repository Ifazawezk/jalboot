import type { Locale, Order, OrderItem, Vertical } from '../api/types';
import { MOCK_RULES } from './mockRules';
import { pick, type L } from './text';

// All stores, people and orders are invented.

interface RawItem extends Omit<OrderItem, 'name'> {
  name: L;
}

interface RawOrder {
  id: string;
  vertical: Vertical;
  status: string;
  store: L;
  area: L;
  placedMinutesAgo: number;
  etaInMinutes: number | null;
  deliveredMinutesAgo: number | null;
  rider: L | null;
  items: RawItem[];
  deliveryFeeQar: number;
}

const ORDERS = {
  late: {
    id: 'JB-48213',
    vertical: 'food',
    status: 'on_the_way',
    store: { en: 'Saffron Door Kitchen', ar: 'مطبخ باب الزعفران' },
    area: { en: 'West Bay', ar: 'الخليج الغربي' },
    placedMinutesAgo: 38,
    etaInMinutes: 14,
    deliveredMinutesAgo: null,
    rider: { en: 'Salim', ar: 'سالم' },
    items: [
      { name: { en: 'Chicken machboos', ar: 'مجبوس دجاج' }, qty: 1, priceQar: 42 },
      { name: { en: 'Karak tea', ar: 'شاي كرك' }, qty: 2, priceQar: 6 },
    ],
    deliveryFeeQar: MOCK_RULES.feeZoneAFoodQar,
  },
  missing: {
    id: 'JB-47902',
    vertical: 'grocery',
    status: 'delivered',
    store: { en: 'Madinat Greens Market', ar: 'سوق مدينة الخضار' },
    area: { en: 'Al Wakrah', ar: 'الوكرة' },
    placedMinutesAgo: 95,
    etaInMinutes: null,
    deliveredMinutesAgo: 35,
    rider: { en: 'Imran', ar: 'عمران' },
    items: [
      { name: { en: 'Fresh laban, 1 litre', ar: 'لبن طازج، لتر واحد' }, qty: 2, priceQar: 9.25 },
      { name: { en: 'Khalas dates, 3 kg box', ar: 'تمر خلاص، علبة 3 كيلو' }, qty: 1, priceQar: 62.5, flag: 'missing' },
      { name: { en: 'Arabic bread, large', ar: 'خبز عربي، كبير' }, qty: 3, priceQar: 4 },
    ],
    deliveryFeeQar: MOCK_RULES.feeZoneCGroceryQar,
  },
} satisfies Record<string, RawOrder>;

export type OrderKey = keyof typeof ORDERS;

function roundQar(value: number): number {
  return Math.round(value * 100) / 100;
}

/** Service fee from the rules: a percentage of the items, held between a floor and a ceiling. */
export function serviceFee(subtotalQar: number): number {
  const fee = (subtotalQar * MOCK_RULES.serviceFeePct) / 100;
  return roundQar(Math.min(MOCK_RULES.serviceFeeMaxQar, Math.max(MOCK_RULES.serviceFeeMinQar, fee)));
}

export function buildOrder(key: OrderKey, locale: Locale, nowMs: number): Order {
  const raw: RawOrder = ORDERS[key];
  const minutes = (n: number) => new Date(nowMs + n * 60_000).toISOString();
  const subtotal = roundQar(raw.items.reduce((sum, item) => sum + item.qty * item.priceQar, 0));
  const fees = roundQar(raw.deliveryFeeQar + serviceFee(subtotal));
  return {
    id: raw.id,
    vertical: raw.vertical,
    status: raw.status,
    store: pick(raw.store, locale),
    area: pick(raw.area, locale),
    placedAt: minutes(-raw.placedMinutesAgo),
    etaAt: raw.etaInMinutes === null ? null : minutes(raw.etaInMinutes),
    deliveredAt: raw.deliveredMinutesAgo === null ? null : minutes(-raw.deliveredMinutesAgo),
    rider: raw.rider ? pick(raw.rider, locale) : null,
    items: raw.items.map((item) => ({ ...item, name: pick(item.name, locale) })),
    feesQar: fees,
    totalQar: roundQar(subtotal + fees),
  };
}
