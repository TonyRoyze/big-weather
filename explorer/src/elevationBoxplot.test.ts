import {describe, expect, it} from 'vitest';
import {elevationBoxes, type SiteValue} from './boxplotStats';
const point = (mean: number, elevation_m = 0, count = 1): SiteValue => ({mean, elevation_m, count, name: 'Site', location_id: `${mean}:${elevation_m}`});
describe('elevation-band distributions', () => {
  it('uses fixed boundaries, includes zero, and excludes missing or incomplete sites', () => {
    const b = elevationBoxes([point(0, 499), point(2, 500), point(3, 1499), point(4, 1500), point(NaN), point(1, NaN), point(8, 1, 0)]);
    expect(b.map(v => v.points.length)).toEqual([1,2,1]);
    expect(b[0].stats?.median).toBe(0);
    expect(b[1].stats?.median).toBe(2.5);
  });
  it('computes interpolated quartiles and whiskers without removing outliers', () => {
    const b = elevationBoxes([0,1,2,3,4,5,100].map(v => point(v)))[0];
    expect(b.stats).toEqual({q1: 1.5, median: 3, q3: 4.5, low: 0, high: 5});
    expect(b.points).toHaveLength(7);
  });
  it('handles empty and constant groups and weights locations equally', () => {
    expect(elevationBoxes([]).every(b => b.stats === null)).toBe(true);
    expect(elevationBoxes([point(5), point(5)])[0].stats).toEqual({q1:5, median:5, q3:5, low:5, high:5});
    expect(elevationBoxes([point(0,0,90),point(10,0,1)])[0].stats?.median).toBe(5);
  });
});
