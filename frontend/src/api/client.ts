import type { PlanRequest, PlanResult } from '../types/planning';
import { isPlan } from './planningGuard';
import type { ReplayRequest, ReplayResponse, DispatchRequest, DispatchResponse } from '../types/telemetry';
import { isReplay, isDispatch } from './telemetryGuards';
import type { HealthResponse, NetworkResponse, ScenariosResponse, ScenarioRequest, SimulationResult } from '../types/api';
import { isHealth, isNetwork, isScenarios, isSimulation, object } from './guards';

export class ApiError extends Error {
  constructor(message: string, public readonly code: string, public readonly status: number | null = null, public readonly field: string | null = null) {
    super(message); this.name = 'ApiError';
  }
}
export function normalizeBaseUrl(value: string): string {
  const base = value.trim().replace(/\/+$/, '');
  if (base.startsWith('/') && !base.startsWith('//') && !/[?#]/.test(base)) return base;
  try {
    const url = new URL(base);
    if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new Error();
    return base;
  } catch { throw new ApiError('Set VITE_API_BASE_URL to an HTTPS API URL or a same-origin path such as /api.', 'configuration'); }
}
export class ApiClient {
  private readonly base: string;
  // Native browser fetch needs its global receiver, even when stored on a client instance.
  constructor(base: string, private readonly timeoutMs = 20_000, private readonly transport: typeof fetch = globalThis.fetch.bind(globalThis)) {
    this.base = normalizeBaseUrl(base);
    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) throw new ApiError('Request timeout must be positive.', 'configuration');
  }
  private async request<T>(path: string, guard: (value: unknown) => value is T, payload?: ScenarioRequest | ReplayRequest | DispatchRequest | PlanRequest, signal?: AbortSignal): Promise<T> {
    const controller = new AbortController();
    let timedOut = false;
    const abort = () => controller.abort();
    signal?.addEventListener('abort', abort, { once: true });
    if (signal?.aborted) controller.abort();
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, this.timeoutMs);
    try {
      const send = () => this.transport(`${this.base}${path}`, {
        method: payload === undefined ? 'GET' : 'POST', signal: controller.signal,
        credentials: 'omit', cache: 'no-store',
        headers: payload === undefined ? { Accept: 'application/json' } : { Accept: 'application/json', 'Content-Type': 'application/json' },
        ...(payload === undefined ? {} : { body: JSON.stringify(payload) }),
      });
      let response = await send();
      // Only metadata GETs retry once, within the original total timeout budget.
      if (payload === undefined && (response.status === 429 || response.status >= 500)) {
        const retryAfter = response.headers.get('retry-after');
        const seconds = retryAfter === null ? 0.25 : /^\d+(\.\d+)?$/.test(retryAfter) ? Number(retryAfter) : Math.max(0, (Date.parse(retryAfter) - Date.now()) / 1000);
        if (Number.isFinite(seconds) && seconds <= 2 && seconds >= 0) {
          await new Promise<void>((resolve, reject) => {
            const cancel = () => { clearTimeout(wait); reject(new ApiError('The request was cancelled.', 'cancelled')); };
            const wait = setTimeout(() => { controller.signal.removeEventListener('abort', cancel); resolve(); }, seconds * 1000);
            controller.signal.addEventListener('abort', cancel, { once: true });
            if (controller.signal.aborted) cancel();
          });
          if (controller.signal.aborted) throw new ApiError('The request was cancelled.', 'cancelled');
          response = await send();
        }
      }
      let body: unknown;
      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('text/html')) throw new ApiError(`Expected API JSON but received HTML (HTTP ${response.status}). Check the Vite proxy configuration and restart the development server.`, response.ok ? 'unexpected_content_type' : 'http_error', response.status);
      try { body = await response.json(); }
      catch { throw new ApiError(response.ok ? 'The API returned invalid JSON.' : `The API returned HTTP ${response.status} without a readable JSON error.`, response.ok ? 'invalid_json' : 'http_error', response.status); }
      if (!response.ok) {
        if (object(body) && object(body.error) && typeof body.error.message === 'string' && typeof body.error.code === 'string') {
          throw new ApiError(body.error.message, body.error.code, response.status, typeof body.error.field === 'string' ? body.error.field : null);
        }
        throw new ApiError(`The API is unavailable (HTTP ${response.status}). Try again shortly.`, 'http_error', response.status);
      }
      if (!guard(body)) throw new ApiError('The API response does not match the expected contract. No results were displayed.', 'invalid_response', response.status);
      return body;
    } catch (error) {
      if (timedOut) throw new ApiError('The request timed out. Try again when the service is available.', 'timeout');
      if (signal?.aborted) throw new ApiError('The request was cancelled.', 'cancelled');
      if (error instanceof ApiError) throw error;
      throw new ApiError('Unable to reach the API. Check your connection and browser CORS configuration.', 'network_error');
    } finally { clearTimeout(timer); signal?.removeEventListener('abort', abort); }
  }
  plan(payload: PlanRequest, signal?: AbortSignal): Promise<PlanResult> { return this.request('/v2/plan', isPlan, payload, signal); }
  replay(payload: ReplayRequest, signal?: AbortSignal): Promise<ReplayResponse> { return this.request('/v2/telemetry/replay', isReplay, payload, signal); }
  evaluateDispatch(payload: DispatchRequest, signal?: AbortSignal): Promise<DispatchResponse> { return this.request('/v2/dispatch/evaluate', isDispatch, payload, signal); }
  health(signal?: AbortSignal): Promise<HealthResponse> { return this.request('/v2/health', isHealth, undefined, signal); }
  network(signal?: AbortSignal): Promise<NetworkResponse> { return this.request('/v2/network', isNetwork, undefined, signal); }
  scenarios(signal?: AbortSignal): Promise<ScenariosResponse> { return this.request('/v2/scenarios', isScenarios, undefined, signal); }
  simulate(payload: ScenarioRequest, signal?: AbortSignal): Promise<SimulationResult> { return this.request('/v2/simulate', isSimulation, payload, signal); }
}
export const createApiClient = () => new ApiClient(import.meta.env.VITE_API_BASE_URL || '/api');
