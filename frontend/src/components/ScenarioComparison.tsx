import type { SimulationResult } from '../types/api';
import { compatibleResults, compareResults } from '../utils/simulationAnalysis';
import { label, number } from '../utils/format';
import { isSimulation } from '../api/guards';
export function scenarioLabel(result: SimulationResult): string {
  const input = result.meta.inputs;
  return `${input.ev_kw} kW EV / ${input.pv_kwp} kWp solar · ${label(input.day_type)} · ${label(input.load_level)} · ${result.bess ? `BESS ${result.bess.power_kw} kW / ${result.bess.energy_kwh} kWh, initial SOC ${result.bess.initial_soc_pct}%` : 'No battery'}`;
}
export function ScenarioComparison({ a, b }: { a: SimulationResult; b: SimulationResult }) {
  if (!isSimulation(a) || !isSimulation(b)) return <p role="alert">Comparison unavailable: invalid simulation data.</p>;
  if (!compatibleResults(a, b)) return <p role="alert">Comparison unavailable: engine versions or time labels differ. Current results remain available.</p>;
  return <section className="scenario-comparison" aria-label="Scenario comparison">
    <h2>Scenario comparison · B minus A</h2>
    <p>A · pinned: {scenarioLabel(a)}</p><p>B · current: {scenarioLabel(b)}</p>
    <div className="table-scroll"><table><caption>Returned engineering metrics · signed differences, not percentage changes</caption><thead><tr><th>Metric</th><th>A · pinned</th><th>B · current</th><th>B − A</th></tr></thead><tbody>{compareResults(a, b).map(row => <tr key={row.key}><th scope="row">{row.label}</th><td>{number(row.before, 4)} {row.unit}</td><td>{number(row.after, 4)} {row.unit}</td><td className={row.difference === 0 ? 'delta-neutral' : row.key === 'min_voltage_pu' || row.key === 'peak_hotspot_c' ? 'delta-context' : row.difference < 0 ? 'delta-better' : 'delta-worse'}>{row.difference > 0 ? '+' : ''}{number(row.difference, 4)} {row.key === 'peak_loading_pct' ? 'percentage points' : row.unit}<span className="delta-label">{row.difference === 0 ? 'No change' : row.key === 'min_voltage_pu' ? 'Voltage shift · check limits' : row.key === 'peak_hotspot_c' ? (row.difference < 0 ? 'Cooler' : 'Hotter') : row.difference < 0 ? 'Lower modeled stress' : 'Higher modeled stress'}</span></td></tr>)}<tr><th scope="row">Alert events</th><td>{a.alerts.length}</td><td>{b.alerts.length}</td><td>{b.alerts.length - a.alerts.length}</td></tr><tr><th scope="row">Constraint verdict</th><td>{label(a.verdict.status)}</td><td>{label(b.verdict.status)}</td><td>{a.verdict.status === b.verdict.status ? 'Unchanged' : 'Changed'}</td></tr></tbody></table></div>
    <p className="inline-note">Both are independently executed scenarios, not a causal estimate or neighbourhood before/after plan. Negative differences are preserved; lower voltage is not an improvement.</p>
  </section>;
}
