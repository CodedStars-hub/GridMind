import { useEffect } from 'react';
import type { NetworkResponse } from '../types/api';
import { label, number } from '../utils/format';
import { Empty } from './ui';

export type Selection = { kind: 'transformer' | 'site'; id: string };

/** Resolve IDs against each response: refreshed objects must never leave stale details. */
function resolveSelection(network: NetworkResponse, selection: Selection | null): Selection | null {
  if (selection?.kind === 'transformer' && network.transformers.some(t => t.id === selection.id)) return selection;
  if (selection?.kind === 'site' && network.sites.some(s => s.id === selection.id)) return selection;
  const first = network.transformers[0];
  return first ? { kind: 'transformer', id: first.id } : null;
}

export function NetworkExplorer({ network, selection: requested, onSelectionChange: setRequested }: { network: NetworkResponse; selection: Selection | null; onSelectionChange: (selection: Selection | null) => void }) {
  const selected = resolveSelection(network, requested);
  // Commit a fallback when an item disappears, so it does not reselect itself if re-added.
  useEffect(() => {
    if (requested !== null && selected !== requested) setRequested(selected);
  }, [requested, selected, setRequested]);
  const site = selected?.kind === 'site' ? network.sites.find(s => s.id === selected.id) : undefined;
  const transformerId = site?.transformer_id ?? (selected?.kind === 'transformer' ? selected.id : undefined);
  const transformer = network.transformers.find(t => t.id === transformerId);
  const associatedSites = network.sites.filter(s => s.transformer_id === transformerId);

  if (!network.transformers.length) return <Empty title="No transformers configured">The API returned an empty inventory. No equipment or connections have been assumed.</Empty>;

  return <div className="network-explorer">
    <div>
      <div className="explorer-legend"><span><i /> Transformer</span><span><i /> Candidate charging site</span><span className="tag">Conceptual inventory</span></div>
      <p className="network-topology-note">Transformer inventory · electrical topology unavailable. Grouping shows configured site associations, not feeder routes or geographic distances.</p>
      <div className="network-inventory" role="group" aria-label="Neighbourhood transformer inventory">
        {network.transformers.map(t => {
          const sites = network.sites.filter(s => s.transformer_id === t.id);
          return <section key={t.id} className={`network-branch ${transformerId === t.id ? 'selected' : ''}`} aria-label={`${t.id} infrastructure`}>
            <button className="transformer-node" aria-label={`Inspect transformer ${t.id}: ${t.name}`} aria-pressed={selected?.kind === 'transformer' && selected.id === t.id} onClick={() => setRequested({ kind: 'transformer', id: t.id })}>
              <span className="asset-identity"><span className="equipment-id">{t.id}</span><span className="asset-symbol" aria-hidden="true">ϟ</span><span className="asset-state">Not assessed</span></span><strong>{t.name}</strong>
              <span className="network-rating">{number(t.rated_kva)} kVA</span>
              <span className="network-node-note">{label(t.archetype)} · {label(t.load_level)}</span>
            </button>
            <div className="network-site-group"><span className="small-label">ASSOCIATED CANDIDATE SITES</span>
              {sites.length ? sites.map(s => <button key={s.id} className="site-node" aria-label={`Inspect site ${s.id}: ${s.name}`} aria-pressed={selected?.kind === 'site' && selected.id === s.id} onClick={() => setRequested({ kind: 'site', id: s.id })}>
                <span><span className="equipment-id">{s.id}</span>{s.name}</span><span>{number(s.max_kw)} kW ceiling</span>
              </button>) : <p className="network-node-note">No sites configured for this transformer.</p>}
            </div>
          </section>;
        })}
      </div>
    </div>
    <section className="network-detail" aria-labelledby="network-detail-heading">
      <p className="small-label">SELECTED {site ? 'CHARGING SITE' : 'TRANSFORMER'}</p>
      <h3 id="network-detail-heading">{site?.name ?? transformer?.name ?? 'Details unavailable'}</h3>
      <p className="network-detail-id">{site?.id ?? transformer?.id}</p>
      {site && <dl className="summary-list">
        <div><dt>Associated transformer</dt><dd>{site.transformer_id}</dd></div>
        <div><dt>Site rating ceiling</dt><dd>{number(site.max_kw)} kW</dd></div>
        <div><dt>Configured footfall score</dt><dd>{number(site.footfall_score)}</dd></div>
      </dl>}
      {transformer ? <>
        {site && <h4>Transformer configuration</h4>}
        <dl className="summary-list">
          <div><dt>Transformer ID</dt><dd>{transformer.id}</dd></div>
          <div><dt>Nameplate capacity</dt><dd>{number(transformer.rated_kva)} kVA</dd></div>
          <div><dt>Demand archetype</dt><dd>{label(transformer.archetype)}</dd></div>
          <div><dt>Existing load level</dt><dd>{label(transformer.load_level)}</dd></div>
          <div><dt>Charging usage profile</dt><dd>{label(transformer.ev_usage)}</dd></div>
          <div><dt>Customer connections</dt><dd>{number(transformer.connections)}</dd></div>
          <div><dt>Associated site count</dt><dd>{associatedSites.length}</dd></div>
        </dl>
        {!site && <div className="network-detail-sites"><h4>Associated candidate sites</h4>{associatedSites.length ? <ul>{associatedSites.map(s => <li key={s.id}><button className="text-link" onClick={() => setRequested({ kind: 'site', id: s.id })}>Inspect {s.id} · {s.name}</button></li>)}</ul> : <p>No candidate sites configured.</p>}</div>}
      </> : <p className="inline-note">The associated transformer is unavailable. No capacity is assumed.</p>}
      <p className="inline-note">Ratings and site ceilings are configuration, not measured loading or available hosting capacity.</p>
      <div className="network-detail-actions"><a href="#/assessment" className="button">Open assessment</a><a href="#/planning" className="text-link">Open planning workspace →</a></div>
      <p className="inline-note">Assessment currently runs a separate single-transformer scenario; these links do not transfer the selected equipment or create an allocation.</p>
    </section>
  </div>;
}
