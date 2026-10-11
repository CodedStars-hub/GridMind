import { useData } from '../app/DataProvider';
import { Empty, ErrorState, Loading, Metric, ModelNote, PageHeading, Panel } from '../components/ui';
import { TransformerTable } from '../components/TransformerTable';
import { number } from '../utils/format';

export function Overview() {
  const { health, network, refresh } = useData();
  return <>
    <PageHeading eyebrow="NEIGHBOURHOOD INTELLIGENCE" title="A clearer view of your grid." action={<a href="#/assessment" className="button">Run an assessment <span aria-hidden="true">↗</span></a>}>Explore the configured network, understand its assumptions, and start a transformer assessment.</PageHeading>
    <div className="intro-strip"><span className="tag teal">ENGINEERING WORKSPACE</span><span>Configuration from the API. Calculations run on the shared engineering engine.</span></div>
    {health.status === 'error' && <ErrorState error={health.error} retry={refresh} />}
    {network.status === 'loading' && <Loading message="Loading neighbourhood configuration…" />}
    {network.status === 'error' && <ErrorState error={network.error} retry={refresh} />}
    {network.status === 'success' && <>
      <div className="section-label"><div><span className="small-label">YOUR NEIGHBOURHOOD</span><h2>{network.data.neighbourhood.name}</h2></div><span className="tag">{network.data.meta.source === 'live' ? 'API configuration' : 'Cached configuration'}</span></div>
      <div className="metric-grid"><Metric label="Transformers" value={number(network.data.transformers.length)} description="Configured distribution branches" /><Metric label="Candidate sites" value={number(network.data.sites.length)} description="Locations defined in the network" /><Metric label="Nameplate capacity" value={number(network.data.transformers.reduce((sum, t) => sum + t.rated_kva, 0))} unit="kVA" description="Sum of configured ratings, not headroom" /><Metric label="Customer connections" value={number(network.data.transformers.reduce((sum, t) => sum + t.connections, 0))} description="Configured counts across transformers" /></div>
      <Panel title="Transformer inventory" subtitle="Equipment configuration. Operating status requires a simulation."><TransformerTable network={network.data} /></Panel>
    </>}
    <div className="two-column"><Panel title="From configuration to decisions" subtitle="A transparent engineering workflow"><ol className="workflow"><li><span>01</span><div><strong>Explore the network</strong><p>Review equipment, load profiles and candidate charging sites.</p></div></li><li><span>02</span><div><strong>Assess a transformer</strong><p>Send a supported scenario to the shared backend model.</p></div></li><li><span>03</span><div><strong>Compare infrastructure plans</strong><p>The interactive planning workspace is coming in a later milestone.</p></div></li></ol></Panel><Panel title="Simulation workspace" subtitle="No results have been assumed"><Empty title="Start with a real assessment">Voltage, loading and thermal metrics appear only after a successful API simulation.</Empty><a className="text-link panel-link" href="#/assessment">Open assessment <span aria-hidden="true">→</span></a></Panel></div>
    <ModelNote />
  </>;
}
