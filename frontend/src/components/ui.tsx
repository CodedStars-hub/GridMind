import type { ReactNode } from 'react';
import { ApiError } from '../api/client';

export function PageHeading({ eyebrow, title, children, action }: { eyebrow: string; title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <div className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="page-description">{children}</p>
      </div>
      {action}
    </div>
  );
}

export function Panel({ title, subtitle, children, className = '' }: { title: string; subtitle?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <h2>{title}</h2>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {children}
    </section>
  );
}

export function Metric({ label, value, unit, description }: { label: string; value: string; unit?: string; description: string }) {
  return (
    <div className="metric">
      <p>{label}</p>
      <div className="metric-value">
        {value}
        {unit && <span>{unit}</span>}
      </div>
      <p className="metric-note">{description}</p>
    </div>
  );
}

export function Loading({ message = 'Loading from the API…' }: { message?: string }) {
  return (
    <div className="state" role="status">
      <span className="loading-ring" aria-hidden="true" />
      <p>{message}</p>
    </div>
  );
}

export function Empty({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="state">
      <p className="state-title">{title}</p>
      <p>{children}</p>
    </div>
  );
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const message = error instanceof Error ? error.message : 'The request could not be completed.';
  return (
    <div className="error-state" role="alert">
      <strong>{error instanceof ApiError && error.status === 429 ? 'The API is busy' : 'Data unavailable'}</strong>
      <p>{message}</p>
      {error instanceof ApiError && error.status === 429 && (
        <p>Please pause before trying again. Your request has not been replaced with estimated data.</p>
      )}
      {error instanceof ApiError && error.field && <p>Field: {error.field}</p>}
      {retry && (
        <button type="button" className="button secondary" onClick={retry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function ModelNote() {
  return (
    <p className="model-note">
      <span aria-hidden="true">ⓘ</span> Planning-grade engineering model. Configuration is illustrative; calculated results are not real-time measurements or utility interconnection approvals.
    </p>
  );
}
