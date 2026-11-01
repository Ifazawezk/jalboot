/** Arabic keyboards often type Arabic-Indic or Persian digits. The API only takes ASCII. */
export function toAsciiDigits(text: string): string {
  return text
    .replace(/[\u0660-\u0669]/g, (d) => String(d.charCodeAt(0) - 0x0660))
    .replace(/[\u06F0-\u06F9]/g, (d) => String(d.charCodeAt(0) - 0x06f0));
}

/** Turns what a customer typed into E.164, or null if it is not a Qatar number. */
export function normalizePhone(input: string): string | null {
  const digits = toAsciiDigits(input).replace(/[\s\-()]/g, '');
  const match = /^(?:\+974|00974|974)?(\d{8})$/.exec(digits);
  return match ? `+974${match[1]}` : null;
}

export function normalizeCode(input: string): string {
  return toAsciiDigits(input).replace(/\D/g, '');
}
