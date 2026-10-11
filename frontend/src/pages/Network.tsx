import { useData } from '../app/DataProvider';
import { TransformerTable } from '../components/TransformerTable';
import { Empty, ErrorState, Loading, ModelNote, PageHeading, Panel } from '../components/ui';
import { number } from '../utils/format';

export function Network() {
  const { network, refresh } = useData();
  return <><PageHeading eyebrow="NETWORK CONFIGURATION" title="Know the neighbourhood.">Review transformer branches and their associated charging sites. Interactive network exploration is upcoming.</PageHeading>
    {network.status === 'loading' ? <Loading /> : network.status === 'error' ? <ErrorState error={network.error} retry={refresh} /> : <>
      <Panel title={network.data.neighbourhood.name} subtitle="Transformer configuration returned by the backend"><TransformerTable network={network.data} /></Panel>
      <Panel title="Candidate charging sites" subtitle="Configured locations and rating ceilings; these are not placement recommendations.">{network.data.sites.length ? <div className="table-scroll"><table><caption className="sr-only">Candidate site configuration</caption><thead><tr><th scope="col">Site</th><th scope="col">Transformer</th><th scope="col" className="numeric">Footfall score</th><th scope="col" className="numeric">Site ceiling</th></tr></thead><tbody>{network.data.sites.map(site => <tr key={site.id}><th scope="row"><span className="equipment-id">{site.id}</span><span className="equipment-name">{site.name}</span></th><td>{site.transformer_id}</td><td className="numeric">{number(site.footfall_score)}</td><td className="numeric">{number(site.max_kw)} <span className="unit">kW</span></td></tr>)}</tbody></table></div> : <Empty title="No candidate sites">No site data was returned by the API.</Empty>}</Panel>
      <details className="panel assumptions"><summary>Configuration assumptions <span>{network.data.assumptions.length} notes</span></summary><div className="assumptions-list">{network.data.assumptions.map(item => <div key={item.name}><strong>{item.name}</strong><p>{item.note}</p></div>)}</div></details>
    </>}<ModelNote /></>;
}
