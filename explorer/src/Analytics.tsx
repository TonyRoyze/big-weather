import {useEffect, useMemo, useState} from 'react';
import {getJson, type Location, type Metadata, type WindowData} from './data';
import {periodDates, periodLabel, type Period} from './periods';
import './analytics.css';
import {ElevationBoxplot} from './ElevationBoxplot';
import {useChartWidth} from './useChartWidth';

type Stats = {count: number; mean: number; min: number; max: number; median: number; variance: number};
type Band = {id: number; label: string; color: string};
type Point = {band: number; bucket: string; mean: number; variance: number; count: number};
type Summary = {stats: Stats | null; timeline: Record<string, Point[]>; scatter: {location_id: string; name: string; elevation_m: number; band: number; mean: number; count: number}[]; histogram: {low: number; high: number; count: number}[]};
type AnalyticsData = {bands: Band[]; metrics: Record<string, Summary>};
const metrics = ['wind_speed_10m', 'relative_humidity_2m', 'surface_pressure'];
const fmt = (value: number) => value.toLocaleString(undefined, {maximumFractionDigits: 2});
const W = 760, H = 260, L = 68, R = 24, T = 20, B = 42;
function scale(min: number, max: number, a: number, b: number) {return (v: number) => a + (v - min) / (max - min || 1) * (b - a);}
function extent(values: number[]): [number, number] {
  if (!values.length) return [0, 1];
  const min = Math.min(...values), max = Math.max(...values), pad = (max - min || Math.abs(min) || 1) * .12;
  return [min - pad, max + pad];
}
function Grid({bounds, unit, width = W, height = H}: {bounds: [number, number]; unit: string; width?: number; height?: number}) {
  return <>{Array.from({length: 5}, (_, i) => {const y = T + i * (height - T - B) / 4; return <g key={i}><line x1={L} x2={width - R} y1={y} y2={y} stroke="#e8ecee"/><text x={L - 10} y={y + 4} textAnchor="end">{fmt(bounds[1] - i * (bounds[1] - bounds[0]) / 4)}</text></g>;})}<text x={L} y={12}>{unit}</text></>;
}
function Timeline({summary, bands, start, end, unit, label}: {summary: Summary; bands: Band[]; start: string; end: string; unit: string; label: string}) {
  const [period, setPeriod] = useState<Period>('daily');
  const [active, setActive] = useState<string | null>(null);
  const points = summary.timeline[period];
  const dates = useMemo(() => periodDates(start, end, period), [start, end, period]);
  const dateIndex = new Map(dates.map((d, i) => [d, i]));
  const byKey = new Map(points.map(p => [`${p.band}:${p.bucket}`, p]));
  const bounds = extent(points.flatMap(p => period === 'daily' ? [p.mean] : [p.mean - Math.sqrt(p.variance), p.mean + Math.sqrt(p.variance)]));
  const x = scale(0, Math.max(1, dates.length - 1), L, W - R), y = scale(...bounds, H - B, T);
  const shown = points.filter(p => p.bucket === active);
  return <section className="analytics-panel"><div className="analytics-heading"><h2>{label} across elevations</h2><label>Timeline<select aria-label="Timeline" value={period} onChange={e => {setPeriod(e.target.value as Period); setActive(null);}}><option value="daily">Daily</option><option value="weekly">Weekly average</option><option value="monthly">Monthly average</option></select></label></div>
    <div className="band-legend">{bands.map(b => <span key={b.id}><i style={{background: b.color}}/>{b.label}</span>)}</div>
    {!points.length ? <p className="muted">No complete daily observations in this selection.</p> : <>
      <svg className="analytics-svg" viewBox={`0 0 ${W} ${H}`} aria-label={`${label} timeline by elevation class`} role="group" onMouseLeave={() => setActive(null)}>
        <Grid bounds={bounds} unit={unit}/>
        {bands.map(b => {let path = '', previous = false; dates.forEach((d, i) => {const p = byKey.get(`${b.id}:${d}`); if (!p) {previous = false; return;} path += `${previous ? 'L' : 'M'}${x(i)},${y(p.mean)} `; previous = true;}); return <g key={b.id}><path d={path} fill="none" stroke={b.color} strokeWidth="2"/>{points.filter(p => p.band === b.id).map(p => <circle key={p.bucket} cx={x(dateIndex.get(p.bucket)!)} cy={y(p.mean)} r="2.5" fill={b.color}/>)}</g>;})}
        {dates.map((d, i) => <rect key={d} x={x(i) - Math.max(2, (W-L-R) / dates.length / 2)} y={T} width={Math.max(4, (W-L-R) / dates.length)} height={H-B-T} fill="transparent" tabIndex={0} role="button" aria-label={`Inspect ${periodLabel(d, period)}`} onFocus={() => setActive(d)} onBlur={() => setActive(null)} onMouseEnter={() => setActive(d)} onClick={() => setActive(d)}/>)}
        {shown.map(p => {const px = x(dateIndex.get(p.bucket)!), sd = Math.sqrt(p.variance), color = bands[p.band].color; return <g key={p.band} pointerEvents="none">{period !== 'daily' && <path d={`M${px},${y(p.mean-sd)}V${y(p.mean+sd)} M${px-6},${y(p.mean-sd)}h12 M${px-6},${y(p.mean+sd)}h12`} stroke={color} strokeWidth="3"/>}<circle cx={px} cy={y(p.mean)} r="5" fill={color} stroke="white"/></g>;})}
        {[0, Math.floor((dates.length-1)/2), dates.length-1].filter((v, i, a) => a.indexOf(v) === i).map(i => <text key={i} x={x(i)} y={H-12} textAnchor={i === 0 ? 'start' : i === dates.length-1 ? 'end' : 'middle'}>{dates[i]}</text>)}
      </svg>
      <div className="chart-readout" aria-live="polite">{shown.length ? <><strong>{periodLabel(active!, period)}</strong>{shown.map(p => <span key={p.band} style={{borderLeft: `3px solid ${bands[p.band].color}`}}>{bands[p.band].label}: {fmt(p.mean)} {unit} · variance {fmt(p.variance)} ({unit})² · n={p.count}</span>)}</> : 'Hover, tap or focus a date to inspect each elevation class.'}</div>
    </>}
    <p className="hint">Each line averages available location-days within its elevation class. Weekly and monthly hover bars show ±1 standard deviation; variance is shown in squared units. Missing periods remain gaps.</p>
  </section>;
}
function Scatter({summary, bands, label, unit}: {summary: Summary; bands: Band[]; label: string; unit: string}) {
  const {ref, width: W} = useChartWidth(), H = 380;
  const [active, setActive] = useState<string | null>(null);
  const bounds = extent(summary.scatter.map(p => p.mean)), xb = extent(summary.scatter.map(p => p.elevation_m));
  const x = scale(...xb, L, W-R), y = scale(...bounds, H-B, T);
  const selected = summary.scatter.find(p => p.location_id === active);
  return <section className="analytics-panel"><h3>{label} vs elevation</h3>{!summary.scatter.length ? <p className="muted">No complete daily observations.</p> : <>
    <svg ref={ref} className="analytics-svg tall-chart" height={H} viewBox={`0 0 ${W} ${H}`} role="group" aria-label={`${label} versus elevation, location means`}>
      <Grid bounds={bounds} unit={unit} width={W} height={H}/>
      {summary.scatter.map(p => <g key={p.location_id}>
        <circle tabIndex={0} role="button" aria-label={`${p.name}: ${fmt(p.mean)} ${unit}, elevation ${fmt(p.elevation_m)} m`} onMouseEnter={() => setActive(p.location_id)} onFocus={() => setActive(p.location_id)} onClick={() => setActive(p.location_id)} cx={x(p.elevation_m)} cy={y(p.mean)} r={active === p.location_id ? 7 : 5} fill={bands[p.band].color}><title>{p.name}: {fmt(p.elevation_m)} m; {fmt(p.mean)} {unit}; {p.count} days</title></circle>
      </g>)}
      {[0,1,2,3].map(i => <text key={i} x={L+i*(W-L-R)/3} y={H-22} textAnchor={i === 0 ? 'start' : i === 3 ? 'end' : 'middle'}>{Math.round(xb[0]+i*(xb[1]-xb[0])/3).toLocaleString()}</text>)}<text x={W/2} y={H-2} textAnchor="middle">Elevation (m)</text>
    </svg>
    <div className="chart-readout" aria-live="polite">{selected ? `${selected.name}: ${fmt(selected.mean)} ${unit} · ${fmt(selected.elevation_m)} m · ${selected.count} complete days` : 'Hover, tap or focus a point for its value and location details.'}</div>
  </>}</section>;
}
function Histogram({summary, label, unit}: {summary: Summary; label: string; unit: string}) {
  const {ref, width: W} = useChartWidth(), H = 380;
  const [active, setActive] = useState<number | null>(null);
  const bins = summary.histogram, max = Math.max(1, ...bins.map(b => b.count)) * 1.12;
  const y = scale(0, max, H-B, T), width = (W-L-R)/Math.max(1,bins.length);
  const selected = active === null ? undefined : bins[active];
  return <section className="analytics-panel"><h3>{label} distribution</h3>{!bins.length ? <p className="muted">No complete daily observations.</p> : <>
    <svg ref={ref} className="analytics-svg tall-chart" height={H} viewBox={`0 0 ${W} ${H}`} role="group" aria-label={`${label} histogram of daily observations`}>
      <Grid bounds={[0,max]} unit="Location-days" width={W} height={H}/>
      {bins.map((b,i) => <g key={i}>
        <rect tabIndex={0} role="button" aria-label={`${fmt(b.low)}–${fmt(b.high)} ${unit}: ${b.count} location-days`} onMouseEnter={() => setActive(i)} onFocus={() => setActive(i)} onClick={() => setActive(i)} x={L+i*width+1} y={y(b.count)} width={Math.max(1,width-2)} height={Math.max(1,H-B-y(b.count))} fill="#28747a" fillOpacity={active === i ? 1 : .8}><title>{fmt(b.low)}–{fmt(b.high)} {unit}: {b.count} location-days</title></rect>
        <text className="bin-value" x={L+(i+.5)*width} y={y(b.count)-8-(width < 20 && i % 2 ? 12 : 0)} textAnchor="middle">{b.count}</text>
      </g>)}
      <text x={L} y={H-20}>{fmt(bins[0].low)}</text><text x={W-R} y={H-20} textAnchor="end">{fmt(bins.at(-1)!.high)}</text><text x={W/2} y={H-2} textAnchor="middle">{unit}</text>
    </svg>
    <div className="chart-readout" aria-live="polite">{selected ? `${fmt(selected.low)}–${fmt(selected.high)} ${unit}: ${selected.count.toLocaleString()} location-days` : 'Labels show the count in each bin. Hover, tap or focus a bar for its value range.'}</div>
  </>}</section>;
}
export function Analytics({meta, data, locations}: {meta: Metadata; data: WindowData; locations: Location[]}) {
  const [result, setResult] = useState<AnalyticsData>();
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const ids = locations.map(l => l.location_id).sort().join(',');
  useEffect(() => {
    const controller = new AbortController(); setResult(undefined); setError('');
    const params = new URLSearchParams({metric: data.metric, start: data.start, end: data.end, fingerprint: data.fingerprint});
    ids.split(',').forEach(id => params.append('locations', id));
    getJson<AnalyticsData>('/api/analytics?' + params, controller.signal).then(r => {if (!controller.signal.aborted) setResult(r);}).catch(e => {if (!controller.signal.aborted) setError(e.message);});
    return () => controller.abort();
  }, [data.metric, data.start, data.end, data.fingerprint, ids, attempt]);
  const feature = meta.features.find(f => f.id === data.metric)!;
  return <div className="analytics" aria-label="Weather analytics"><div className="analytics-heading"><h2>Weather in context</h2><span>{data.start} — {data.end} · {[...new Set(locations.map(l => l.country))].join(', ')} · {locations.length} locations</span></div>
    <p className="hint">Statistics use complete UTC daily values across the loaded selection, independent of map playback and map aggregation. Each location-day has equal weight. Variance is population variance.</p>
    {error ? <div role="alert" className="error">{error} <button onClick={() => setAttempt(a => a+1)}>Retry charts</button></div> : !result ? <p role="status">Loading weather summaries…</p> : <>
      <div className="kpi-grid">{metrics.map(id => {const f = meta.features.find(f => f.id === id), s = result.metrics[id]?.stats; const label = f?.label || ({wind_speed_10m: 'Wind speed', relative_humidity_2m: 'Relative humidity', surface_pressure: 'Surface pressure'}[id]); return <section className="weather-kpi" key={id}><h3>Average {label?.toLowerCase()}</h3><div className="kpi-value">{s ? fmt(s.mean) : '—'} <small>{f?.unit}</small></div>{s ? <><dl>{(['min','max','median','variance'] as const).map(k => <div key={k}><dt>{k === 'variance' ? `Variance (${f?.unit})²` : k[0].toUpperCase() + k.slice(1)}</dt><dd>{fmt(s[k])}</dd></div>)}</dl><p className="hint">{s.count.toLocaleString()} complete location-days</p></> : <p className="hint">{f ? 'No complete daily observations.' : 'Not available in this dataset.'}</p>}</section>;})}</div>
      <ElevationBoxplot key={`${data.metric}:${data.start}:${data.end}:${data.fingerprint}:${ids}`} sites={result.metrics[data.metric].scatter} label={feature.label} unit={feature.unit} start={data.start} end={data.end}/>
      <Timeline summary={result.metrics[data.metric]} bands={result.bands} start={data.start} end={data.end} unit={feature.unit} label={feature.label}/>
      <p className="hint">{result.bands.length} equal-width elevation classes span the selected locations; regions reaching 3,000 m use five classes, others use four. Empty classes have no line. Class boundaries stay fixed over the loaded dates.</p>
      <div className="analytics-grid">{metrics.filter(id => result.metrics[id]).map(id => {const f = meta.features.find(f => f.id === id)!; return <Scatter key={id} summary={result.metrics[id]} bands={result.bands} label={f.label} unit={f.unit}/>;})}</div>
      <p className="hint">Scatter points show each location’s mean over available complete days. Colour matches the elevation classes above.</p>
      <div className="analytics-grid">{metrics.filter(id => result.metrics[id]).map(id => {const f = meta.features.find(f => f.id === id)!; return <Histogram key={id} summary={result.metrics[id]} label={f.label} unit={f.unit}/>;})}</div>
    </>}
  </div>;
}
