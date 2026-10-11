export const number = (value: number, digits = 0) => new Intl.NumberFormat('en-IN', { maximumFractionDigits: digits }).format(value);
export const label = (value: string) => value.replaceAll('_', ' ').replace(/\b\w/g, char => char.toUpperCase());
