import { PrecomputedFallback } from '../components/PrecomputedFallback';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useData, type Resource } from '../app/DataProvider';
import { Empty, ErrorState, Loading, Metric, ModelNote, PageHeading, Panel } from '../components/ui';
import type { DayType, EvKw, LoadLevel, PvKwp, ScenariosResponse, ScenarioRequest, SimulationResult, BatteryConfig } from '../types/api';
import { label, number } from '../utils/format';
import { DispatchMonitor } from '../components/DispatchMonitor';
import { BatteryControls, type BatteryFields } from '../components/BatteryControls';
import { SimulationCharts } from '../components/SimulationCharts';
import { ScenarioComparison, scenarioLabel } from '../components/ScenarioComparison';

export function Assessment() {
  const { client } = useData();
  const [scenarios, setScenarios] = useState<Resource<ScenariosResponse>>({ status: 'loading' });
  const [inputs, setInputs] = useState<ScenarioRequest | null>(null);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [batteryEnabled, setBatteryEnabled] = useState(false);
  const [batteryFields, setBatteryFields] = useState<BatteryFields>({});
  const [reference, setReference] = useState<SimulationResult | null>(null);
  const [submitted, setSubmitted] = useState<ScenarioRequest | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);
  const [revision, setRevision] = useState(0);
  const [provenance, setProvenance] = useState<string | null>(null);
  const submitting = useRef(false);
  const simulation = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setScenarios({ status: 'loading' });
    void client.scenarios(controller.signal).then(data => {
      if (controller.signal.aborted) return;
      setScenarios({ status: 'success', data });
      const { ev_kw, pv_kwp, day_type, load_level } = data.defaults;
      setInputs({ ev_kw, pv_kwp, day_type, load_level });
      const initial = data.assumptions.find(a => a.name === 'initial_soc_pct')?.value;
      if (typeof initial === 'number') setBatteryFields(fields => ({ ...fields, initial_soc_pct: String(initial) }));
    }).catch(cause => { if (!controller.signal.aborted) setScenarios({ status: 'error', error: cause }); });
    return () => { controller.abort(); simulation.current?.abort(); };
  }, [client, revision]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!inputs || submitting.current) return;
    submitting.current = true; setProvenance(null);
    const controller = new AbortController(); simulation.current = controller;
    const request = { ...inputs };
    if (batteryEnabled) {
      request.bess_override = Object.fromEntries(
        Object.entries(batteryFields).filter(([, value]) => value !== '').map(([key, value]) => [key, Number(value)])
      ) as unknown as BatteryConfig;
    }
    setPending(true); setError(null); setResult(null); setSubmitted(null);
    try {
      const data = await client.simulate(request, controller.signal);
      if (!controller.signal.aborted) { setResult(data); setSubmitted(request); }
    } catch (cause) { if (!controller.signal.aborted) setError(cause); }
    finally { submitting.current = false; if (!controller.signal.aborted) setPending(false); }
  }

  // Derive prominent verdict text based on real simulation results
  const verdictInfo = result ? (() => {
    const isSafe = result.verdict.status === 'safe' || result.verdict.status === 'safe_with_bess';
    if (isSafe) {
      return {
        title: 'No modeled limit violations',
        summary: 'All evaluated constraints remained within their configured limits.',
        className: 'safe',
      };
    }
    const hasVoltageAlert = result.summary.min_voltage_pu < 0.95;
    const hasThermalAlert = result.summary.peak_loading_pct > 100 || result.summary.peak_hotspot_c > 120;
    if (hasVoltageAlert && hasThermalAlert) {
      return {
        title: 'Voltage & thermal limits exceeded',
        summary: 'Voltage dropped below minimum and transformer loading exceeded rated capacity during peak hours.',
        className: 'warning',
      };
    }
    if (hasVoltageAlert) {
      return {
        title: 'Voltage limit exceeded',
        summary: 'Minimum voltage fell below the configured limit during the evening peak.',
        className: 'warning',
      };
    }
    return {
      title: 'Thermal loading limit exceeded',
      summary: 'Transformer winding temperature or current exceeded configured operational bounds.',
      className: 'warning',
    };
  })() : null;

  return (
    <>
      <PageHeading
        eyebrow="SINGLE-TRANSFORMER MODEL"
        title="Your simulation studio."
      >
        Simulate a full day of charging demand and evaluate voltage, loading, and thermal stress. Test charging demand. See the grid response. Compare an alternative. This is a single-transformer model, separate from neighbourhood allocations.
      </PageHeading>

      {/* 5-step simulation workflow strip */}
      <ol className="studio-steps" aria-label="Simulation workflow">
        <li><span>1</span>Configure</li>
        <li><span>2</span>Simulate</li>
        <li><span>3</span>Understand</li>
        <li><span>4</span>Compare</li>
        <li><span>5</span>Decide</li>
      </ol>

      <Panel
        title="Scenario inputs"
        subtitle="Configure a representative day. Choices, defaults and limits come from the backend."
      >
        {scenarios.status === 'loading' ? (
          <Loading message="Loading supported scenarios…" />
        ) : scenarios.status === 'error' ? (
          <ErrorState error={scenarios.error} retry={() => setRevision(n => n + 1)} />
        ) : inputs && (
          <form onSubmit={event => { void submit(event); }}>
            <fieldset disabled={pending} className="scenario-grid">
              <legend className="sr-only">Simulation scenario</legend>
              <label>
                EV hub rating
                <select
                  aria-label="EV hub rating"
                  value={inputs.ev_kw}
                  onChange={e => setInputs({ ...inputs, ev_kw: Number(e.target.value) as EvKw })}
                >
                  {scenarios.data.enums.ev_kw.map(value => (
                    <option key={value} value={value}>{value} kW</option>
                  ))}
                </select>
                <small><strong>EV Demand:</strong> Adds charging demand to the selected transformer.</small>
              </label>

              <label>
                Installed solar
                <select
                  aria-label="Installed solar"
                  value={inputs.pv_kwp}
                  onChange={e => setInputs({ ...inputs, pv_kwp: Number(e.target.value) as PvKwp })}
                >
                  {scenarios.data.enums.pv_kwp.map(value => (
                    <option key={value} value={value}>{value} kWp</option>
                  ))}
                </select>
                <small><strong>Solar PV:</strong> Models local generation that can offset demand.</small>
              </label>

              <label>
                Representative day
                <select
                  aria-label="Representative day"
                  value={inputs.day_type}
                  onChange={e => setInputs({ ...inputs, day_type: e.target.value as DayType })}
                >
                  {scenarios.data.enums.day_type.map(value => (
                    <option key={value} value={value}>{label(value)}</option>
                  ))}
                </select>
                <small>Changes seasonal demand profiles and ambient temperature.</small>
              </label>

              <label>
                Existing load
                <select
                  aria-label="Existing load"
                  value={inputs.load_level}
                  onChange={e => setInputs({ ...inputs, load_level: e.target.value as LoadLevel })}
                >
                  {scenarios.data.enums.load_level.map(value => (
                    <option key={value} value={value}>{label(value)}</option>
                  ))}
                </select>
                <small>Demand already on the transformer before adding EV charging.</small>
              </label>
            </fieldset>

            <BatteryControls
              enabled={batteryEnabled}
              setEnabled={setBatteryEnabled}
              fields={batteryFields}
              setFields={setBatteryFields}
              pending={pending}
            />

            <div className="form-footer">
              <p>
                <strong>Battery Storage:</strong> Models charging and discharging to manage grid stress. Calculated by the Python engine.
              </p>
              <button className="button" type="submit" disabled={pending}>
                {pending ? 'Running simulation…' : 'Run simulation'} <span aria-hidden="true">→</span>
              </button>
            </div>
          </form>
        )}
      </Panel>

      {pending && <Loading message="Running the transformer model…" />}
      {error !== null && <ErrorState error={error} />}

      {!pending && (
        <PrecomputedFallback
          onInspect={(data, stamp) => {
            setResult(data);
            setSubmitted(data.meta.inputs);
            setProvenance(stamp);
            setReference(null);
            setError(null);
          }}
        />
      )}

      {provenance && (
        <p className="provenance-banner" role="status">
          <strong>Precomputed snapshot — not live.</strong> {provenance}. This is the explicitly selected scenario, not a substitute for your submitted inputs. Limits for the current backend may differ.
        </p>
      )}

      {reference && (
        <div className="comparison-controls">
          <p>
            A · pinned successful scenario: {scenarioLabel(reference)}. Run another scenario for B.
            <br />
            <small><strong>Scenario Comparison:</strong> Shows how changing inputs affects grid performance.</small>
          </p>
          <button type="button" className="button secondary" onClick={() => setReference(null)}>
            Clear comparison A
          </button>
        </div>
      )}

      {!pending && !result && error === null && (
        <Panel title="Assessment results">
          <Empty title="Ready when you are">
            Choose a supported scenario and run the model. No estimated metrics are shown before a successful response.
          </Empty>
        </Panel>
      )}

      {result && submitted && (
        <div aria-live="polite">
          {/* Result Heading with verdict */}
          <div className="result-heading">
            <div>
              <span className="small-label">03 · EXPLORE YOUR RESULTS</span>
              <h2>{label(submitted.day_type)} · {label(submitted.load_level)}</h2>
              <p>
                {submitted.ev_kw} kW EV hub / {submitted.pv_kwp} kWp solar · Engine {result.meta.engine_version} · {result.meta.source}
              </p>
            </div>
            <span className="tag">{label(result.verdict.status)}</span>
          </div>

          {/* Prominent Simulation Verdict Summary */}
          {verdictInfo && (
            <div className={`verdict ${verdictInfo.className}`}>
              <strong>{verdictInfo.title}</strong>
              <p>{verdictInfo.summary}</p>
              <p className="verdict-detail">{result.verdict.message}</p>
            </div>
          )}

          {!provenance && (
            <div className="comparison-controls">
              <button className="button secondary" type="button" onClick={() => setReference(result)}>
                Use as comparison A
              </button>
              <p>
                Pin this successful result, then change inputs and run a second scenario. Comparison stays in this page only.
              </p>
            </div>
          )}

          {/* Key Metrics Grid */}
          <div className="metric-grid">
            <Metric
              label="Minimum voltage"
              value={number(result.summary.min_voltage_pu, 4)}
              unit="p.u."
              description={`Lowest modeled voltage at ${result.summary.min_voltage_time} · Statutory bounds prevent equipment trips`}
            />
            <Metric
              label="Peak hot-spot"
              value={number(result.summary.peak_hotspot_c, 4)}
              unit="°C"
              description={`Hottest winding point at ${result.summary.peak_hotspot_time} · Drives IEEE C57.91 insulation aging`}
            />
            <Metric
              label="Peak loading"
              value={number(result.summary.peak_loading_pct, 4)}
              unit="%"
              description={`Demand on rated current at ${result.summary.peak_loading_time} · >100% risks accelerated aging`}
            />
            <Metric
              label="Alert events"
              value={number(result.alerts.length)}
              description="Returned limit events · not damage predictions"
            />
          </div>

          {/* The centerpiece: 3 Synchronized Simulation Graphs Visible Simultaneously */}
          <Panel
            title="24-hour simulation series"
            subtitle="Actual 15-minute samples. Synchronized time inspection across voltage, loading and thermal stress."
          >
            <SimulationCharts
              result={result}
              assumptions={
                !provenance && scenarios.status === 'success' && scenarios.data.engine_version === result.meta.engine_version
                  ? scenarios.data.assumptions
                  : []
              }
              reference={reference}
            />
          </Panel>

          {reference && <ScenarioComparison a={reference} b={result} />}

          {!provenance && <DispatchMonitor key={JSON.stringify(submitted)} scenario={submitted} />}

          {result.bess && (
            <Panel
              title="Battery energy ledger"
              subtitle="Grid-side energy and stored SOC; final SOC is not guaranteed to equal initial SOC."
            >
              <dl className="summary-list">
                <div><dt>Battery size</dt><dd>{number(result.bess.power_kw, 4)} kW / {number(result.bess.energy_kwh, 4)} kWh</dd></div>
                <div><dt>Initial → final SOC</dt><dd>{number(result.bess.initial_soc_pct, 4)}% → {number(result.bess.final_soc_pct, 4)}%</dd></div>
                <div><dt>Energy charged</dt><dd>{number(result.bess.charged_kwh, 4)} kWh</dd></div>
                <div><dt>Energy discharged</dt><dd>{number(result.bess.discharged_kwh, 4)} kWh</dd></div>
                <div><dt>Conversion losses</dt><dd>{number(result.bess.loss_kwh, 4)} kWh</dd></div>
              </dl>
            </Panel>
          )}

          {/* Secondary Details & Methodology in clean expandable panels */}
          <div className="two-column">
            <Panel title="Aging and voltage summary">
              <dl className="summary-list">
                <div><dt>Peak voltage deviation</dt><dd>{number(result.summary.peak_voltage_deviation_pu, 4)} p.u.</dd></div>
                <div><dt>Peak aging acceleration</dt><dd>{number(result.summary.peak_aging_factor, 4)} × reference</dd></div>
                <div><dt>Equivalent reference aging</dt><dd>{number(result.summary.daily_equivalent_aging_hours, 4)} h/day</dd></div>
                <div><dt>Reference-model life estimate</dt><dd>{number(result.summary.insulation_life_years, 4)} years</dd></div>
              </dl>
              <p className="inline-note">The capped model life estimate is not measured remaining service life or a failure-date prediction.</p>
            </Panel>

            <Panel title="Alert events" subtitle="Severity and affected step range from the engine.">
              {result.alerts.length ? (
                <ul className="alert-list">
                  {result.alerts.map((alert, index) => (
                    <li key={`${alert.type}-${alert.start}-${index}`}>
                      <span className={`tag ${alert.severity}`}>{label(alert.severity)}</span>
                      <div>
                        <strong>{label(alert.type)}</strong>
                        <p>{alert.start}–{alert.end} · {number(alert.peak_value, 4)} {alert.unit}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <Empty title="No threshold events">The engine returned no alerts for this scenario.</Empty>
              )}
            </Panel>
          </div>
        </div>
      )}

      <ModelNote />
    </>
  );
}
