import {useEffect, useState} from 'react';
import {ArrowUpRight, LoaderCircle} from 'lucide-react';
import './ask.css';

type Row = {day?: string; name?: string; country?: string; elevation_m?: number; value?: number; complete_days: number};
type Result = {clarification?: string; summary?: string; sql?: string; unit?: string; records?: Row[];
  complete_days?: number; expected_days?: number; preview?: boolean; fingerprint?: string;
  plan?: {explanation: string; start: string; end: string; chart: string; group_by: string; metric: string}};
const examples = ['Compare average temperature in Colombo and Kandy over the latest week.',
  'Show daily rainfall in Sri Lanka for the latest available month.',
  'How does temperature vary with elevation across Sri Lanka in the latest week?'];

function ResultChart({result}: {result: Result}) {
  const rows = result.records || [];
  const valid = rows.filter(r => r.value != null);
  if (!valid.length) return null;
  const scatter = result.plan?.chart === 'scatter', line = result.plan?.chart === 'line';
  const lower = Math.min(0, ...valid.map(r => r.value!)), upper = Math.max(0, ...valid.map(r => r.value!));
  const y = (v: number) => 255 - (v-lower)/(upper-lower || 1)*215;
  const xs = rows.map((r,i) => scatter ? r.elevation_m ?? 0 : line ? Date.parse(r.day!) : i);
  const xmin = Math.min(...xs), xmax = Math.max(...xs);
  const x = (i: number) => 65 + (xs[i]-xmin)/(xmax-xmin || 1)*635;
  const label = (r: Row) => r.day || r.name || r.country || '';
  let path = '', previous = -1;
  rows.forEach((r,i) => {if(r.value == null) {previous=-1; return;}
    const contiguous = previous >= 0 && (!line || xs[i]-xs[previous] <= 86400000);
    path += `${contiguous ? 'L' : 'M'}${x(i)},${y(r.value)} `; previous=i;});
  return <figure className="ask-chart"><figcaption>{result.plan?.metric.replaceAll('_',' ')} ({result.unit})</figcaption>
    {line || scatter ? <svg viewBox="0 0 760 310" role="img" aria-label={`${scatter ? 'Elevation comparison' : 'Daily trend'} in ${result.unit}`}>
      {[lower,(lower+upper)/2,upper].map((v,i)=><g key={i}><line x1="65" x2="710" y1={y(v)} y2={y(v)} stroke="#e2e8eb"/><text x="53" y={y(v)+4} textAnchor="end">{v.toFixed(1)}</text></g>)}
      {line && <path d={path} fill="none" stroke="#28747a" strokeWidth="2.5"/>}
      {rows.map((r,i)=>r.value == null ? null : <circle key={i} cx={x(i)} cy={y(r.value)} r={scatter ? 5 : 3} fill="#28747a"><title>{label(r)}: {r.value.toFixed(2)} {result.unit}{scatter ? ` at ${r.elevation_m} m` : ''}</title></circle>)}
      <text x="65" y="282">{scatter ? `${xmin} m` : rows[0]?.day}</text><text x="710" y="282" textAnchor="end">{scatter ? `${xmax} m` : rows.at(-1)?.day}</text>
      {scatter && <text x="385" y="304" textAnchor="middle">Elevation (m)</text>}
    </svg> : <div className="ask-bars">{valid.map((r,i)=><div className="ask-bar" key={i}><span>{label(r)}</span><div className="ask-bar-track"><b style={{left:`${-lower/(upper-lower || 1)*100}%`}}/><i style={{marginLeft:`${(Math.min(0,r.value!)-lower)/(upper-lower || 1)*100}%`,width:`${Math.abs(r.value!)/(upper-lower || 1)*100}%`}}/></div><strong>{r.value!.toFixed(2)} {result.unit}</strong></div>)}</div>}
  </figure>;
}

export function AskPage() {
  const [question,setQuestion] = useState('');
  const [submitted,setSubmitted] = useState('');
  const [result,setResult] = useState<Result>();
  const [error,setError] = useState('');
  const [busy,setBusy] = useState(false);
  const [configured,setConfigured] = useState<boolean>();
  const [connection,setConnection] = useState('');
  useEffect(()=>{fetch('/api/ask/status').then(r=>{if(!r.ok) throw Error(); return r.json();}).then(r=>{setConfigured(r.configured);setConnection(r.message || '');}).catch(()=>setError('Unable to connect to the analysis service.'));},[]);
  async function ask() {
    if(busy || !question.trim()) return;
    setBusy(true); setError(''); setResult(undefined); setSubmitted(question.trim());
    try {
      const response = await fetch('/api/ask', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:question.trim()})});
      const payload = await response.json();
      if(!response.ok) throw Error(typeof payload.detail === 'string' ? payload.detail : 'Check your question and try again.');
      setResult(payload);
    } catch(e) {setError(e instanceof Error ? e.message : 'The analysis failed. Try again.');}
    finally {setBusy(false);}
  }
  return <div className="app-shell"><header className="topbar"><a className="brand" href="/"><span>Big Weather</span></a><nav className="ask-nav"><a href="/">Elevation explorer</a>
    {/*<a href={import.meta.env.VITE_STREAMLIT_URL || 'http://localhost:8501'} target="_blank" rel="noreferrer">Streamlit <ArrowUpRight size={14} /></a>*/}
  </nav></header>
    <main className="ask-page"><h1>Ask your weather data</h1><p className="ask-intro">Explore a place, compare elevations, or follow a change over time.</p>
      <form onSubmit={e=>{e.preventDefault(); void ask();}} className="ask-composer"><label htmlFor="weather-question">What would you like to see?</label><textarea id="weather-question" value={question} onChange={e=>setQuestion(e.target.value)} maxLength={3000} rows={3} placeholder="Compare rainfall in Colombo and Kandy during August 2026…" required disabled={busy}/><div><span>Answers use the data downloaded so far.</span><button disabled={busy || configured !== true || question.trim().length<3} type="submit">{busy ? <><LoaderCircle size={17} className="spin"/> Analysing…</> : 'Explore data'}</button></div></form>
      {configured === false && <p className="ask-notice" role="status">{connection}</p>}
      {/*{configured && <p className="ask-context">{connection}</p>}*/}
      {!result && !busy && <div className="ask-examples">{examples.map(example=><button key={example} onClick={()=>setQuestion(example)}>{example}</button>)}</div>}
      {busy && <p role="status" className="ask-progress">Interpreting your question, querying Spark, and preparing your chart and summary. This may take a few minutes.</p>}
      {error && <p role="alert" className="ask-notice">{error}</p>}
      {result && <article className="ask-answer" aria-live="polite"><h2>{submitted}</h2>{result.clarification ? <p>{result.clarification}</p> : <>
        <p className="ask-summary">{result.summary}</p><p className="ask-context">{result.plan?.start} to {result.plan?.end} · {result.complete_days?.toLocaleString()} / {result.expected_days?.toLocaleString()} complete location-days{result.preview ? ' · Unpublished preview' : ''}</p>
        <ResultChart result={result}/><details><summary>How this was calculated</summary><p>{result.plan?.explanation}</p><p>Only days with 24 non-null hours contribute. Missing observations are excluded; groups can have different coverage.</p><p className="ask-fingerprint">Dataset: {result.fingerprint}</p></details>
        <details><summary>Generated Spark SQL</summary><pre><code>{result.sql}</code></pre></details>
        <details><summary>Result data ({result.records?.length || 0} rows)</summary><div className="ask-table"><table><thead><tr><th>Location / date</th><th>Elevation (m)</th><th>Value ({result.unit})</th><th>Complete days</th></tr></thead><tbody>{result.records?.map((r,i)=><tr key={i}><td>{r.day || r.name || r.country}</td><td>{r.elevation_m ?? '—'}</td><td>{r.value?.toFixed(3) ?? 'Missing'}</td><td>{r.complete_days}</td></tr>)}</tbody></table></div></details>
      </>}</article>}
    </main></div>;
}
