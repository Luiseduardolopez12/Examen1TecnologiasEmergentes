const moneda0 = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const moneda2 = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 2 });
const entero = new Intl.NumberFormat('es-HN', { maximumFractionDigits: 0 });
const compacto = new Intl.NumberFormat('es-HN', { notation: 'compact', maximumFractionDigits: 1 });

export const dinero = (n: number) => moneda0.format(n);
export const dinero2 = (n: number) => moneda2.format(n);
export const numero = (n: number) => entero.format(n);
export const porcentaje = (n: number) => `${n.toFixed(1)} %`;
export const dineroCompacto = (n: number) => `$${compacto.format(n)}`;

/** Fecha de SQL Server ("2016-05-31" o "2026-11-13T01:11:05.72") a texto legible. */
export function fecha(valor: string | null | undefined, conHora = false): string {
  if (!valor) return '—';
  const d = new Date(valor.length === 10 ? `${valor}T00:00:00` : valor);
  if (isNaN(d.getTime())) return valor;
  return d.toLocaleString('es-HN', conHora
    ? { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }
    : { day: '2-digit', month: 'short', year: 'numeric' });
}
