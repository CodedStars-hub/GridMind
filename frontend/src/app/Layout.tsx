import { BrandLogo } from '../components/BrandLogo';
import { Icon } from '../components/Icon';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useData } from './DataProvider';

export const routes = [
  { path: '/', title: 'Overview', icon: 'grid' as const, detail: 'Workspace' },
  { path: '/network', title: 'Network', icon: 'bolt' as const, detail: 'Neighbourhood' },
  { path: '/assessment', title: 'Assessment', icon: 'chart' as const, detail: 'Transformer model' },
  { path: '/planning', title: 'Planning', icon: 'plan' as const, detail: 'Infrastructure' },
];

export function Layout({ path, children }: { path: string; children: ReactNode }) {
  const { health, network, refresh } = useData();
  const [menuOpen, setMenuOpen] = useState(false);
  const main = useRef<HTMLElement>(null);
  const previousPath = useRef(path);

  useEffect(() => {
    setMenuOpen(false);
    if (previousPath.current !== path) {
      main.current?.focus();
      previousPath.current = path;
    }
    document.title = `${routes.find(r => r.path === path)?.title ?? 'Page not found'} · GridMind`;
  }, [path]);

  const status = health.status === 'success' ? 'API connected' : health.status === 'error' ? 'API unavailable' : 'Connecting to API';

  return (
    <div className="app-shell">
      <a href="#main" className="skip-link" onClick={event => { event.preventDefault(); main.current?.focus(); }}>
        Skip to content
      </a>

      <aside className="sidebar">
        <a className="brand" href="#/" aria-label="GridMind overview">
          <span className="brand-mark" aria-hidden="true">
            <BrandLogo />
          </span>
          <span>
            GridMind
            <small>EV Infrastructure Intelligence</small>
          </span>
        </a>

        <button 
          type="button"
          className="menu-toggle" 
          aria-expanded={menuOpen} 
          aria-controls="primary-nav" 
          onClick={() => setMenuOpen(open => !open)}
        >
          Navigation <span aria-hidden="true">{menuOpen ? '−' : '+'}</span>
        </button>

        <nav id="primary-nav" className={menuOpen ? 'open' : ''} aria-label="Primary navigation">
          <p className="nav-label">WORKSPACE</p>
          {routes.map(route => (
            <a 
              key={route.path} 
              href={`#${route.path}`} 
              aria-current={path === route.path ? 'page' : undefined}
            >
              <span className="nav-icon" aria-hidden="true">
                <Icon name={route.icon} />
              </span>
              <span>{route.title}</span>
              {path === route.path && <span className="nav-dot" aria-hidden="true" />}
            </a>
          ))}
        </nav>

        <div className="sidebar-note">
          <span className="small-label">ENGINEERING CONSOLE</span>
          <p>Understand the grid.<br />Plan with evidence.</p>
          <span>Illustrative neighbourhood data</span>
        </div>

        <div className="sidebar-footer">
          <span className="brand-mini" aria-hidden="true">G</span>
          <div>
            Engineering workspace
            <small>Planning-grade · API v2</small>
          </div>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <span>/</span> <strong>{routes.find(r => r.path === path)?.title ?? 'Not found'}</strong>
          </div>
          
          <div className="header-actions">
            <span className={`connection ${health.status}`} role="status">
              <span className="status-dot" aria-hidden="true" />
              {status}
            </span>
            <button 
              type="button"
              className="refresh-button" 
              aria-label="Refresh API connection and network data" 
              disabled={health.status === 'loading' || network.status === 'loading'} 
              onClick={refresh}
            >
              <span aria-hidden="true">↻</span>
            </button>
          </div>
        </header>

        <main id="main" ref={main} tabIndex={-1}>
          {children}
        </main>

        <footer className="workspace-footer">
          <span>GridMind · Engineering estimates, clearly explained.</span>
          <span>
            {health.status === 'success' 
              ? `Engine ${health.data.engine_version} / API ${health.data.api_version}` 
              : 'Connection status shown above'}
          </span>
        </footer>
      </div>
    </div>
  );
}
