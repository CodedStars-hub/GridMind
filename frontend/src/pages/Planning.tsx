import { useData } from '../app/DataProvider';
import { Empty, ErrorState, Loading, ModelNote, PageHeading, Panel } from '../components/ui';
import { number } from '../utils/format';

export function Planning() {
  const { network, refresh } = useData();
  return <><PageHeading eyebrow="INFRASTRUCTURE PLANNING" title="Make room for better decisions.">A foundation for the placement and before/after workspace. No plan has been generated.</PageHeading><Panel title="Planning configuration" subtitle="Values below are configured targets, not feasible hosting capacities.">{network.status === 'loading' ? <Loading /> : network.status === 'error' ? <ErrorState error={network.error} retry={refresh} /> : <div className="planning-config"><span className="small-label">AVAILABLE TARGETS</span><div className="target-list">{network.data.enums.target_kw.map(target => <span className="target-option" key={target}>{number(target)} <small>kW</small>{target === network.data.defaults.target_kw && <span className="tag teal">Default</span>}</span>)}</div><p>Representative month: {network.data.defaults.month.weekday_count} weekdays and {network.data.defaults.month.weekend_count} weekend days, as configured by the API.</p></div>}</Panel><Panel title="Interactive planning is upcoming"><Empty title="Placement comparison will arrive in a later milestone">The backend provides planning calculations. Site selection controls, remedy comparison and interactive before/after views are outside this frontend foundation.</Empty></Panel><ModelNote /></>;
}
