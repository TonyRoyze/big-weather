import {describe, expect, it} from 'vitest';
import {periodDates, periodStart, nextPeriod, weekValue, fromWeek} from './periods';
describe('calendar periods', () => {
  it('uses ISO weeks across year boundaries', () => {
    expect(weekValue('2021-01-01')).toBe('2020-W53');
    expect(fromWeek('2020-W53')).toBe('2020-12-28');
    expect(periodStart('2024-03-03', 'weekly')).toBe('2024-02-26');
  });
  it('includes leap days and clipped boundary periods', () => {
    expect(periodDates('2024-02-28', '2024-03-01', 'daily')).toHaveLength(3);
    expect(periodDates('2024-01-31', '2024-03-01', 'monthly')).toEqual(['2024-01-01', '2024-02-01', '2024-03-01']);
    expect(nextPeriod('2024-02-01', 'monthly')).toBe('2024-03-01');
    expect(periodDates('2023-12-31', '2025-01-01', 'yearly')).toEqual(['2023-01-01', '2024-01-01', '2025-01-01']);
  });
});
