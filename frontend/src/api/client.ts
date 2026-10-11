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
  private async request<T>(path: string, guard: (value: unknown) => value is T, payload?: ScenarioRequest, signal?: AbortSignal): Promise<T> {
    const controller = new AbortController();
    let timedOut = false;
    const abort = () => controller.abort();
    signal?.addEventListener('abort', abort, { once: true });
    if (signal?.aborted) controller.abort();
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, this.timeoutMs);
    try {
      const response = await this.transport(`${this.base}${path}`, {
        method: payload === undefined ? 'GET' : 'POST', signal: controller.signal,
        credentials: 'omit', cache: 'no-store',
        headers: payload === undefined ? { Accept: 'application/json' } : { Accept: 'application/json', 'Content-Type': 'application/json' },
        ...(payload === undefined ? {} : { body: JSON.stringify(payload) }),
      });
      let body: unknown;
      try { body = await response.json(); }
      catch { throw new ApiError('The API returned an unreadable response.', 'invalid_response', response.status); }
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
  health(signal?: AbortSignal): Promise<HealthResponse> { return this.request('/v2/health', isHealth, undefined, signal); }
  network(signal?: AbortSignal): Promise<NetworkResponse> { return this.request('/v2/network', isNetwork, undefined, signal); }
  scenarios(signal?: AbortSignal): Promise<ScenariosResponse> { return this.request('/v2/scenarios', isScenarios, undefined, signal); }
  simulate(payload: ScenarioRequest, signal?: AbortSignal): Promise<SimulationResult> { return this.request('/v2/simulate', isSimulation, payload, signal); }
}
export const createApiClient = () => new ApiClient(import.meta.env.VITE_API_BASE_URL || '/api');
