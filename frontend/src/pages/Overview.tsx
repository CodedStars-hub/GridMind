import { useState } from 'react';
import { useData } from '../app/DataProvider';
import { Empty, ErrorState, Loading, Metric, ModelNote, Panel } from '../components/ui';
import { TransformerTable } from '../components/TransformerTable';
import { Icon } from '../components/Icon';
import { number } from '../utils/format';

export function Overview() {
  const { health, network, refresh } = useData();
  const [inventoryOpen, setInventoryOpen] = useState(false);
  return <>
    <section className="overview-hero">
      <div className="hero-story"><p className="eyebrow"><span className="status-dot" /> EV CHARGING · GRID INTELLIGENCE</p><h1>More charging.<br /><span>A grid that can handle it.</span></h1><p>See how EV demand changes voltage, transformer stress and ageing. Test the alternatives before you build.</p><div className="hero-actions"><a href="#/assessment" className="button">Run a simulation <Icon name="arrow" /></a><a href="#/network" className="button secondary">Explore Network</a></div><div className="hero-footnote"><Icon name="chart" /><span>One shared engineering engine. Transparent assumptions.</span></div></div>
      <div className="hero-network"><div className="preview-heading"><span className="small-label">NEIGHBOURHOOD SNAPSHOT</span><span className="tag">Conceptual inventory</span></div>
        {network.status === 'loading' ? <Loading message="Loading neighbourhood configuration…" /> : network.status === 'error' ? <Empty title="Preview unavailable">Connect to the API to explore configured assets. No network data is assumed.</Empty> : !network.data.transformers.length ? <Empty title="No transformers configured">The API returned an empty inventory.</Empty> : <div className="preview-assets">{network.data.transformers.map(t => <a href={`#/network?transformer=${encodeURIComponent(t.id)}`} className="preview-asset" key={t.id} aria-label={`Explore ${t.id}: ${t.name}`}><div><span className="equipment-id">{t.id}</span><Icon name="bolt" /></div><strong>{t.name}</strong><span>{number(t.rated_kva)} <small>kVA</small></span><p>{network.data.sites.filter(s => s.transformer_id === t.id).length} candidate sites</p></a>)}</div>}
        <p className="preview-note">Configured assets · no physical feeder topology or live telemetry implied.</p>
      </div>
    </section>
    {health.status === 'error' && <ErrorState error={health.error} retry={refresh} />}
    {network.status === 'error' && <ErrorState error={network.error} retry={refresh} />}
    <div className="journey-strip" aria-label="How GridMind works">{[{n:'01',name:'Understand',text:'Explore assets & demand',icon:'grid' as const},{n:'02',name:'Simulate',text:'Test a full 24-hour day',icon:'chart' as const},{n:'03',name:'Compare',text:'See stress & voltage changes',icon:'bolt' as const},{n:'04',name:'Intervene',text:'Try storage or managed charging',icon:'battery' as const}].map(step => <div key={step.n}><span>{step.n}</span><Icon name={step.icon} /><div><strong>{step.name}</strong><p>{step.text}</p></div></div>)}</div>
    {network.status === 'success' && <>
      <div className="section-label"><div><span className="small-label">YOUR NEIGHBOURHOOD</span><h2>{network.data.neighbourhood.name}</h2></div><span className="tag">{network.data.meta.source === 'live' ? 'API configuration' : 'Cached configuration'}</span></div>
      <div className="metric-grid"><Metric label="Transformers" value={number(network.data.transformers.length)} description="Independent modeled branches" /><Metric label="Candidate sites" value={number(network.data.sites.length)} description="Configured charging opportunities" /><Metric label="Nameplate capacity" value={number(network.data.transformers.reduce((sum, t) => sum + t.rated_kva, 0))} unit="kVA" description="Sum of ratings · not available headroom" /><Metric label="Customer connections" value={number(network.data.transformers.reduce((sum, t) => sum + t.connections, 0))} description="Configured connections · not damaged homes" /></div>
      <details className="panel inventory-details" onToggle={event => setInventoryOpen(event.currentTarget.open)}><summary>Transformer inventory <span>View equipment configuration</span></summary>{inventoryOpen && <TransformerTable network={network.data} />}</details>
    </>}
    <div className="capability-grid"><Panel title="Simulation studio" subtitle="No results have been assumed"><div className="capability-icon"><Icon name="chart" /></div><p>Explore the whole day, not just the peak. Inspect voltage, loading and hot-spot temperatures, then compare a battery alternative.</p><a className="text-link panel-link" href="#/assessment">Open assessment <Icon name="arrow" /></a></Panel><Panel title="Network explorer" subtitle="Infrastructure, in context"><div className="capability-icon"><Icon name="grid" /></div><p>Select a transformer or charging site to understand its capacity, demand profile and configured associations.</p><a className="text-link panel-link" href="#/network">Explore the neighbourhood <Icon name="arrow" /></a></Panel><Panel title="Placement planning" subtitle="Decisions under constraints"><div className="capability-icon"><Icon name="plan" /></div><p>Run the existing planner to see allocations, electrical constraints and the trade-offs against modelled uncontrolled placement.</p><a className="text-link panel-link" href="#/planning">Open planning workspace <Icon name="arrow" /></a></Panel></div>
    <ModelNote />
  </>;
}
