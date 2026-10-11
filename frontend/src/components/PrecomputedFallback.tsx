import { useEffect, useState } from 'react';
import { ErrorState, Panel } from './ui';
import { isSnapshot, type Snapshot } from '../utils/precomputed';
import type { SimulationResult } from '../types/api';
export function PrecomputedFallback({ onInspect }: { onInspect: (result: SimulationResult, provenance: string) => void }) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open) return;
    let active = true;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    void globalThis.fetch(`${import.meta.env.BASE_URL}precomputed/scenarios.json`, { signal: controller.signal, cache: 'no-store' }).then(async response => {
      if (!response.ok) throw new Error(`Snapshot unavailable (HTTP ${response.status}).`);
      const data: unknown = await response.json();
      if (!isSnapshot(data)) throw new Error('Snapshot failed contract validation.');
      if (!controller.signal.aborted) setSnapshot(data);
    }).catch(cause => { if (!active) return; if (!controller.signal.aborted) setError(cause); else setError(new Error('Snapshot request did not complete.')); }).finally(() => clearTimeout(timer));
    return () => { active = false; clearTimeout(timer); controller.abort(); };
  }, [open]);
  return <Panel className="fallback-panel" title="Precomputed scenarios" subtitle="Optional engine snapshots, never live measurements or automatic replacements for your request.">
    <button type="button" className="button secondary" onClick={() => setOpen(true)} disabled={open}>Inspect available precomputed scenarios</button>
    {error !== null && <ErrorState error={error} />}
    {snapshot && <><p>Generated {snapshot.generated_at} · Engine {snapshot.engine_version}</p><p>Model/configuration fingerprint: <code>{snapshot.model_sha256}</code>. Current deployed model fingerprint is unknown; equivalence is not claimed.</p>
      <div className="snapshot-choices">{snapshot.artifacts.map(item => <button type="button" className="button secondary" key={item.id} onClick={() => onInspect(item.result, `${snapshot.generated_at} · Engine ${snapshot.engine_version} · Model ${snapshot.model_sha256}`)}>View precomputed: {item.inputs.ev_kw} kW EV / {item.inputs.pv_kwp} kWp solar · {item.inputs.day_type} · {item.inputs.load_level}</button>)}</div>
    </>}
  </Panel>;
}
