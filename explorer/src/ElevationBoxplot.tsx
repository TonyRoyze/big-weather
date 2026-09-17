import {useState} from 'react';
import {elevationBoxes, type SiteValue} from './boxplotStats';
import {useChartWidth} from './useChartWidth';

const fmt = (v: number) => v.toLocaleString(undefined, {maximumFractionDigits: 2});
export function ElevationBoxplot({sites, label, unit, start, end}: {sites: SiteValue[]; label: string; unit: string; start: string; end: string}) {
  const {ref, width} = useChartWidth();
  const [active, setActive] = useState('');
  const boxes = elevationBoxes(sites), values = boxes.flatMap(b => b.points.map(p => p.mean));
  const height = 390, left = 70, right = 16, top = 28, bottom = 75;
  const min = values.length ? Math.min(...values) : 0, max = values.length ? Math.max(...values) : 1;
  const pad = (max - min || Math.abs(min) || 1) * .12;
  const y = (v: number) => top + (max + pad - v) / (max - min + 2 * pad) * (height - top - bottom);
  const step = (width - left - right) / 3, boxWidth = Math.min(80, step * .52);
  const x = (i: number) => left + step * (i + .5);
  return <section className="analytics-panel elevation-boxplot"><div className="analytics-heading"><h2>{label} by elevation band</h2><span>{start} — {end}</span></div>
    <p className="hint">One point per location: average over its available complete days in the loaded range. Rainfall uses the average daily total. All locations have equal weight here.</p>
    {!values.length ? <p className="muted">No complete daily observations for this selection.</p> : <>
      <svg ref={ref} className="analytics-svg" height={height} viewBox={`0 0 ${width} ${height}`} role="group" aria-label={`${label} boxplots by elevation band from ${start} to ${end}`}>
        <text x={left} y={14}>{unit}</text>
        {Array.from({length: 5}, (_, i) => {const value = min - pad + i * (max - min + 2 * pad) / 4; return <g key={i}><line x1={left} x2={width-right} y1={y(value)} y2={y(value)} stroke="#e8ecee"/><text x={left-8} y={y(value)+4} textAnchor="end">{fmt(value)}</text></g>;})}
        {boxes.map((b, i) => {const s = b.stats, cx = x(i); const description = s ? `${b.label}: ${b.points.length} locations; median ${fmt(s.median)}, middle 50% ${fmt(s.q1)}–${fmt(s.q3)}, whiskers ${fmt(s.low)}–${fmt(s.high)} ${unit}` : `${b.label}: no locations with data`; return <g key={b.label}>
          {s ? <g tabIndex={0} role="button" aria-label={description} onFocus={() => setActive(description)} onMouseEnter={() => setActive(description)} onClick={() => setActive(description)}>
            <rect x={cx-step*.42} y={top} width={step*.84} height={height-top-bottom} fill="transparent"/>
            <path d={`M${cx},${y(s.low)}V${y(s.high)} M${cx-boxWidth/3},${y(s.low)}h${boxWidth*2/3} M${cx-boxWidth/3},${y(s.high)}h${boxWidth*2/3}`} stroke={b.color}/>
            <rect x={cx-boxWidth/2} y={y(s.q3)} width={boxWidth} height={Math.max(1,y(s.q1)-y(s.q3))} fill={b.color} fillOpacity=".13" stroke={b.color}/>
            <line x1={cx-boxWidth/2} x2={cx+boxWidth/2} y1={y(s.median)} y2={y(s.median)} stroke={b.color} strokeWidth="3"/>
            <title>{description}</title>
          </g> : <text x={cx} y={height/2} textAnchor="middle">No data</text>}
          {b.points.map(p => {const hash = [...p.location_id].reduce((n,c) => (n*31+c.charCodeAt(0))>>>0,0); const description = `${p.name}: ${fmt(p.mean)} ${unit} · ${fmt(p.elevation_m)} m · ${p.count} complete days`; return <circle key={p.location_id} cx={cx+((hash%101)/100-.5)*boxWidth*.8} cy={y(p.mean)} r="3.5" fill={b.color} fillOpacity=".7" stroke="white" strokeWidth=".6" tabIndex={0} role="button" aria-label={description} onMouseEnter={() => setActive(description)} onFocus={() => setActive(description)} onClick={() => setActive(description)}><title>{description}</title></circle>;})}
          <text x={cx} y={height-48} textAnchor="middle">{i === 0 ? '<500 m' : i === 1 ? '500–<1,500 m' : '≥1,500 m'}</text>
          <text x={cx} y={height-27} textAnchor="middle">{b.points.length} locations</text>
        </g>;})}
      </svg>
      <div className="chart-readout" aria-live="polite">{active || 'Hover, tap or focus a box for quartiles, or a point for location and coverage details.'}</div>
    </>}
    <p className="hint">Boxes show the middle 50% and median; whiskers extend to values within 1.5 × IQR. All points, including outliers, remain visible. Bands stay fixed across selections. Locations can have different coverage; this chart describes associations, not causal effects.</p>
  </section>;
}
