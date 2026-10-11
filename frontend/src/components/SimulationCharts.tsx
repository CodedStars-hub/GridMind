import { useId, useState } from 'react';
import type { Assumption, SimulationResult } from '../types/api';
import { isSimulation } from '../api/guards';
import { chartGeometry, compatibleResults, thresholdsFor, violates, type ChartKey } from '../utils/simulationAnalysis';
import { number } from '../utils/format';
import { Empty } from './ui';

const charts: { key: ChartKey; title: string; unit: string }[] = [
  { key: 'voltage_pu', title: 'Connection-point voltage', unit: 'p.u.' },
  { key: 'loading_pct', title: 'Transformer loading', unit: '% rated current' },
  { key: 'hotspot_c', title: 'Hot-spot temperature', unit: '°C' },
];
export function SimulationCharts({ result, assumptions, reference = null }: { result: SimulationResult | null; assumptions: Assumption[]; reference?: SimulationResult | null }) {
  const [index, setIndex] = useState(0);
  const [tableOpen, setTableOpen] = useState(false);
  const id = useId();
  if (!result) return <Empty title="No chart data">Run a simulation to inspect actual returned samples.</Empty>;
  if (!isSimulation(result)) return <p role="alert">Simulation chart data is invalid. No values were assumed.</p>;
  const overlay = reference && isSimulation(reference) && compatibleResults(reference, result) ? reference : null;
  const active = Math.min(index, result.series.time.length - 1);
  return <section className="simulation-charts" aria-label="Interactive simulation charts">
    <div className="chart-controls"><label htmlFor={id}>Inspect time: {result.series.time[active]}<input id={id} type="range" min={0} max={result.series.time.length - 1} value={active} onChange={e => setIndex(Number(e.target.value))} aria-valuetext={result.series.time[active]} /></label><p>Arrow keys select actual 15-minute samples. Hover a chart to inspect the same time across all charts.</p></div>
    <p className="inline-note">Voltage shows supply quality; loading shows demand on rated current; hot-spot temperature shows modeled winding stress. A limit event is not evidence of equipment or appliance damage.</p>
    <p className="chart-legend">Solid line: {overlay ? 'B · current scenario' : 'current scenario'}{overlay && ' · Dashed line: A · pinned scenario'} · Filled circles: current samples strictly outside available limits; outlined circles: pinned violations.</p>
    {[...charts, ...(result.bess ? [{ key: 'bess_kw' as const, title: 'Battery dispatch (+ discharge / − charge)', unit: 'kW' }, { key: 'bess_soc_pct' as const, title: 'Battery state of charge', unit: '%' }] : [])].map(chart => {
      const values = result.series[chart.key]!;
      const resolved = chart.key === 'bess_soc_pct' && result.bess ? ['soc_min_pct', 'soc_max_pct'].map(name => ({ name, value: result.bess![name as 'soc_min_pct' | 'soc_max_pct'], unit: '%', note: 'Resolved battery limit from response' })) : assumptions;
      const limits = thresholdsFor(chart.key, resolved);
      const referenceValues = overlay?.series[chart.key];
      const other = referenceValues ?? [];
      const chartOverlay = overlay && referenceValues ? overlay : null;
      const plot = chartGeometry(values, limits, other);
      return <figure key={chart.key} className="simulation-chart" data-metric={chart.key}>
        <figcaption>{chart.title} ({chart.unit})</figcaption>
        <div className="chart-plot"><svg viewBox="0 0 740 255" role="img" aria-label={`${chart.title}: ${result.series.time[0]} to ${result.series.time.at(-1)}. Exact values available below and in the sample table.`} onPointerMove={event => {
          const rect = event.currentTarget.getBoundingClientRect();
          if (rect.width && Number.isFinite(event.clientX)) setIndex(Math.max(0, Math.min(values.length - 1, Math.round(((event.clientX - rect.left) / rect.width * 740 - 60) / 640 * (values.length - 1)))));
        }}>
          <line x1="60" x2="60" y1="30" y2="210" className="chart-axis" /><line x1="60" x2="700" y1="210" y2="210" className="chart-axis" />
          {[plot.low, (plot.low + plot.high) / 2, plot.high].map(value => <g key={value}><line x1="60" x2="700" y1={plot.y(value)} y2={plot.y(value)} className="chart-grid" /><text x="54" y={plot.y(value) + 4} textAnchor="end">{number(value, 2)}</text></g>)}
          {[0, 24, 48, 72, 95].map(i => <text key={i} x={plot.x(i)} y="235" textAnchor="middle">{result.series.time[i]}</text>)}
          {limits.map(limit => <g key={limit.label}><line x1="60" x2="700" y1={plot.y(limit.value)} y2={plot.y(limit.value)} className="chart-limit" /><text x="65" y={plot.y(limit.value) - 4}>{limit.label}: {number(limit.value, 4)} {chart.unit}</text></g>)}
          {chartOverlay && <polyline points={plot.points(other)} className="chart-reference" />}
          {chartOverlay && other.map((value, i) => violates(value, limits) ? <circle key={i} cx={plot.x(i)} cy={plot.y(value)} r="3" className="chart-reference-violation"><title>A · {result.series.time[i]} · {number(value, 4)} {chart.unit} · outside configured limit</title></circle> : null)}
          <polygon points={`60,210 ${plot.points(values)} 700,210`} className="chart-area" />
          <polyline points={plot.points(values)} className="chart-series" />
          {values.map((value, i) => violates(value, limits) ? <circle key={i} cx={plot.x(i)} cy={plot.y(value)} r="3" className="chart-violation"><title>{result.series.time[i]} · {number(value, 4)} {chart.unit} · outside configured limit</title></circle> : null)}
          <line x1={plot.x(active)} x2={plot.x(active)} y1="30" y2="210" className="chart-cursor" /><circle cx={plot.x(active)} cy={plot.y(values[active]!)} r="4" className="chart-selected" />
        </svg></div>
        <p className="chart-readout">{result.series.time[active]} · {chartOverlay ? 'B' : 'Current'}: {number(values[active]!, 4)} {chart.unit}{chartOverlay && ` · A: ${number(other[active]!, 4)} ${chart.unit}`}{violates(values[active]!, limits) && ' · Outside configured limit'}</p>
        {!limits.length && chart.key !== 'bess_kw' && <p className="inline-note">Thresholds unavailable from the API; no limit values assumed.</p>}
      </figure>;
    })}
    <details onToggle={event => setTableOpen(event.currentTarget.open)}><summary>All returned samples (accessible data table)</summary>{tableOpen && <div className="table-scroll"><table><caption>Current simulation · 96 samples, end-of-step temperatures</caption><thead><tr><th>Time</th><th>Voltage (p.u.)</th><th>Loading (%)</th><th>Hot-spot (°C)</th><th>Aging (× reference)</th></tr></thead><tbody>{result.series.time.map((time, i) => <tr key={time}><th scope="row">{time}</th><td>{number(result.series.voltage_pu[i]!, 4)}</td><td>{number(result.series.loading_pct[i]!, 4)}</td><td>{number(result.series.hotspot_c[i]!, 4)}</td><td>{number(result.series.aging_factor[i]!, 4)}</td></tr>)}</tbody></table></div>}</details>
  </section>;
}
