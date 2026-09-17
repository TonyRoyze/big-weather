import {useEffect, useRef, useState} from 'react';
import {periodLabel, type Period} from './periods';
export function TimelineSlider({dates, index, period, onCommit, onDrag}: {dates: string[]; index: number; period: Period; onCommit: (i: number) => void; onDrag: () => void}) {
  const [draft, setDraft] = useState(index);
  const dragging = useRef(false);
  useEffect(() => {if (!dragging.current) setDraft(index);}, [index, dates]);
  const commit = (value: number) => {dragging.current = false; const tick = Math.round(value); setDraft(tick); onCommit(tick);};
  const last = Math.max(0, dates.length - 1);
  const ticks = Array.from({length: Math.min(5, dates.length)}, (_, i) => i);
  const positions = ticks.map((_, i) => ticks.length === 1 ? 0 : Math.round(i * last / (ticks.length - 1)));
  return <div className="scrubber">
    <output className="scrubber-preview">{periodLabel(dates[Math.round(draft)] || '', period)}</output>
    <div className="slider-rail"><div className="slider-position-ticks" aria-hidden="true">{dates.map((date, i) => <i key={date} data-date={date} className={i === Math.round(draft) ? 'active' : ''} style={{left: `${last ? i / last * 100 : 0}%`}}/>)}</div>
    <input aria-label="Weather date" aria-valuetext={periodLabel(dates[Math.round(draft)] || '', period)} type="range" min={0} max={last} step="any" value={draft} disabled={dates.length < 2}
      onPointerDown={e => {dragging.current = true; e.currentTarget.setPointerCapture(e.pointerId); onDrag();}}
      onChange={e => {setDraft(+e.target.value); if (!dragging.current) commit(+e.target.value);}}
      onPointerUp={e => commit(+e.currentTarget.value)} onPointerCancel={e => commit(+e.currentTarget.value)}
      onKeyDown={e => {const delta = e.key === 'ArrowRight' || e.key === 'ArrowUp' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowDown' ? -1 : 0; if (delta || e.key === 'Home' || e.key === 'End') {e.preventDefault(); onDrag(); commit(e.key === 'Home' ? 0 : e.key === 'End' ? last : Math.max(0, Math.min(last, Math.round(draft) + delta)));}}}/></div>
    <div className="timeline-ticks" aria-hidden="true">{positions.map((p, i) => <span key={p} style={{left: `${last ? p / last * 100 : 0}%`}} className={i === 0 ? 'first' : i === positions.length - 1 ? 'last' : ''}>{periodLabel(dates[p], period)}</span>)}</div>
  </div>;
}
