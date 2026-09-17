import {dayAfter, daysBetween} from './data';
export type Period = 'daily' | 'weekly' | 'monthly' | 'yearly';
export const limits: Record<Period, number> = {daily: 93, weekly: 366, monthly: 1096, yearly: 3660};
export function periodStart(day: string, period: Period): string {
  if (period === 'monthly') return day.slice(0, 7) + '-01';
  if (period === 'yearly') return day.slice(0, 4) + '-01-01';
  if (period === 'weekly') return dayAfter(day, -((new Date(day + 'T00:00:00Z').getUTCDay() + 6) % 7));
  return day;
}
export function nextPeriod(day: string, period: Period, n = 1): string {
  const d = new Date(day + 'T00:00:00Z');
  if (period === 'monthly') d.setUTCMonth(d.getUTCMonth() + n);
  else if (period === 'yearly') d.setUTCFullYear(d.getUTCFullYear() + n);
  else return dayAfter(day, n * (period === 'weekly' ? 7 : 1));
  return d.toISOString().slice(0, 10);
}
export function periodDates(start: string, end: string, period: Period): string[] {
  const result: string[] = [];
  for (let day = periodStart(start, period); day <= end; day = nextPeriod(day, period)) result.push(day);
  return result;
}
export function weekValue(day: string): string {
  const monday = periodStart(day, 'weekly'), thursday = dayAfter(monday, 3), year = thursday.slice(0, 4);
  return `${year}-W${String(1 + Math.round(daysBetween(periodStart(`${year}-01-04`, 'weekly'), monday) / 7)).padStart(2, '0')}`;
}
export function fromWeek(value: string): string {
  const [year, week] = value.split('-W');
  return dayAfter(periodStart(`${year}-01-04`, 'weekly'), (Number(week) - 1) * 7);
}
export function periodLabel(day: string, period: Period): string {
  if (!day) return '';
  if (period === 'yearly') return day.slice(0, 4);
  if (period === 'monthly') return new Date(day + 'T00:00:00Z').toLocaleDateString('en-GB', {month: 'short', year: 'numeric', timeZone: 'UTC'});
  return period === 'weekly' ? `Week of ${day}` : day;
}
