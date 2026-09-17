import React, {useEffect, useMemo, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import DeckGL from '@deck.gl/react';
import {MapView, type PickingInfo} from '@deck.gl/core';
import {ScatterplotLayer, LineLayer, TextLayer} from '@deck.gl/layers';
import {WeatherTerrainLayer} from './WeatherTerrainLayer';
import {Play, Pause, RotateCcw, LoaderCircle, SlidersHorizontal} from 'lucide-react';
import {weatherSurface} from './surface';
import {MapSettings} from './MapSettings';
import {color, dayAfter, daysBetween, getJson, type Location, type Metadata, type WindowData, type Observation} from './data';
import './style.css';
import {periodStart, nextPeriod, periodDates, periodLabel, weekValue, fromWeek, limits, type Period} from './periods';
import {TimelineSlider} from './TimelineSlider';
import {AskPage} from './AskPage';
import {Analytics} from './Analytics';
import {useChartWidth} from './useChartWidth';

type Point = Location & {value: number | null};
const initialView = {longitude: 80.65, latitude: 7.35, zoom: 7, pitch: 58, bearing: -24};
const terrainURL = import.meta.env.VITE_TERRAIN_URL || 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png';
const mapView = new MapView({repeat: false});

function History({records, unit, date}: {records: Observation[]; unit: string; date: string}) {
  const {ref, width} = useChartWidth();
  const [hovered, setHovered] = useState<string | null>(null);
  const valid = records.filter(r => r.value !== null);
  if (!valid.length) return <p className="muted">No complete observations in this window.</p>;
  const min = Math.min(...valid.map(r => r.value!)), max = Math.max(...valid.map(r => r.value!));
  const pad = (max - min || Math.abs(min) || 1) * .15, low = min-pad, high = max+pad;
  const x = (i: number) => 54 + i / Math.max(1, records.length - 1) * (width-80);
  const y = (v: number) => 276 - (v-low)/(high-low)*240;
  const active = records.find(r => r.date === (hovered || date));
  let path = '', previous = false;
  records.forEach((r, i) => {if (r.value === null) {previous = false; return;} path += `${previous ? 'L' : 'M'}${x(i)},${y(r.value)} `; previous = true;});
  const current = records.findIndex(r => r.date === date);
  const labelEvery = Math.max(1, Math.ceil(records.length / Math.max(2, Math.floor((width-80)/65))));
  return <>
    <svg ref={ref} viewBox={`0 0 ${width} 320`} role="group" aria-label={`Location history in ${unit}`}>
      <text x="54" y="16">{unit}</text>
      {[0,1,2,3,4].map(i => {const value = low+(high-low)*i/4; return <g key={i}><line x1="54" x2={width-26} y1={y(value)} y2={y(value)} stroke="#e8ecee"/><text x="46" y={y(value)+4} textAnchor="end">{value.toFixed(1)}</text></g>;})}
      <path d={path} fill="none" stroke="#28747a" strokeWidth="2.5"/>
      {current >= 0 && <line x1={x(current)} x2={x(current)} y1="24" y2="276" stroke="#74828a" strokeDasharray="3 4"/>}
      {records.map((r,i) => r.value === null ? null : <g key={r.date}>
        <circle cx={x(i)} cy={y(r.value)} r={active?.date === r.date ? 5 : 3} fill="#28747a"/>
        {(i % labelEvery === 0 || active?.date === r.date) && <text className="history-value" x={x(i)} y={y(r.value)-12} textAnchor={i === 0 ? 'start' : i === records.length-1 ? 'end' : 'middle'}>{r.value.toFixed(2)}</text>}
        <circle tabIndex={0} role="button" aria-label={`${r.date}: ${r.value.toFixed(2)} ${unit}`} cx={x(i)} cy={y(r.value)} r="10" fill="transparent" onMouseEnter={() => setHovered(r.date)} onFocus={() => setHovered(r.date)} onClick={() => setHovered(r.date)}><title>{r.date}: {r.value.toFixed(2)} {unit}</title></circle>
      </g>)}
      <text x="54" y="310">{records[0]?.date}</text><text x={width-26} y="310" textAnchor="end">{records.at(-1)?.date}</text>
    </svg>
    <div className="chart-readout" aria-live="polite">{active ? `${active.date}: ${active.value === null ? 'No complete observation' : `${active.value.toFixed(2)} ${unit}`}` : 'Hover, tap or focus a point to see its date and value.'}</div>
  </>;
}

function App() {
  const [meta, setMeta] = useState<Metadata>();
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [metric, setMetric] = useState('temperature_2m');
  const [country, setCountry] = useState('LK');
  const [aggregation, setAggregation] = useState('auto');
  const [period, setPeriod] = useState<Period>('daily');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [data, setData] = useState<WindowData>();
  const [loadedIds, setLoadedIds] = useState<string[]>([]);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [exaggeration, setExaggeration] = useState(4);
  const [terrain, setTerrain] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [surface, setSurface] = useState(true);
  const [opacity, setOpacity] = useState(75);
  const [labels, setLabels] = useState(true);
  const [terrainError, setTerrainError] = useState('');
  const [rendererError, setRendererError] = useState('');
  const [selected, setSelected] = useState('');
  const [view, setView] = useState(initialView);
  const elevationDecoder = useMemo(() => ({rScaler: 256 * exaggeration,
    gScaler: exaggeration, bScaler: exaggeration / 256, offset: -32768 * exaggeration}), [exaggeration]);
  const cache = useRef(new Map<string, WindowData>());
  const request = useRef<AbortController | null>(null);
  const [cacheHit, setCacheHit] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    getJson<Metadata>('/api/metadata', controller.signal).then(m => {
      setMeta(m); setEnd(m.end); setStart(dayAfter(m.end, -Math.min(6, daysBetween(m.start, m.end))));
      setMetric(m.features[0]?.id || '');
    }).catch(e => {if (e.name !== 'AbortError') setError(e.message);});
    return () => {controller.abort(); request.current?.abort();};
  }, []);
  const requestedLocations = useMemo(() => meta?.locations.filter(l => country === 'All countries' || l.country === country) || [], [meta, country]);
  const loadedLocations = useMemo(() => meta?.locations.filter(l => loadedIds.includes(l.location_id)) || [], [meta, loadedIds]);
  const loadedPeriod = data?.period || 'daily';
  const dates = useMemo(() => data ? periodDates(data.start, data.end, loadedPeriod) : [], [data, loadedPeriod]);
  const day = dates[index] || '';
  const count = dates.length;
  const unit = featureUnit();
  function featureUnit() {const f = meta?.features.find(f => f.id === (data?.metric || metric)); return f?.aggregation === 'sum' && data?.aggregation === 'sum' && loadedPeriod !== 'daily' ? 'mm' : f?.unit || '';}
  useEffect(() => {
    if (!playing || count < 2) return;
    const timer = window.setInterval(() => setIndex(i => (i + 1) % count), 650);
    return () => window.clearInterval(timer);
  }, [playing, count]);
  const feature = meta?.features.find(f => f.id === (data?.metric || metric));
  const aggregationLabel = ({mean: 'mean', min: 'minimum', max: 'maximum', sum: 'total'} as Record<string, string>)[data?.aggregation || feature?.aggregation || 'mean'];
  const values = useMemo(() => data?.records.flatMap(r => r.value === null ? [] : [r.value]) || [], [data]);
  const min = values.length ? Math.min(...values) : 0, max = values.length ? Math.max(...values) : 1;
  const points: Point[] = useMemo(() => {
    const observations = new Map(data?.records.filter(r => r.date === day).map(r => [r.location_id, r.value]));
    return (data ? loadedLocations : requestedLocations).map(l => ({...l, value: observations.get(l.location_id) ?? null}));
  }, [data, day, loadedLocations, requestedLocations]);
  const mesh = useMemo(() => weatherSurface(points, min, max, exaggeration), [points, min, max, exaggeration]);
  const chosen = points.find(p => p.location_id === selected);
  const history = useMemo(() => {
    if (!data || !selected) return [];
    const rows = new Map(data.records.filter(r => r.location_id === selected).map(r => [r.date, r]));
    return Array.from({length: count}, (_, i) => {const date = dates[i]; return rows.get(date) || {date, location_id: selected, value: null, hours: 0};});
  }, [data, selected, count, dates]);
  const position = (p: Point): [number, number, number] => [p.longitude, p.latitude, p.elevation_m * exaggeration + 150];
  const layers = [
    terrain && !terrainError ? new WeatherTerrainLayer({id: 'terrain', elevationData: terrainURL,
      weatherMesh: surface ? mesh : null, weatherOpacity: opacity / 100,
      elevationDecoder,
      color: [225, 229, 227], wireframe: false, meshMaxError: 12, maxZoom: 11, minZoom: 0,
      onTileError: () => setTerrainError('Terrain tiles are unavailable. Sampled elevations remain interactive.')}) : null,
    new LineLayer<Point>({id: 'stems', data: points, getSourcePosition: p => [p.longitude, p.latitude, 0], getTargetPosition: position,
      getColor: [99, 116, 124, 110], getWidth: 1, updateTriggers: {getTargetPosition: exaggeration}}),
    new ScatterplotLayer<Point>({id: 'locations', data: points, getPosition: position, billboard: true,
      getFillColor: p => color(p.value, min, max), getRadius: p => p.location_id === selected ? 9 : 6,
      parameters: {depthCompare: 'always', depthWriteEnabled: false},
      radiusUnits: 'pixels', stroked: false, getLineColor: [255, 255, 255, 255], lineWidthUnits: 'pixels', getLineWidth: 1,
      pickable: true, onClick: ({object}: PickingInfo<Point>) => {if (object) setSelected(object.location_id);},
      updateTriggers: {getPosition: exaggeration, getFillColor: [min, max], getRadius: selected}}),
    labels ? new TextLayer<Point>({id: 'labels', data: points.filter(p => p.location_id === selected || view.zoom >= 8.5), getPosition: position, getText: p => p.name,
      parameters: {depthCompare: 'always', depthWriteEnabled: false},
      getSize: 12, getColor: [34, 48, 54], getPixelOffset: [11, 0], getTextAnchor: 'start',
      background: true, getBackgroundColor: [255, 255, 255, 230], backgroundPadding: [4, 3],
      updateTriggers: {getPosition: exaggeration}}) : null,
  ];
  async function load() {
    if (!meta) return;
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    setError(''); setLoading(true); setPlaying(false);
    const ids = requestedLocations.map(l => l.location_id).sort();
    const params = new URLSearchParams({metric, start, end, period, aggregation, fingerprint: meta.fingerprint});
    ids.forEach(id => params.append('locations', id));
    try {
      const current = meta.preview ? await getJson<Metadata>('/api/metadata', controller.signal) : meta;
      if (controller.signal.aborted) return;
      if (current.fingerprint !== meta.fingerprint) {
        cache.current.clear(); setMeta(current);
        params.set('fingerprint', current.fingerprint);
      }
      const requestKey = params.toString();
      const cached = cache.current.get(requestKey);
      const result = cached || await getJson<WindowData>('/api/window?' + requestKey, controller.signal);
      if (controller.signal.aborted) return;
      if (!cached) {if (cache.current.size >= 12) cache.current.delete(cache.current.keys().next().value!); cache.current.set(requestKey, result);}
      setCacheHit(!!cached); setData(result); setLoadedIds(ids); setIndex(periodDates(result.start, result.end, result.period || 'daily').length - 1);
      const first = result.records.find(r => r.value !== null)?.location_id || ids[0];
      setSelected(first || '');
      const focus = meta.locations.find(l => l.location_id === first);
      if (focus) setView({...initialView, longitude: focus.longitude, latitude: focus.latitude});
    } catch (e) {if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Unable to load weather.');}
    finally {if (!controller.signal.aborted) setLoading(false);}
  }
  function preset(p: Period, n: number) {
    if (!meta) return;
    const first = nextPeriod(periodStart(meta.end, p), p, -(n - 1));
    setStart(first < meta.start ? meta.start : first); setEnd(meta.end);
  }
  function dateSelector(label: string, value: string, update: (v: string) => void, last: boolean) {
    const inputValue = !value ? '' : period === 'weekly' ? weekValue(value) : period === 'monthly' ? value.slice(0, 7) : period === 'yearly' ? value.slice(0, 4) : value;
    const change = (v: string) => {
      if (!v) {update(''); return;}
      let date = period === 'weekly' ? fromWeek(v) : period === 'monthly' ? v + '-01' : period === 'yearly' ? v + '-01-01' : v;
      if (last) date = dayAfter(nextPeriod(date, period), -1);
      if (meta) date = date < meta.start ? meta.start : date > meta.end ? meta.end : date;
      update(date);
    };
    return <label>{label}{period === 'yearly' ? <select aria-label={`${label} year`} value={inputValue} onChange={e => change(e.target.value)}>{meta && Array.from({length: +meta.end.slice(0, 4) - +meta.start.slice(0, 4) + 1}, (_, i) => +meta.start.slice(0, 4) + i).map(y => <option key={y}>{y}</option>)}</select> : <input aria-label={`${label} ${period === 'daily' ? 'date' : period === 'weekly' ? 'week' : 'month'}`} type={period === 'daily' ? 'date' : period === 'weekly' ? 'week' : 'month'} value={inputValue} onChange={e => change(e.target.value)}/>}</label>;
  }
  const invalidRange = !start || !end || start > end || (!!meta && (start < meta.start || end > meta.end)) || daysBetween(start, end) >= limits[period];
  const hasData = points.filter(p => p.value !== null).length;
  return <div className="app-shell">
    <header className="topbar">
      <a className="brand" href="/"><span>Big Weather</span></a>
      <a className="streamlit-link" href="?page=ask">Ask weather</a>
      {/*<a className="streamlit-link" href={import.meta.env.VITE_STREAMLIT_URL || 'http://localhost:8501'} target="_blank" rel="noreferrer">Streamlit dashboard <ArrowUpRight size={15}/></a>*/}
    </header>
    <main className="workspace">
      <div className="page-heading"><h1>Elevation explorer</h1>{meta?.preview && <span className="preview-note">Partial download · unpublished</span>}</div>
      <div className="explorer-layout"><aside className="filter-sidebar" aria-label="Weather filters"><form className="data-controls" onSubmit={e => {e.preventDefault(); void load();}}>
        <label>Weather feature<select value={metric} onChange={e => {setMetric(e.target.value); setAggregation('auto');}} disabled={!meta}>{meta?.features.map(f => <option key={f.id} value={f.id}>{f.label} ({f.unit})</option>)}</select></label>
        <label>Country<select value={country} onChange={e => setCountry(e.target.value)}><option>All countries</option>{[...new Set(meta?.locations.map(l => l.country))].sort().map(c => <option key={c}>{c}</option>)}</select></label>
        <label>Aggregation<select value={aggregation} onChange={e => setAggregation(e.target.value)} disabled={!meta}>
          <option value="auto">Default ({meta?.features.find(f => f.id === metric)?.aggregation === 'sum' ? 'total' : 'mean'})</option>
          <option value="mean">Mean</option><option value="min">Minimum</option><option value="max">Maximum</option>
          {meta?.features.find(f => f.id === metric)?.aggregation === 'sum' && <option value="sum">Total</option>}
        </select></label>
        <p className="hint">Aggregates daily {meta?.features.find(f => f.id === metric)?.aggregation === 'sum' ? 'rainfall totals' : 'means'} within each selected period.</p>
        <fieldset className="period-options"><legend>View by</legend>{(['daily', 'weekly', 'monthly', 'yearly'] as Period[]).map(p => <label key={p}><input type="radio" name="period" value={p} checked={period === p} onChange={() => {setPeriod(p); preset(p, p === 'daily' ? 7 : p === 'weekly' ? 4 : p === 'monthly' ? 3 : 2);}}/>{p[0].toUpperCase() + p.slice(1)}</label>)}</fieldset>
        {dateSelector('From', start, setStart, false)}
        {dateSelector('To', end, setEnd, true)}
        <div className="preset-pills" aria-label="Date presets">{(period === 'daily' ? [7, 30, 90] : period === 'weekly' ? [4, 12, 52] : period === 'monthly' ? [3, 6, 12] : [2, 5, 10]).map(n => <button type="button" key={n} disabled={!meta} onClick={() => preset(period, n)}>Last {n} {period === 'daily' ? 'days' : period === 'weekly' ? 'weeks' : period === 'monthly' ? 'months' : 'years'}</button>)}</div>
        <p className="hint">Presets end at the latest available date. Periods at the coverage boundary include only the selected dates.</p>
        <button className="primary-button" disabled={!meta || loading || invalidRange || !requestedLocations.length}>{loading && <LoaderCircle className="spin" size={17}/>} {loading ? 'Loading…' : 'Load weather'}</button>
      </form>
      {invalidRange && meta && <p className="validation">Choose a date range of 1–{limits[period].toLocaleString()} days within the available data.</p>}
      {error && <div role="alert" className="error">{error} {!meta && <button onClick={() => window.location.reload()}>Retry connection</button>}</div>}
      </aside><div className="map-workspace"><section className="scene" aria-label="Interactive 3D elevation map">
        {!rendererError && <DeckGL views={mapView} viewState={view} onViewStateChange={e => setView(e.viewState as typeof initialView)} controller layers={layers}
          onError={e => setRendererError(e.message)}
          getTooltip={({object}: PickingInfo<Point>) => object ? {text: `${object.name}\nElevation: ${object.elevation_m.toFixed(0)} m\n${object.value === null ? 'No complete period value' : `${object.value.toFixed(2)} ${unit}`}`} : null}/>}
        <div className="scene-top">
          <div className="scene-summary"><h2>{data ? `${feature?.label} · ${aggregationLabel}` : 'Sampled elevations'}</h2><p>{data ? `${periodLabel(day, loadedPeriod)} · ${hasData} of ${points.length} locations with data` : `${points.length} locations. Load weather to see colours.`}</p></div>
          <button type="button" className="settings-button" aria-haspopup="dialog" onClick={() => setSettingsOpen(true)}><SlidersHorizontal size={17}/> Map settings</button>
        </div>
        {(terrainError || rendererError) && <div className="scene-warning" role="status">{rendererError ? `3D rendering unavailable: ${rendererError}. Use the location list and history below.` : terrainError}</div>}
        <div className="scene-bottom"><span className="gesture">Drag to pan<br/>Shift + drag to rotate<br/>Scroll to zoom</span></div>
        <div className="legend"><span>{unit || 'Weather value'}</span><div className="gradient"/><div className="range-labels"><span>{values.length ? min.toFixed(1) : '—'}</span><span>{values.length ? max.toFixed(1) : '—'}</span></div><div className="missing"><i/> Missing period value</div>
          {data && surface && terrain && <p className="interpolation-note">{mesh ? 'Terrain colour is interpolated between samples.' : 'Gradient needs three nearby samples with data.'}</p>}
        </div>
      </section>
      <div className="timeline"><button className="play-button" aria-label={playing ? 'Pause playback' : 'Play playback'} disabled={count < 2} onClick={() => setPlaying(!playing)}>{playing ? <Pause size={18}/> : <Play size={18}/>}</button><div className="timeline-track"><div className="timeline-heading"><strong>{periodLabel(day, loadedPeriod) || 'Choose a weather window'}</strong><span>{data ? `${cacheHit ? 'Cached' : `${data.query_ms.toFixed(0)} ms query`} · ${data.input_rows.toLocaleString()} hourly rows` : 'Choose a period and load weather'}</span></div><TimelineSlider dates={dates} index={index} period={loadedPeriod} onDrag={() => setPlaying(false)} onCommit={setIndex}/></div></div>
      <div className="detail-grid">
        <section className="location-panel"><label htmlFor="location">Location</label><select id="location" value={selected} onChange={e => setSelected(e.target.value)}><option value="">Select a point on the map</option>{points.map(p => <option key={p.location_id} value={p.location_id}>{p.name}</option>)}</select>
          <div className="readings"><div><strong>{chosen ? Math.round(chosen.elevation_m).toLocaleString() : '—'}<small> m</small></strong><span>Elevation</span></div><div><strong>{chosen?.value != null ? chosen.value.toFixed(1) : '—'}<small> {unit}</small></strong><span>{`${loadedPeriod[0].toUpperCase() + loadedPeriod.slice(1)} ${aggregationLabel}`}</span></div></div>
          <p className="hint">{chosen ? `${chosen.latitude.toFixed(3)}° N · ${chosen.longitude.toFixed(3)}° E · ${chosen.country}` : 'Click a location to inspect its weather.'}</p>
        </section>
        <section className="history-panel"><h2>{chosen ? `${chosen.name} history` : 'Location history'}</h2><History key={`${selected}-${data?.metric}-${data?.start}-${data?.end}`} records={history} unit={unit} date={day}/></section>
      </div>
      {meta && data && <Analytics meta={meta} data={data} locations={loadedLocations}/>}
      <div className="attribution">{meta?.attribution} {terrain && <>Terrain: Mapzen / AWS Open Data, USGS & NOAA. <a href="https://github.com/tilezen/joerd/blob/master/docs/attribution.md" target="_blank" rel="noreferrer">Source credits</a>. </>}</div>
      </div></div>
    </main>
    <MapSettings open={settingsOpen} onClose={() => setSettingsOpen(false)}>
      <label className="slider-label">Elevation exaggeration <strong>{exaggeration}×</strong><input aria-label="Elevation exaggeration" type="range" min="1" max="12" value={exaggeration} onChange={e => setExaggeration(+e.target.value)}/></label>
      <label className="toggle"><span>Weather colours on terrain</span><input type="checkbox" checked={surface} onChange={e => setSurface(e.target.checked)}/></label>
      <label className="slider-label">Colour opacity <strong>{opacity}%</strong><input aria-label="Colour opacity" type="range" min="10" max="100" disabled={!surface} value={opacity} onChange={e => setOpacity(+e.target.value)}/></label>
      <label className="toggle"><span>Terrain surface</span><input type="checkbox" checked={terrain} onChange={e => {setTerrain(e.target.checked); setTerrainError('');}}/></label>
      <label className="toggle"><span>Location labels</span><input type="checkbox" checked={labels} onChange={e => setLabels(e.target.checked)}/></label>
      <p className="hint">Colours blend between nearby samples with data. Gaps stay unfilled. Colours follow the terrain elevation. Values between samples are visual estimates.</p>
      <button type="button" className="reset-button" onClick={() => setView(initialView)}><RotateCcw size={16}/> Reset camera</button>
    </MapSettings>
  </div>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode>{new URLSearchParams(window.location.search).get('page') === 'ask' ? <AskPage/> : <App/>}</React.StrictMode>);
