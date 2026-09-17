import Delaunator from 'delaunator';
import {color, type Location} from './data';

export type WeatherPoint = Location & {value: number | null};

/** Connect nearby samples only. Missing vertices leave holes; no extrapolation. */
export function weatherSurface(points: WeatherPoint[], min: number, max: number, exaggeration: number) {
  const unique = new Map<string, WeatherPoint>();
  for (const p of points) {
    if ([p.longitude, p.latitude, p.elevation_m].every(Number.isFinite)) {
      unique.set(`${p.longitude},${p.latitude}`, p);
    }
  }
  const samples = [...unique.values()];
  if (samples.length < 3) return null;
  // Locally scaled coordinates for triangulation, not for rendering.
  const latitude = samples.reduce((sum, p) => sum + p.latitude, 0) / samples.length;
  const scale = Math.cos(latitude * Math.PI / 180);
  const triangulation = Delaunator.from(samples, p => p.longitude * scale, p => p.latitude);
  const positions: number[] = [], colors: number[] = [];
  const distance = (a: WeatherPoint, b: WeatherPoint) => {
    const radians = Math.PI / 180;
    const h = Math.sin((b.latitude - a.latitude) * radians / 2) ** 2 +
      Math.cos(a.latitude * radians) * Math.cos(b.latitude * radians) *
      Math.sin((b.longitude - a.longitude) * radians / 2) ** 2;
    return 12742 * Math.asin(Math.sqrt(Math.min(1, h)));
  };
  for (let i = 0; i < triangulation.triangles.length; i += 3) {
    const triangle = Array.from(triangulation.triangles.slice(i, i + 3), index => samples[index]);
    if (triangle.some(p => p.value === null || !Number.isFinite(p.value))) continue;
    if (triangle.some((p, j) => distance(p, triangle[(j + 1) % 3]) > 250)) continue;
    for (const p of triangle) {
      positions.push(p.longitude, p.latitude, p.elevation_m * exaggeration + 150);
      colors.push(...color(p.value, min, max).slice(0, 3).map(c => c / 255));
    }
  }
  if (!positions.length) return null;
  return {attributes: {
    positions: {size: 3, value: new Float32Array(positions)},
    colors: {size: 3, value: new Float32Array(colors)},
  }};
}
