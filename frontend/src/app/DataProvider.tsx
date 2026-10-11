import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { createApiClient, type ApiClient } from '../api/client';
import type { HealthResponse, NetworkResponse } from '../types/api';

export type Resource<T> = { status: 'loading' } | { status: 'success'; data: T } | { status: 'error'; error: unknown };
interface Data { health: Resource<HealthResponse>; network: Resource<NetworkResponse>; refresh: () => void; client: ApiClient }
const Context = createContext<Data | null>(null);
export function DataProvider({ children, client: providedClient }: { children: ReactNode; client?: ApiClient }) {
  const [client] = useState(() => providedClient ?? createApiClient());
  const [health, setHealth] = useState<Resource<HealthResponse>>({ status: 'loading' });
  const [network, setNetwork] = useState<Resource<NetworkResponse>>({ status: 'loading' });
  const [revision, setRevision] = useState(0);
  const active = useRef<AbortController | null>(null);
  const refresh = useCallback(() => { active.current?.abort(); setRevision(n => n + 1); }, []);
  useEffect(() => {
    const controller = new AbortController(); active.current = controller;
    setHealth({ status: 'loading' }); setNetwork({ status: 'loading' });
    async function load() {
      // Sequential requests respect the backend's small request burst budget.
      try { const data = await client.health(controller.signal); if (!controller.signal.aborted) setHealth({ status: 'success', data }); }
      catch (error) { if (!controller.signal.aborted) setHealth({ status: 'error', error }); }
      if (controller.signal.aborted) return;
      try { const data = await client.network(controller.signal); if (!controller.signal.aborted) setNetwork({ status: 'success', data }); }
      catch (error) { if (!controller.signal.aborted) setNetwork({ status: 'error', error }); }
    }
    void load();
    return () => controller.abort();
  }, [client, revision]);
  return <Context.Provider value={{ health, network, refresh, client }}>{children}</Context.Provider>;
}
export function useData(): Data {
  const value = useContext(Context);
  if (!value) throw new Error('useData must be used inside DataProvider');
  return value;
}
