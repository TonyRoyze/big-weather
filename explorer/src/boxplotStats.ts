export type SiteValue = {location_id: string; name: string; elevation_m: number; mean: number; count: number};
const bands = [
  {label: 'Below 500 m', color: '#28747a'},
  {label: '500–<1,500 m', color: '#617aaf'},
  {label: '1,500 m and above', color: '#ad7047'},
];
function quantile(sorted: number[], fraction: number) {
  const index = (sorted.length - 1) * fraction, lo = Math.floor(index), weight = index - lo;
  return sorted[lo] * (1 - weight) + sorted[Math.ceil(index)] * weight;
}
export function elevationBoxes(sites: SiteValue[]) {
  return bands.map((band, index) => {
    const points = sites.filter(p => Number.isFinite(p.mean) && Number.isFinite(p.elevation_m) && p.count > 0 && (p.elevation_m < 500 ? 0 : p.elevation_m < 1500 ? 1 : 2) === index);
    const values = points.map(p => p.mean).sort((a, b) => a - b);
    if (!values.length) return {...band, points, stats: null};
    const q1 = quantile(values, .25), median = quantile(values, .5), q3 = quantile(values, .75), iqr = q3 - q1;
    const inside = values.filter(v => v >= q1 - 1.5 * iqr && v <= q3 + 1.5 * iqr);
    return {...band, points, stats: {q1, median, q3, low: inside[0], high: inside.at(-1)!}};
  });
}
