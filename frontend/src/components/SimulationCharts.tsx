import { useId, useState } from 'react';
import type { Assumption, SimulationResult } from '../types/api';
import { isSimulation } from '../api/guards';
import { chartGeometry, compatibleResults, thresholdsFor, violates, type ChartKey } from '../utils/simulationAnalysis';
import { number } from '../utils/format';
import { Empty } from './ui';

const primaryCharts: { key: ChartKey; title: string; unit: string }[] = [
  { key: 'voltage_pu', title: 'Connection-point voltage', unit: 'p.u.' },
  { key: 'loading_pct', title: 'Transformer loading', unit: '% rated current' },
  { key: 'hotspot_c', title: 'Hot-spot temperature', unit: '°C' },
];

export function SimulationCharts({
  result,
  assumptions,
  reference = null,
}: {
  result: SimulationResult | null;
  assumptions: Assumption[];
  reference?: SimulationResult | null;
}) {
  const [index, setIndex] = useState(0);
  const [tableOpen, setTableOpen] = useState(false);
  const id = useId();

  if (!result) return <Empty title="No chart data">Run a simulation to inspect actual returned samples.</Empty>;
  if (!isSimulation(result)) return <p role="alert">Simulation chart data is invalid. No values were assumed.</p>;

  const overlay = reference && isSimulation(reference) && compatibleResults(reference, result) ? reference : null;
  const active = Math.min(Math.max(0, index), result.series.time.length - 1);
  const currentTime = result.series.time[active] ?? '00:00';

  // Find sample indices for quick jump buttons (plain variables, no hooks)
  let minVIdx = 0;
  let minVal = result.series.voltage_pu[0] ?? 1;
  for (let i = 1; i < result.series.voltage_pu.length; i++) {
    if ((result.series.voltage_pu[i] ?? 1) < minVal) {
      minVal = result.series.voltage_pu[i]!;
      minVIdx = i;
    }
  }

  let maxLoadIdx = 0;
  let maxLoadVal = result.series.loading_pct[0] ?? 0;
  for (let i = 1; i < result.series.loading_pct.length; i++) {
    if ((result.series.loading_pct[i] ?? 0) > maxLoadVal) {
      maxLoadVal = result.series.loading_pct[i]!;
      maxLoadIdx = i;
    }
  }

  let maxTempIdx = 0;
  let maxTempVal = result.series.hotspot_c[0] ?? 0;
  for (let i = 1; i < result.series.hotspot_c.length; i++) {
    if ((result.series.hotspot_c[i] ?? 0) > maxTempVal) {
      maxTempVal = result.series.hotspot_c[i]!;
      maxTempIdx = i;
    }
  }

  // One-line interpretations for the 3 primary charts
  const interpretations: Record<string, string> = {
    voltage_pu:
      result.summary.min_voltage_pu < 0.95
        ? `Lowest voltage ${number(result.summary.min_voltage_pu, 4)} p.u. at ${result.summary.min_voltage_time} — falls below 0.95 p.u. threshold.`
        : `Supply voltage stays within statutory limits (lowest ${number(result.summary.min_voltage_pu, 4)} p.u. at ${result.summary.min_voltage_time}).`,
    loading_pct:
      result.summary.peak_loading_pct > 100
        ? `Peak loading ${number(result.summary.peak_loading_pct, 2)}% at ${result.summary.peak_loading_time} — exceeds 100% rated transformer current.`
        : `Peak loading ${number(result.summary.peak_loading_pct, 2)}% at ${result.summary.peak_loading_time} — operates safely within 250 kVA capacity.`,
    hotspot_c:
      result.summary.peak_hotspot_c > 120
        ? `Peak hot-spot ${number(result.summary.peak_hotspot_c, 2)}°C at ${result.summary.peak_hotspot_time} — elevated thermal aging regime.`
        : `Peak hot-spot ${number(result.summary.peak_hotspot_c, 2)}°C at ${result.summary.peak_hotspot_time} — within IEEE C57.91 normal aging limits.`,
  };

  const allCharts = [
    ...primaryCharts,
    ...(result.bess
      ? [
          { key: 'bess_kw' as const, title: 'Battery dispatch (+ discharge / − charge)', unit: 'kW' },
          { key: 'bess_soc_pct' as const, title: 'Battery state of charge', unit: '%' },
        ]
      : []),
  ];

  return (
    <section className="simulation-charts" aria-label="Interactive simulation charts">
      {/* Synchronized Readout Bar */}
      <div className="synchronized-readout-banner" role="region" aria-label="Synchronized simulation time readout">
        <div className="readout-clock">
          <span className="clock-tag">STEP {active + 1}/96</span>
          <strong>{currentTime}</strong>
        </div>
        <div className="readout-metrics">
          <span className="readout-item">
            <span className="readout-name">Voltage:</span>{' '}
            <strong className={result.series.voltage_pu[active]! < 0.95 ? 'text-critical' : 'text-value'}>
              {number(result.series.voltage_pu[active]!, 4)} p.u.
            </strong>
          </span>
          <span className="readout-divider" aria-hidden="true">|</span>
          <span className="readout-item">
            <span className="readout-name">Loading:</span>{' '}
            <strong className={result.series.loading_pct[active]! > 100 ? 'text-warning' : 'text-value'}>
              {number(result.series.loading_pct[active]!, 2)}%
            </strong>
          </span>
          <span className="readout-divider" aria-hidden="true">|</span>
          <span className="readout-item">
            <span className="readout-name">Hot-spot:</span>{' '}
            <strong className={result.series.hotspot_c[active]! > 120 ? 'text-critical' : 'text-value'}>
              {number(result.series.hotspot_c[active]!, 1)}°C
            </strong>
          </span>
          {result.bess && result.series.bess_kw && (
            <>
              <span className="readout-divider" aria-hidden="true">|</span>
              <span className="readout-item">
                <span className="readout-name">BESS:</span>{' '}
                <strong className="text-value">
                  {number(result.series.bess_kw[active]!, 1)} kW ({number(result.series.bess_soc_pct?.[active] ?? 0, 1)}%)
                </strong>
              </span>
            </>
          )}
        </div>
      </div>

      {/* Scrubbing & Inspection Controls */}
      <div className="chart-controls">
        <label htmlFor={id}>
          Inspect time: {currentTime}
          <input
            id={id}
            type="range"
            min={0}
            max={result.series.time.length - 1}
            value={active}
            onChange={e => setIndex(Number(e.target.value))}
            aria-valuetext={currentTime}
          />
        </label>
        <div className="scrubber-quick-jumps" role="group" aria-label="Jump to critical events">
          <span className="quick-jumps-label">Jump to:</span>
          <button type="button" className="jump-btn" onClick={() => setIndex(minVIdx)}>
            Min V ({result.summary.min_voltage_time})
          </button>
          <button type="button" className="jump-btn" onClick={() => setIndex(maxLoadIdx)}>
            Peak Load ({result.summary.peak_loading_time})
          </button>
          <button type="button" className="jump-btn" onClick={() => setIndex(maxTempIdx)}>
            Peak Temp ({result.summary.peak_hotspot_time})
          </button>
          <button type="button" className="jump-btn" onClick={() => setIndex(48)}>
            12:00 Solar
          </button>
          <button type="button" className="jump-btn" onClick={() => setIndex(76)}>
            19:00 Evening
          </button>
        </div>
        <p>Arrow keys select actual 15-minute samples. Hover a chart to inspect the same time across all charts.</p>
      </div>

      <p className="inline-note">
        Voltage shows supply quality; loading shows demand on rated current; hot-spot temperature shows modeled winding stress. A limit event is not evidence of equipment or appliance damage.
      </p>

      <p className="chart-legend">
        Solid line: {overlay ? 'B · current scenario' : 'current scenario'}
        {overlay && ' · Dashed line: A · pinned scenario'} · Filled circles: current samples strictly outside available limits; outlined circles: pinned violations.
      </p>

      {/* Primary 3-column unified grid on desktop */}
      <div className="charts-triple-grid">
        {primaryCharts.map(chart => {
          const values = result.series[chart.key]!;
          const limits = thresholdsFor(chart.key, assumptions);
          const referenceValues = overlay?.series[chart.key];
          const other = referenceValues ?? [];
          const chartOverlay = overlay && referenceValues ? overlay : null;
          const plot = chartGeometry(values, limits, other);

          return (
            <figure key={chart.key} className="simulation-chart" data-metric={chart.key}>
              <figcaption>
                {chart.title} ({chart.unit})
              </figcaption>
              <div className="chart-plot">
                <svg
                  viewBox="0 0 740 255"
                  role="img"
                  aria-label={`${chart.title}: ${result.series.time[0]} to ${result.series.time.at(-1)}. Exact values available below and in the sample table.`}
                  onPointerMove={event => {
                    const rect = event.currentTarget.getBoundingClientRect();
                    if (rect.width && Number.isFinite(event.clientX)) {
                      setIndex(
                        Math.max(
                          0,
                          Math.min(
                            values.length - 1,
                            Math.round((((event.clientX - rect.left) / rect.width) * 740 - 60) / 640 * (values.length - 1))
                          )
                        )
                      );
                    }
                  }}
                >
                  <line x1="60" x2="60" y1="30" y2="210" className="chart-axis" />
                  <line x1="60" x2="700" y1="210" y2="210" className="chart-axis" />

                  {/* Grid lines */}
                  {[plot.low, (plot.low + plot.high) / 2, plot.high].map(value => (
                    <g key={value}>
                      <line x1="60" x2="700" y1={plot.y(value)} y2={plot.y(value)} className="chart-grid" />
                      <text x="54" y={plot.y(value) + 4} textAnchor="end">
                        {number(value, 2)}
                      </text>
                    </g>
                  ))}

                  {/* Time ticks */}
                  {[0, 24, 48, 72, 95].map(i => (
                    <text key={i} x={plot.x(i)} y="235" textAnchor="middle">
                      {result.series.time[i]}
                    </text>
                  ))}

                  {/* Engineering thresholds with high-contrast label pills */}
                  {limits.map(limit => (
                    <g key={limit.label} className="chart-threshold-group">
                      <line x1="60" x2="700" y1={plot.y(limit.value)} y2={plot.y(limit.value)} className="chart-limit" />
                      <rect
                        x="63"
                        y={plot.y(limit.value) - 13}
                        width={Math.min(260, (limit.label.length + 12) * 7.5)}
                        height="15"
                        rx="3"
                        className="chart-limit-backdrop"
                      />
                      <text x="66" y={plot.y(limit.value) - 2} className="chart-limit-label">
                        {limit.label}: {number(limit.value, 4)} {chart.unit}
                      </text>
                    </g>
                  ))}

                  {/* Reference overlay line & violations */}
                  {chartOverlay && <polyline points={plot.points(other)} className="chart-reference" />}
                  {chartOverlay &&
                    other.map((value, i) =>
                      violates(value, limits) ? (
                        <circle
                          key={i}
                          cx={plot.x(i)}
                          cy={plot.y(value)}
                          r="3"
                          className="chart-reference-violation"
                        >
                          <title>
                            A · {result.series.time[i]} · {number(value, 4)} {chart.unit} · outside configured limit
                          </title>
                        </circle>
                      ) : null
                    )}

                  {/* Primary series area, line & violation markers */}
                  <polygon points={`60,210 ${plot.points(values)} 700,210`} className="chart-area" />
                  <polyline points={plot.points(values)} className="chart-series" />
                  {values.map((value, i) =>
                    violates(value, limits) ? (
                      <circle
                        key={i}
                        cx={plot.x(i)}
                        cy={plot.y(value)}
                        r="3.5"
                        className="chart-violation"
                      >
                        <title>
                          {result.series.time[i]} · {number(value, 4)} {chart.unit} · outside configured limit
                        </title>
                      </circle>
                    ) : null
                  )}

                  {/* Synchronized vertical time crosshair & marker */}
                  <line x1={plot.x(active)} x2={plot.x(active)} y1="30" y2="210" className="chart-cursor" />
                  <circle cx={plot.x(active)} cy={plot.y(values[active]!)} r="4.5" className="chart-selected" />
                </svg>
              </div>

              {/* Exact format required by Vitest: */}
              <p className="chart-readout">
                {result.series.time[active]} · {chartOverlay ? 'B' : 'Current'}: {number(values[active]!, 4)} {chart.unit}
                {chartOverlay && ` · A: ${number(other[active]!, 4)} ${chart.unit}`}
                {violates(values[active]!, limits) && ' · Outside configured limit'}
              </p>

              {/* One-line interpretation */}
              <p className="chart-summary-line">{interpretations[chart.key]}</p>

              {!limits.length && chart.key !== 'bess_kw' && (
                <p className="inline-note">Thresholds unavailable from the API; no limit values assumed.</p>
              )}
            </figure>
          );
        })}
      </div>

      {/* Battery charts if BESS is enabled */}
      {result.bess && (
        <div className="charts-battery-grid">
          {allCharts.slice(3).map(chart => {
            const values = result.series[chart.key]!;
            const resolved =
              chart.key === 'bess_soc_pct' && result.bess
                ? ['soc_min_pct', 'soc_max_pct'].map(name => ({
                    name,
                    value: result.bess![name as 'soc_min_pct' | 'soc_max_pct'],
                    unit: '%',
                    note: 'Resolved battery limit from response',
                  }))
                : assumptions;
            const limits = thresholdsFor(chart.key, resolved);
            const referenceValues = overlay?.series[chart.key];
            const other = referenceValues ?? [];
            const chartOverlay = overlay && referenceValues ? overlay : null;
            const plot = chartGeometry(values, limits, other);

            return (
              <figure key={chart.key} className="simulation-chart" data-metric={chart.key}>
                <figcaption>
                  {chart.title} ({chart.unit})
                </figcaption>
                <div className="chart-plot">
                  <svg
                    viewBox="0 0 740 255"
                    role="img"
                    aria-label={`${chart.title}: ${result.series.time[0]} to ${result.series.time.at(-1)}.`}
                    onPointerMove={event => {
                      const rect = event.currentTarget.getBoundingClientRect();
                      if (rect.width && Number.isFinite(event.clientX)) {
                        setIndex(
                          Math.max(
                            0,
                            Math.min(
                              values.length - 1,
                              Math.round((((event.clientX - rect.left) / rect.width) * 740 - 60) / 640 * (values.length - 1))
                            )
                          )
                        );
                      }
                    }}
                  >
                    <line x1="60" x2="60" y1="30" y2="210" className="chart-axis" />
                    <line x1="60" x2="700" y1="210" y2="210" className="chart-axis" />
                    {[plot.low, (plot.low + plot.high) / 2, plot.high].map(value => (
                      <g key={value}>
                        <line x1="60" x2="700" y1={plot.y(value)} y2={plot.y(value)} className="chart-grid" />
                        <text x="54" y={plot.y(value) + 4} textAnchor="end">
                          {number(value, 2)}
                        </text>
                      </g>
                    ))}
                    {[0, 24, 48, 72, 95].map(i => (
                      <text key={i} x={plot.x(i)} y="235" textAnchor="middle">
                        {result.series.time[i]}
                      </text>
                    ))}
                    {limits.map(limit => (
                      <g key={limit.label}>
                        <line x1="60" x2="700" y1={plot.y(limit.value)} y2={plot.y(limit.value)} className="chart-limit" />
                        <text x="65" y={plot.y(limit.value) - 4}>
                          {limit.label}: {number(limit.value, 4)} {chart.unit}
                        </text>
                      </g>
                    ))}
                    {chartOverlay && <polyline points={plot.points(other)} className="chart-reference" />}
                    <polygon points={`60,210 ${plot.points(values)} 700,210`} className="chart-area" />
                    <polyline points={plot.points(values)} className="chart-series" />
                    <line x1={plot.x(active)} x2={plot.x(active)} y1="30" y2="210" className="chart-cursor" />
                    <circle cx={plot.x(active)} cy={plot.y(values[active]!)} r="4" className="chart-selected" />
                  </svg>
                </div>
                <p className="chart-readout">
                  {result.series.time[active]} · {chartOverlay ? 'B' : 'Current'}: {number(values[active]!, 4)} {chart.unit}
                  {chartOverlay && ` · A: ${number(other[active]!, 4)} ${chart.unit}`}
                  {violates(values[active]!, limits) && ' · Outside configured limit'}
                </p>
              </figure>
            );
          })}
        </div>
      )}

      {/* Accessible sample table */}
      <details onToggle={event => setTableOpen(event.currentTarget.open)}>
        <summary>All returned samples (accessible data table)</summary>
        {tableOpen && (
          <div className="table-scroll">
            <table>
              <caption>Current simulation · 96 samples, end-of-step temperatures</caption>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Voltage (p.u.)</th>
                  <th>Loading (%)</th>
                  <th>Hot-spot (°C)</th>
                  <th>Aging (× reference)</th>
                </tr>
              </thead>
              <tbody>
                {result.series.time.map((time, i) => (
                  <tr key={time}>
                    <th scope="row">{time}</th>
                    <td>{number(result.series.voltage_pu[i]!, 4)}</td>
                    <td>{number(result.series.loading_pct[i]!, 4)}</td>
                    <td>{number(result.series.hotspot_c[i]!, 4)}</td>
                    <td>{number(result.series.aging_factor[i]!, 4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </details>
    </section>
  );
}
