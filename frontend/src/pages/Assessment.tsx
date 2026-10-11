import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useData, type Resource } from '../app/DataProvider';
import { Empty, ErrorState, Loading, Metric, ModelNote, PageHeading, Panel } from '../components/ui';
import type { DayType, EvKw, LoadLevel, PvKwp, ScenariosResponse, ScenarioRequest, SimulationResult } from '../types/api';
import { label, number } from '../utils/format';

export function Assessment() {
  const { client } = useData();
  const [scenarios, setScenarios] = useState<Resource<ScenariosResponse>>({ status: 'loading' });
  const [inputs, setInputs] = useState<ScenarioRequest | null>(null);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [submitted, setSubmitted] = useState<ScenarioRequest | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);
  const [revision, setRevision] = useState(0);
  const simulation = useRef<AbortController | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    setScenarios({ status: 'loading' });
    void client.scenarios(controller.signal).then(data => {
      if (controller.signal.aborted) return;
      setScenarios({ status: 'success', data });
      const { ev_kw, pv_kwp, day_type, load_level } = data.defaults;
      setInputs({ ev_kw, pv_kwp, day_type, load_level });
    }).catch(cause => { if (!controller.signal.aborted) setScenarios({ status: 'error', error: cause }); });
    return () => { controller.abort(); simulation.current?.abort(); };
  }, [client, revision]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!inputs || pending) return;
    const controller = new AbortController(); simulation.current = controller;
    const request = { ...inputs };
    setPending(true); setError(null); setResult(null); setSubmitted(null);
    try {
      const data = await client.simulate(request, controller.signal);
      if (!controller.signal.aborted) { setResult(data); setSubmitted(request); }
    } catch (cause) { if (!controller.signal.aborted) setError(cause); }
    finally { if (!controller.signal.aborted) setPending(false); }
  }
  return <><PageHeading eyebrow="SINGLE-TRANSFORMER MODEL" title="Test a charging scenario.">Run a supported 24-hour transformer simulation. This assessment is separate from the neighbourhood’s site allocations.</PageHeading>
    <Panel title="Scenario inputs" subtitle="Choices and defaults are loaded from the backend configuration.">
      {scenarios.status === 'loading' ? <Loading message="Loading supported scenarios…" /> : scenarios.status === 'error' ? <ErrorState error={scenarios.error} retry={() => setRevision(n => n + 1)} /> : inputs && <form onSubmit={event => { void submit(event); }}>
        <fieldset disabled={pending} className="scenario-grid"><legend className="sr-only">Simulation scenario</legend>
          <label>EV hub rating <select value={inputs.ev_kw} onChange={e => setInputs({ ...inputs, ev_kw: Number(e.target.value) as EvKw })}>{scenarios.data.enums.ev_kw.map(value => <option key={value} value={value}>{value} kW</option>)}</select></label>
          <label>Installed solar <select value={inputs.pv_kwp} onChange={e => setInputs({ ...inputs, pv_kwp: Number(e.target.value) as PvKwp })}>{scenarios.data.enums.pv_kwp.map(value => <option key={value} value={value}>{value} kWp</option>)}</select></label>
          <label>Representative day <select value={inputs.day_type} onChange={e => setInputs({ ...inputs, day_type: e.target.value as DayType })}>{scenarios.data.enums.day_type.map(value => <option key={value} value={value}>{label(value)}</option>)}</select></label>
          <label>Existing load <select value={inputs.load_level} onChange={e => setInputs({ ...inputs, load_level: e.target.value as LoadLevel })}>{scenarios.data.enums.load_level.map(value => <option key={value} value={value}>{label(value)}</option>)}</select></label>
        </fieldset><div className="form-footer"><p>Calculated by the Python engine. Battery options are not available here.</p><button className="button" type="submit" disabled={pending}>{pending ? 'Running simulation…' : 'Run simulation'} <span aria-hidden="true">→</span></button></div>
      </form>}
    </Panel>
    {pending && <Loading message="Running the transformer model…" />}
    {error !== null && <ErrorState error={error} />}
    {!pending && !result && error === null && <Panel title="Assessment results"><Empty title="Ready when you are">Choose a supported scenario and run the model. No estimated metrics are shown before a successful response.</Empty></Panel>}
    {result && submitted && <div aria-live="polite">
      <div className="result-heading"><div><span className="small-label">LAST COMPLETED SCENARIO</span><h2>{label(submitted.day_type)} · {label(submitted.load_level)}</h2><p>{submitted.ev_kw} kW EV hub / {submitted.pv_kwp} kWp solar · Engine {result.meta.engine_version} · {result.meta.source}</p></div><span className="tag">{label(result.verdict.status)}</span></div>
      <div className={`verdict ${result.verdict.status === 'safe' ? 'safe' : 'warning'}`}><strong>Model verdict</strong><p>{result.verdict.message}</p></div>
      <div className="metric-grid"><Metric label="Minimum voltage" value={number(result.summary.min_voltage_pu, 4)} unit="p.u." description={`At ${result.summary.min_voltage_time}`} /><Metric label="Peak hot-spot" value={number(result.summary.peak_hotspot_c, 4)} unit="°C" description={`At ${result.summary.peak_hotspot_time}`} /><Metric label="Peak loading" value={number(result.summary.peak_loading_pct, 4)} unit="%" description={`Rated current · at ${result.summary.peak_loading_time}`} /><Metric label="Alert events" value={number(result.alerts.length)} description="Threshold events returned by the engine" /></div>
      <div className="two-column"><Panel title="Aging and voltage summary"><dl className="summary-list"><div><dt>Peak voltage deviation</dt><dd>{number(result.summary.peak_voltage_deviation_pu, 4)} p.u.</dd></div><div><dt>Peak aging acceleration</dt><dd>{number(result.summary.peak_aging_factor, 4)} × reference</dd></div><div><dt>Equivalent reference aging</dt><dd>{number(result.summary.daily_equivalent_aging_hours, 4)} h/day</dd></div><div><dt>Reference-model life estimate</dt><dd>{number(result.summary.insulation_life_years, 4)} years</dd></div></dl><p className="inline-note">The capped model life estimate is not measured remaining service life or a failure-date prediction.</p></Panel><Panel title="Alert events" subtitle="Severity and inclusive first/last affected step labels from the engine.">{result.alerts.length ? <ul className="alert-list">{result.alerts.map((alert, index) => <li key={`${alert.type}-${alert.start}-${index}`}><span className={`tag ${alert.severity}`}>{label(alert.severity)}</span><div><strong>{label(alert.type)}</strong><p>{alert.start}–{alert.end} · {number(alert.peak_value, 4)} {alert.unit}</p></div></li>)}</ul> : <Empty title="No threshold events">The engine returned no alerts for this scenario.</Empty>}</Panel></div>
    </div>}
    <ModelNote />
  </>;
}
