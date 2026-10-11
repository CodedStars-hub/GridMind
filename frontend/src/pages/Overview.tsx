import { useState } from 'react';
import { useData } from '../app/DataProvider';
import { Empty, ErrorState, Loading, Metric, ModelNote, Panel } from '../components/ui';
import { TransformerTable } from '../components/TransformerTable';
import { Icon } from '../components/Icon';
import { number } from '../utils/format';

type CollisionPhase = 'noon' | 'peak' | 'night';

export function Overview() {
  const { health, network, refresh } = useData();
  const [inventoryOpen, setInventoryOpen] = useState(false);
  const [phase, setPhase] = useState<CollisionPhase>('peak');

  const collisionData = {
    noon: {
      time: '12:00 PM',
      label: 'Daylight Solar Balance',
      tag: 'Balanced Grid',
      tagClass: 'emerald',
      solarPct: 88,
      solarText: 'Peak daylight generation (30 kWp)',
      evPct: 20,
      evText: 'Minimal baseline charging',
      stressPct: 35,
      stressState: 'Optimal (Cool & Stable)',
      stressClass: 'emerald',
      summary: 'Strong rooftop solar generation absorbs local demand. Voltage remains near 1.0 p.u. and transformer winding temperature remains well below nameplate limits.',
    },
    peak: {
      time: '07:00 PM',
      label: 'The 7:00 PM Grid Collision',
      tag: 'Critical Overload',
      tagClass: 'critical',
      solarPct: 0,
      solarText: 'Zero output (Sun has set)',
      evPct: 95,
      evText: 'Surge: Commuters fast-charging simultaneously',
      stressPct: 98,
      stressState: 'Severe Stress (110°C+ Hot-spot & Voltage Droop)',
      stressClass: 'critical',
      summary: 'The critical grid bottleneck: Solar generation drops to zero exactly when EV charging surges and residential cooking/cooling peaks. Winding hot-spot accelerates insulation aging exponentially (IEEE C57.91).',
    },
    night: {
      time: '11:00 PM',
      label: 'Off-Peak Storage & Managed Relief',
      tag: 'Relieved & Buffered',
      tagClass: 'teal',
      solarPct: 0,
      solarText: 'Zero output (Night)',
      evPct: 45,
      evText: 'Managed: Battery peak-shaving & shifted charge',
      stressPct: 40,
      stressState: 'Stabilized (Protected Asset)',
      stressClass: 'teal',
      summary: 'A localized battery buffer (BESS) or managed charging schedule shaves the evening surge. The transformer operates within safe limits, avoiding an expensive ₹5-7 Lakh physical replacement.',
    },
  };

  const currentPhase = collisionData[phase];

  return (
    <>
      {/* 1. Narrative Hero Header */}
      <section className="overview-hero">
        <div className="hero-story">
          <p className="eyebrow">
            <span className="status-dot" aria-hidden="true" /> EV CHARGING · GRID INTELLIGENCE
          </p>
          <h1>
            More charging.<br />
            <span>A grid that can handle it.</span>
          </h1>
          <p>
            Distribution transformers were sized decades before EV fast-charging. GridMind simulates 
            24-hour thermal degradation and feeder voltage drops so utilities and developers can plan with confidence.
          </p>
          <div className="hero-actions">
            <a href="#/assessment" className="button">
              Run a simulation <Icon name="arrow" />
            </a>
            <a href="#/network" className="button secondary">
              Explore Network
            </a>
          </div>
          <div className="hero-footnote">
            <Icon name="chart" />
            <span>One shared engineering engine · Transparent IEEE C57.91 physics</span>
          </div>
        </div>

        {/* Hero Network Asset Snapshot Card */}
        <div className="hero-network">
          <div className="preview-heading">
            <div>
              <span className="small-label">NEIGHBOURHOOD INVENTORY</span>
              <h3 style={{ marginTop: '4px' }}>Configured Distribution Assets</h3>
            </div>
            <span className="tag info">Conceptual inventory</span>
          </div>

          {network.status === 'loading' ? (
            <Loading message="Loading neighbourhood configuration…" />
          ) : network.status === 'error' ? (
            <Empty title="Preview unavailable">
              Connect to the API to explore configured assets. No network data is assumed.
            </Empty>
          ) : !network.data.transformers.length ? (
            <Empty title="No transformers configured">
              The API returned an empty inventory.
            </Empty>
          ) : (
            <div className="preview-assets">
              {network.data.transformers.map(t => (
                <a
                  href={`#/network?transformer=${encodeURIComponent(t.id)}`}
                  className="preview-asset"
                  key={t.id}
                  aria-label={`Explore ${t.id}: ${t.name}`}
                >
                  <div>
                    <span className="equipment-id">{t.id}</span>
                    <Icon name="bolt" />
                  </div>
                  <strong>{t.name}</strong>
                  <span>
                    {number(t.rated_kva)} <small>kVA</small>
                  </span>
                  <p>{network.data.sites.filter(s => s.transformer_id === t.id).length} candidate sites</p>
                </a>
              ))}
            </div>
          )}
          <p className="preview-note">
            Configured assets · no physical feeder topology or live telemetry implied.
          </p>
        </div>
      </section>

      {health.status === 'error' && <ErrorState error={health.error} retry={refresh} />}
      {network.status === 'error' && <ErrorState error={network.error} retry={refresh} />}

      {/* 2. The 7:00 PM Grid Collision Interactive Exhibit */}
      <section className="collision-exhibit" aria-label="Interactive 7:00 PM Grid Collision Exhibit">
        <div className="collision-header">
          <div>
            <span className="small-label" style={{ color: 'var(--accent-orange)' }}>
              THE CORE INFRASTRUCTURE BOTTLENECK
            </span>
            <h2>The 7:00 PM Grid Collision</h2>
            <p>
              Why distribution transformers fail: EV charging spikes precisely as solar PV production ceases.
              Explore how time-of-day dynamics stress the grid:
            </p>
          </div>

          <div className="time-tabs" role="tablist" aria-label="Select time of day">
            <button
              type="button"
              role="tab"
              aria-selected={phase === 'noon'}
              className={`time-tab ${phase === 'noon' ? 'active' : ''}`}
              data-phase="noon"
              onClick={() => setPhase('noon')}
            >
              12:00 PM · Solar Peak
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={phase === 'peak'}
              className={`time-tab ${phase === 'peak' ? 'active' : ''}`}
              data-phase="peak"
              onClick={() => setPhase('peak')}
            >
              07:00 PM · Evening Collision
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={phase === 'night'}
              className={`time-tab ${phase === 'night' ? 'active' : ''}`}
              data-phase="night"
              onClick={() => setPhase('night')}
            >
              11:00 PM · Storage Relief
            </button>
          </div>
        </div>

        {/* 3 Energy Streams */}
        <div className="collision-canvas">
          {/* Stream 1: Rooftop Solar */}
          <div className={`stream-card ${phase === 'noon' ? 'highlight' : ''}`}>
            <div className="stream-card-header">
              <strong>☀️ Rooftop Solar PV</strong>
              <span className={`tag ${phase === 'noon' ? 'emerald' : 'info'}`}>
                {phase === 'noon' ? 'Generating' : 'Dormant'}
              </span>
            </div>
            <div className="stream-value" style={{ color: 'var(--accent-gold)' }}>
              {phase === 'noon' ? 'High Output' : '0 kW'}
            </div>
            <div className="stream-bar-rail">
              <div 
                className="stream-bar-fill" 
                style={{ width: `${currentPhase.solarPct}%`, background: 'var(--accent-gold)' }} 
              />
            </div>
            <p className="stream-note">{currentPhase.solarText}</p>
          </div>

          {/* Stream 2: EV Hub Demand */}
          <div className={`stream-card ${phase === 'peak' ? 'highlight' : ''}`}>
            <div className="stream-card-header">
              <strong>⚡ EV Charging Hub</strong>
              <span className={`tag ${phase === 'peak' ? 'critical' : phase === 'night' ? 'teal' : 'info'}`}>
                {phase === 'peak' ? 'Peak Surge' : phase === 'night' ? 'Shifted' : 'Low Demand'}
              </span>
            </div>
            <div className="stream-value" style={{ color: 'var(--accent-orange)' }}>
              {phase === 'peak' ? 'Peak Spike' : phase === 'night' ? 'Buffered' : 'Light Load'}
            </div>
            <div className="stream-bar-rail">
              <div 
                className="stream-bar-fill" 
                style={{ width: `${currentPhase.evPct}%`, background: 'var(--accent-orange)' }} 
              />
            </div>
            <p className="stream-note">{currentPhase.evText}</p>
          </div>

          {/* Stream 3: Transformer Thermal & Voltage State */}
          <div className={`stream-card ${phase === 'peak' ? 'highlight' : ''}`}>
            <div className="stream-card-header">
              <strong>🛡️ Transformer State</strong>
              <span className={`tag ${currentPhase.tagClass}`}>
                {currentPhase.tag}
              </span>
            </div>
            <div className="stream-value" style={{ color: phase === 'peak' ? 'var(--accent-ruby)' : 'var(--accent-emerald)' }}>
              {currentPhase.stressState.split(' ')[0]}
            </div>
            <div className="stream-bar-rail">
              <div 
                className="stream-bar-fill" 
                style={{ 
                  width: `${currentPhase.stressPct}%`, 
                  background: phase === 'peak' ? 'var(--accent-ruby)' : 'var(--accent-emerald)' 
                }} 
              />
            </div>
            <p className="stream-note">{currentPhase.stressState}</p>
          </div>
        </div>

        {/* Plain-English Physics Callout */}
        <div className="collision-verdict">
          <div className="collision-verdict-text">
            <span 
              className="collision-verdict-icon" 
              style={{ 
                background: phase === 'peak' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                color: phase === 'peak' ? 'var(--accent-ruby)' : 'var(--accent-emerald)'
              }}
            >
              {phase === 'peak' ? '⚠️' : '✓'}
            </span>
            <div>
              <h4>{currentPhase.label}: {currentPhase.time}</h4>
              <p>{currentPhase.summary}</p>
            </div>
          </div>
          <a href="#/assessment" className="button secondary" style={{ whiteSpace: 'nowrap' }}>
            Simulate this condition →
          </a>
        </div>
      </section>

      {/* 3. One-Click Quick Scenario Launchpads */}
      <section className="scenario-launchpads" aria-label="Quick Scenario Launchpads">
        <div className="section-label">
          <div>
            <span className="small-label">ENGINEERING ENTRY POINTS</span>
            <h2>Test Common Utility Scenarios</h2>
          </div>
          <span className="tag teal">One-click presets</span>
        </div>

        <div className="scenario-cards">
          {/* Card 1: Evening Rush */}
          <article className="launchpad-card">
            <header>
              <span className="equipment-id">SCENARIO · 01</span>
              <span className="tag critical">High Stress</span>
            </header>
            <h3>Evening Peak Rush</h3>
            <p>
              Simulate high EV charging demand colliding with residential evening cooking and cooling. 
              Observe severe voltage droop below 0.95 p.u. and winding temperatures over 110°C.
            </p>
            <div className="launchpad-specs">
              <span>50 kW EV Hub</span>
              <span>Heavy Load</span>
              <span>Summer Weekday</span>
            </div>
            <a href="#/assessment" className="button">
              Run Evening Scenario <Icon name="arrow" />
            </a>
          </article>

          {/* Card 2: Solar Buffering */}
          <article className="launchpad-card">
            <header>
              <span className="equipment-id">SCENARIO · 02</span>
              <span className="tag emerald">Balanced</span>
            </header>
            <h3>Solar-Buffered Day</h3>
            <p>
              Evaluate whether 30 kWp rooftop solar can absorb daytime fleet charging without 
              triggering thermal rise or feeder degradation.
            </p>
            <div className="launchpad-specs">
              <span>30 kW EV Hub</span>
              <span>30 kWp Solar</span>
              <span>Summer Weekday</span>
            </div>
            <a href="#/assessment" className="button secondary">
              Run Solar Scenario <Icon name="arrow" />
            </a>
          </article>

          {/* Card 3: Neighborhood Siting */}
          <article className="launchpad-card">
            <header>
              <span className="equipment-id">PLANNER · 03</span>
              <span className="tag teal">Multi-Site</span>
            </header>
            <h3>Neighborhood Siting Plan</h3>
            <p>
              Evaluate how the allocation algorithm distributes a 150 kW target across 
              competing neighborhood sites while enforcing individual transformer limits.
            </p>
            <div className="launchpad-specs">
              <span>150 kW Target</span>
              <span>Managed Charging</span>
              <span>4 Transformers</span>
            </div>
            <a href="#/planning" className="button secondary">
              Open Placement Plan <Icon name="arrow" />
            </a>
          </article>
        </div>
      </section>

      {/* 4. Four-Step Interactive Journey Strip */}
      <div className="journey-strip" aria-label="How GridMind works">
        {[
          { n: '01', name: 'Understand', text: 'Explore assets, feeders & load levels', icon: 'grid' as const },
          { n: '02', name: 'Simulate', text: 'Run 96-step (24h) power flow & thermal model', icon: 'chart' as const },
          { n: '03', name: 'Compare', text: 'Identify voltage sags & hot-spot violations', icon: 'bolt' as const },
          { n: '04', name: 'Intervene', text: 'Evaluate battery storage (BESS) or managed caps', icon: 'battery' as const },
        ].map(step => (
          <div key={step.n}>
            <span>{step.n}</span>
            <Icon name={step.icon} />
            <div>
              <strong>{step.name}</strong>
              <p>{step.text}</p>
            </div>
          </div>
        ))}
      </div>

      {/* 5. Connected Neighborhood Metrics & Equipment Inventory */}
      {network.status === 'success' && (
        <>
          <div className="section-label">
            <div>
              <span className="small-label">YOUR NEIGHBOURHOOD</span>
              <h2>{network.data.neighbourhood.name}</h2>
            </div>
            <span className="tag">
              {network.data.meta.source === 'live' ? 'API configuration' : 'Cached configuration'}
            </span>
          </div>

          <div className="metric-grid">
            <Metric 
              label="Transformers" 
              value={number(network.data.transformers.length)} 
              description="Independent modeled branches" 
            />
            <Metric 
              label="Candidate sites" 
              value={number(network.data.sites.length)} 
              description="Configured charging opportunities" 
            />
            <Metric 
              label="Nameplate capacity" 
              value={number(network.data.transformers.reduce((sum, t) => sum + t.rated_kva, 0))} 
              unit="kVA" 
              description="Sum of ratings · not available headroom" 
            />
            <Metric 
              label="Customer connections" 
              value={number(network.data.transformers.reduce((sum, t) => sum + t.connections, 0))} 
              description="Configured connections · not damaged homes" 
            />
          </div>

          <details 
            className="panel inventory-details" 
            onToggle={event => setInventoryOpen(event.currentTarget.open)}
          >
            <summary>
              Transformer inventory <span>View equipment configuration</span>
            </summary>
            {inventoryOpen && <TransformerTable network={network.data} />}
          </details>
        </>
      )}

      {/* 6. Capability Navigation Grid */}
      <div className="capability-grid">
        <Panel title="Simulation studio" subtitle="No results have been assumed">
          <div className="capability-icon">
            <Icon name="chart" />
          </div>
          <p>
            Explore the whole day, not just peak demand. Inspect connection voltage, loading current and 
            hot-spot temperatures, then compare battery storage peak-shaving.
          </p>
          <a className="text-link panel-link" href="#/assessment">
            Open assessment studio <Icon name="arrow" />
          </a>
        </Panel>

        <Panel title="Network explorer" subtitle="Infrastructure, in context">
          <div className="capability-icon">
            <Icon name="grid" />
          </div>
          <p>
            Select a transformer or candidate site to understand nameplate ratings, 
            configured baseline profiles, and attached customer connections.
          </p>
          <a className="text-link panel-link" href="#/network">
            Explore the neighbourhood <Icon name="arrow" />
          </a>
        </Panel>

        <Panel title="Placement planning" subtitle="Decisions under constraints">
          <div className="capability-icon">
            <Icon name="plan" />
          </div>
          <p>
            Run the placement optimizer to see demand allocations, electrical boundary constraints, 
            and trade-offs against uncontrolled charging installation.
          </p>
          <a className="text-link panel-link" href="#/planning">
            Open planning workspace <Icon name="arrow" />
          </a>
        </Panel>
      </div>

      <ModelNote />
    </>
  );
}
