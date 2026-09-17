import {describe, it, expect} from 'vitest';
import {color, dayAfter, daysBetween} from './data';
describe('UTC timeline and missing weather', () => {
  it('steps through leap day and year boundaries', () => {
    expect(dayAfter('2024-02-28', 1)).toBe('2024-02-29');
    expect(dayAfter('2024-12-31', 1)).toBe('2025-01-01');
    expect(daysBetween('2024-02-28', '2024-03-01')).toBe(2);
  });
  it('distinguishes missing values from zero and handles constant ranges', () => {
    expect(color(null, 0, 1)).not.toEqual(color(0, 0, 1));
    expect(color(5, 5, 5).every(Number.isFinite)).toBe(true);
    expect(color(100, 0, 1)).toEqual(color(1, 0, 1));
  });
});
