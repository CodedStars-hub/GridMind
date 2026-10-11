import { isSimulation, object } from '../api/guards';
import type { ScenarioRequest, ScenarioInputs, SimulationResult } from '../types/api';
export interface Snapshot { schema_version: 1; engine_version: string; generated_at: string; model_sha256: string; source_hashes: Record<string, string>; artifacts: { id: string; inputs: SimulationResult['meta']['inputs']; result: SimulationResult }[] }
const canonical = (value: unknown): string => {
  if (Array.isArray(value)) return JSON.stringify(value.map(item => JSON.parse(canonical(item)) as unknown));
  if (object(value)) return JSON.stringify(Object.fromEntries(Object.keys(value).sort().map(key => [key, JSON.parse(canonical(value[key])) as unknown])));
  return JSON.stringify(value);
};
export function isSnapshot(value: unknown): value is Snapshot {
  return object(value) && value.schema_version === 1 && typeof value.engine_version === 'string' && typeof value.generated_at === 'string' && Number.isFinite(Date.parse(value.generated_at)) && typeof value.model_sha256 === 'string' && /^[a-f0-9]{64}$/.test(value.model_sha256) && object(value.source_hashes) && Object.values(value.source_hashes).every(hash => typeof hash === 'string' && /^[a-f0-9]{64}$/.test(hash)) && Array.isArray(value.artifacts) && value.artifacts.length > 0 && new Set(value.artifacts.map(item => object(item) ? item.id : null)).size === value.artifacts.length && value.artifacts.every(item => object(item) && typeof item.id === 'string' && isSimulation(item.result) && item.result.meta.source === 'cached' && item.result.meta.engine_version === value.engine_version && canonical(item.inputs) === canonical(item.result.meta.inputs));
}
export function exactSnapshot(snapshot: Snapshot, request: ScenarioRequest | ScenarioInputs, engineVersion: string, modelSha256: string): SimulationResult | null {
  if (snapshot.engine_version !== engineVersion || snapshot.model_sha256 !== modelSha256) return null;
  const inputs = { bess: 'off', ...request, bess_override: request.bess_override ?? null };
  return snapshot.artifacts.find(item => canonical(item.inputs) === canonical(inputs))?.result ?? null;
}
