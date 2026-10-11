import type { BatteryConfig } from '../types/api';
import { Icon } from './Icon';
export type BatteryFields = Partial<Record<keyof BatteryConfig, string>>;
export function BatteryControls({ enabled, setEnabled, fields, setFields, pending }: { enabled: boolean; setEnabled: (value: boolean) => void; fields: BatteryFields; setFields: (value: BatteryFields) => void; pending: boolean }) {
  const fieldsList: { key: keyof BatteryConfig; label: string; help: string; required?: boolean }[] = [
    { key: 'energy_kwh', label: 'Battery energy capacity (kWh)', help: 'How much energy the battery can store.', required: true },
    { key: 'power_kw', label: 'Battery power limit (kW)', help: 'How fast it can charge or discharge.', required: true },
    { key: 'initial_soc_pct', label: 'Initial SOC (%)', help: 'How full the battery is at the start.', required: true },
    { key: 'soc_min_pct', label: 'Minimum SOC (%)', help: 'Lower operating bound.' }, { key: 'soc_max_pct', label: 'Maximum SOC (%)', help: 'Upper operating bound.' },
    { key: 'charge_efficiency', label: 'Charging efficiency (ratio)', help: 'Stored energy / grid energy.' }, { key: 'discharge_efficiency', label: 'Discharging efficiency (ratio)', help: 'Grid energy / stored energy.' },
  ];
  const inputs = (list: typeof fieldsList) => <div className="scenario-grid">{list.map(field => <label key={field.key}>{field.label}<input aria-label={field.label} type="number" step="any" required={field.required} value={fields[field.key] ?? ''} placeholder={field.required ? 'Enter value' : 'Backend default'} onChange={event => setFields({ ...fields, [field.key]: event.target.value })} /><small>{field.help}</small></label>)}</div>;
  return <fieldset disabled={pending} className="battery-controls"><legend>Optional Battery Storage</legend>
    <div className="battery-summary"><Icon name="battery" /><label><input type="checkbox" checked={enabled} onChange={event => setEnabled(event.target.checked)} /> Enable battery storage</label><strong>Try a peak-shaving alternative</strong></div>
    {enabled && <><p>The battery shifts grid demand within power, energy and SOC constraints. Fixed-size simulation, not automatic sizing. Newer features may require the local backend until AWS is updated.</p>{inputs(fieldsList.filter(field => field.required))}<details><summary>Advanced operating limits & efficiencies</summary>{inputs(fieldsList.filter(field => !field.required))}<p>Blank advanced fields use configured defaults. SOC means state of charge; efficiencies include conversion losses.</p></details></>}
  </fieldset>;
}
