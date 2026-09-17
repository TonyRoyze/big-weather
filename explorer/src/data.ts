export type Location = {location_id: string; name: string; country: string; region: string; latitude: number; longitude: number; elevation_m: number};
export type Feature = {id: string; label: string; unit: string; aggregation: string};
export type Metadata = {version: string; fingerprint: string; preview: boolean; start: string; end: string; attribution: string; locations: Location[]; features: Feature[]};
export type Observation = {location_id: string; date: string; value: number | null; hours: number};
export type WindowData = {aggregation?: string; period?: import('./periods').Period; metric: string; start: string; end: string; version: string; fingerprint: string; query_ms: number; input_rows: number; records: Observation[]};
export const dayAfter = (day: string, n: number) => new Date(Date.parse(day + 'T00:00:00Z') + n * 86400000).toISOString().slice(0, 10);
export const daysBetween = (a: string, b: string) => Math.round((Date.parse(b) - Date.parse(a)) / 86400000);
export function color(value: number | null, min: number, max: number): [number, number, number, number] {
  if (value === null) return [104, 126, 137, 160];
  const t = max === min ? 0.5 : Math.min(1, Math.max(0, (value - min) / (max - min)));
  const stops = [[79, 166, 194], [165, 215, 170], [246, 209, 119], [230, 115, 77]];
  const i = Math.min(2, Math.floor(t * 3)), f = t * 3 - i;
  return [...stops[i].map((v, j) => Math.round(v + (stops[i + 1][j] - v) * f)), 255] as [number, number, number, number];
}
export async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, {signal});
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status}).`);
  }
  return response.json();
}
