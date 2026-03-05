export function formatMinor(amountMinor: number, currencyCode: string): string {
  const normalizedCurrencyCode = currencyCode.trim().toUpperCase() || "CAD";
  const value = amountMinor / 100;
  const amountText = new Intl.NumberFormat(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(value);
  return `${normalizedCurrencyCode} ${amountText}`;
}

export function formatMinorCompact(amountMinor: number): string {
  const value = amountMinor / 100;
  return new Intl.NumberFormat(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2
  }).format(value);
}

export function currentMonth(): string {
  const now = new Date();
  const month = `${now.getMonth() + 1}`.padStart(2, "0");
  return `${now.getFullYear()}-${month}`;
}
