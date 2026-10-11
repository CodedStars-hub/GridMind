import { useEffect, useState } from 'react';
import { useData } from '../app/DataProvider';
import { NetworkExplorer, type Selection } from '../components/NetworkExplorer';
import { Empty, ErrorState, Loading, ModelNote, PageHeading, Panel } from '../components/ui';
import { number } from '../utils/format';

export function Network() {
  const { network, refresh } = useData();
  const selectedFromLink = () => {
    const id = new URLSearchParams(window.location.hash.split('?')[1] ?? '').get('transformer');
    return id ? { kind: 'transformer' as const, id } : null;
  };
  const [selection, setSelection] = useState<Selection | null>(selectedFromLink);

  useEffect(() => {
    const followLink = () => {
      const selected = selectedFromLink();
      if (selected) setSelection(selected);
    };
    window.addEventListener('hashchange', followLink);
    return () => window.removeEventListener('hashchange', followLink);
  }, []);

  return (
    <>
      <PageHeading eyebrow="NETWORK CONFIGURATION" title="Explore the network.">
        Explore modeled transformers, connected candidate sites, and infrastructure constraints. Choose an asset to see what it serves, its configured demand and where charging could fit. Operating risk requires a simulation.
      </PageHeading>

      {/* Contextual concepts guide */}
      <div className="network-concept-strip" role="region" aria-label="Key infrastructure concepts">
        <div className="concept-pill">
          <strong>Transformer Capacity</strong>
          <small>250 kVA continuous thermal rating</small>
        </div>
        <div className="concept-pill">
          <strong>Candidate Sites</strong>
          <small>Prospective EV charging locations</small>
        </div>
        <div className="concept-pill">
          <strong>Connected Load</strong>
          <small>Residential & commercial baseload</small>
        </div>
        <div className="concept-pill">
          <strong>Managed Charging</strong>
          <small>Power curtailment to prevent peaks</small>
        </div>
      </div>

      {network.status === 'loading' ? (
        <Loading />
      ) : network.status === 'error' ? (
        <ErrorState error={network.error} retry={refresh} />
      ) : (
        <>
          <Panel
            title={network.data.neighbourhood.name}
            subtitle="Transformer configuration returned by the backend. Select a transformer or site to view specifications."
          >
            <NetworkExplorer network={network.data} selection={selection} onSelectionChange={setSelection} />
          </Panel>

          <Panel
            title="Candidate charging sites"
            subtitle="Configured locations and rating ceilings; these are not placement recommendations."
          >
            {network.data.sites.length ? (
              <div className="table-scroll">
                <table>
                  <caption className="sr-only">Candidate site configuration</caption>
                  <thead>
                    <tr>
                      <th scope="col">Site</th>
                      <th scope="col">Transformer</th>
                      <th scope="col" className="numeric">Footfall score</th>
                      <th scope="col" className="numeric">Site ceiling</th>
                    </tr>
                  </thead>
                  <tbody>
                    {network.data.sites.map(site => (
                      <tr key={site.id}>
                        <th scope="row">
                          <span className="equipment-id">{site.id}</span>
                          <span className="equipment-name">{site.name}</span>
                        </th>
                        <td>{site.transformer_id}</td>
                        <td className="numeric">{number(site.footfall_score)}</td>
                        <td className="numeric">
                          {number(site.max_kw)} <span className="unit">kW</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty title="No candidate sites">No site data was returned by the API.</Empty>
            )}
          </Panel>

          <details className="panel assumptions">
            <summary>
              Configuration assumptions <span>{network.data.assumptions.length} notes</span>
            </summary>
            <div className="assumptions-list">
              {network.data.assumptions.map(item => (
                <div key={item.name}>
                  <strong>{item.name}</strong>
                  <p>{item.note}</p>
                </div>
              ))}
            </div>
          </details>
        </>
      )}

      <ModelNote />
    </>
  );
}
