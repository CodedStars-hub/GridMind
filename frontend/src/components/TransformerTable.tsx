import type { NetworkResponse } from '../types/api';
import { label, number } from '../utils/format';
import { Empty } from './ui';

export function TransformerTable({ network }: { network: NetworkResponse }) {
  if (!network.transformers.length) return <Empty title="No transformers configured">The API returned an empty neighbourhood. No equipment values have been assumed.</Empty>;
  return <div className="table-scroll"><table><caption className="sr-only">Configured neighbourhood transformers and their associated charging sites</caption><thead><tr><th scope="col">Transformer</th><th scope="col">Demand profile</th><th scope="col">Load level</th><th scope="col" className="numeric">Rating</th><th scope="col" className="numeric">Connections</th><th scope="col" className="numeric">Sites</th></tr></thead><tbody>{network.transformers.map(t => <tr key={t.id}><th scope="row"><span className="equipment-id">{t.id}</span><span className="equipment-name">{t.name}</span></th><td>{label(t.archetype)}</td><td><span className="tag">{label(t.load_level)}</span></td><td className="numeric">{number(t.rated_kva)} <span className="unit">kVA</span></td><td className="numeric">{number(t.connections)}</td><td className="numeric">{network.sites.filter(s => s.transformer_id === t.id).length}</td></tr>)}</tbody></table></div>;
}
