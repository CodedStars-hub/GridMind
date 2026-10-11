import { useEffect, useRef, useState } from 'react';
import { ApiError } from '../api/client';
import { useData } from '../app/DataProvider';
import type { ScenarioRequest } from '../types/api';
import type { DispatchResponse, ReplayResponse } from '../types/telemetry';
import { ErrorState, Panel } from './ui';
import { label, number } from '../utils/format';

export function DispatchMonitor({ scenario }: { scenario: ScenarioRequest }) {
  const { client } = useData();
  const [start, setStart] = useState('');
  const [replay, setReplay] = useState<ReplayResponse | null>(null);
  const [index, setIndex] = useState(-1);
  const [decision, setDecision] = useState<DispatchResponse | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);
  const active = useRef<AbortController | null>(null);
  useEffect(() => () => active.current?.abort(), []);
  async function load() {
    const controller = new AbortController(); active.current = controller;
    setPending(true); setError(null); setReplay(null); setIndex(-1); setDecision(null);
    try {
      const data = await client.replay({ scenario, start_time: start }, controller.signal);
      if (!controller.signal.aborted) setReplay(data);
    } catch (cause) { if (!controller.signal.aborted) setError(cause); }
    finally { if (!controller.signal.aborted) setPending(false); }
  }
  async function next() {
    if (!replay || pending || index + 1 >= replay.records.length) return;
    const nextIndex = index + 1, record = replay.records[nextIndex]!;
    const controller = new AbortController(); active.current = controller;
    setPending(true); setError(null); setDecision(null);
    try {
      const response = await client.evaluateDispatch({ telemetry: record, now: record.timestamp, previous_timestamp: index >= 0 ? replay.records[index]!.timestamp : null, battery: replay.battery }, controller.signal);
      if (response.telemetry_timestamp !== record.timestamp) throw new ApiError('Dispatch response timestamp does not match the requested sample.', 'invalid_response');
      if (!controller.signal.aborted) { setDecision(response); setIndex(nextIndex); }
    } catch (cause) { if (!controller.signal.aborted) setError(cause); }
    finally { if (!controller.signal.aborted) setPending(false); }
  }
  const record = replay && index >= 0 ? replay.records[index] : null;
  const reading = (value: number | null | undefined, unit: string) => value == null ? 'Unavailable' : `${number(value, 4)} ${unit}`;
  return <Panel title="Dispatch Monitoring" subtitle="Simulated replay · advisory only · no physical hardware or IoT publishing.">
    <div className="dispatch-monitor">
      <p>This replay uses independent simulation outputs. Recommendations do not change the next replay sample or command a device. Evaluation uses the replay timestamp as its simulated clock.</p>
      <label>Replay start (UTC ISO timestamp)<input value={start} placeholder="YYYY-MM-DDTHH:MM:SSZ" onChange={event => setStart(event.target.value)} disabled={pending} /></label>
      <div className="comparison-controls"><button type="button" className="button secondary" disabled={pending || !start.trim()} onClick={() => { void load(); }}>{pending ? 'Processing replay…' : 'Load simulated replay'}</button>{replay && <button type="button" className="button" disabled={pending || index + 1 >= replay.records.length} onClick={() => { void next(); }}>Evaluate next sample</button>}</div>
      {error !== null && <ErrorState error={error} />}
      {!replay && error === null && <p>No telemetry loaded. Local M16 backend required; the deployed API may not support these routes.</p>}
      {replay && <><p role="status">Replay progress: {index + 1} / {replay.records.length} samples evaluated</p><progress aria-label="Replay progress" max={replay.records.length} value={index + 1} />{record && <dl className="summary-list"><div><dt>Simulated transformer</dt><dd>{record.transformer_id}</dd></div><div><dt>Timestamp</dt><dd>{record.timestamp}</dd></div><div><dt>Loading</dt><dd>{reading(record.loading_pct, '%')}</dd></div><div><dt>Voltage</dt><dd>{reading(record.voltage_pu, 'p.u.')}</dd></div><div><dt>Hot-spot</dt><dd>{reading(record.hotspot_c, '°C')}</dd></div><div><dt>Battery SOC</dt><dd>{reading(record.battery_soc_pct, '%')}</dd></div></dl>}</>}
      {decision && <div className="dispatch-decision" aria-live="polite"><h3>Advisory action: {label(decision.action)}</h3><p>{number(decision.power_kw, 4)} kW (+ discharge / − charge) · Predicted next SOC: {reading(decision.next_soc_pct, '%')}</p><p>Reasons: {decision.reasons.map(label).join(', ')}</p><p>Engineering alerts: {decision.alerts.length ? decision.alerts.map(label).join(', ') : 'None returned'}</p><p>Published: No. This is a bounded one-step recommendation, not proof of subsequent grid compliance.</p></div>}
    </div>
  </Panel>;
}
