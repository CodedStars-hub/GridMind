"""Independent allocation examples and the complete six-transformer workflow."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from gridmind_engine import planner_allocation
from gridmind_engine.hosting_feasibility import DAYS, check_operating_series
from gridmind_engine.impact import _present, compare_network_impacts
from gridmind_engine.network import assess_network_with_precision, transformer_load_series
from gridmind_engine.planner import plan_charging, unplanned_allocation
from gridmind_engine.planner_allocation import allocate_sites, entry, evaluate_allocation
from gridmind_engine.planner_comparison import before_after_electrical, scenario_metrics
from gridmind_engine.planner_sites import planning_sites, validate_plan_request
from gridmind_engine.profiles import load_config_dir
from gridmind_engine.validate import InvalidInputError

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def config():
    return load_config_dir(ROOT / 'config')


def value(config, key, new):
    config['neighbourhood']['parameters'][key]['value'] = new


def candidate(identity='A', requested=30, transformer='T1', eligible=True):
    return dict(site_id=identity, name=identity, transformer_id=transformer,
                requested_kw=requested, eligible=eligible, score=1,
                score_components=dict(footfall=10, normalized_footfall=1, footfall_weight=1))


def headroom(feasible=True):
    return {'T1': {'baseline': {'feasible': feasible, 'violations': [] if feasible else
                               [dict(scenario='summer_weekday', constraint='voltage_min_pu')]}}}


def checked(feasible, keys=('loading_info_pct',), energy=100):
    return dict(feasible=feasible,
                violations=[] if feasible else [dict(scenario=d, constraint=k) for d in DAYS for k in keys],
                days={d: dict(served_energy_kwh=energy) for d in DAYS})


def analytical_series(voltage=1, loading=50, hotspot=60):
    return dict(time=[f'{i // 4:02d}:{i % 4 * 15:02d}' for i in range(96)],
                voltage_pu=[voltage] * 96, loading_pct=[loading] * 96, hotspot_c=[hotspot] * 96)


def test_rank_score_and_stable_ties(config):
    before = deepcopy(config)
    ranked = planning_sites(config)
    assert [s['site_id'] for s in ranked] == ['S1', 'S2', 'S4', 'S3', 'S5', 'S6', 'S7']
    assert ranked[0]['score'] == 1 and ranked[1]['score'] == .9
    assert all(s['requested_kw'] > 0 and s['eligible'] for s in ranked)
    assert config == before
    sites = config['neighbourhood']['parameters']['sites']['value']
    sites[1]['footfall_score'] = 10
    sites.reverse()
    assert [s['site_id'] for s in planning_sites(config)][:2] == ['S1', 'S2']
    value(config, 'planner_score_weights', {'footfall': 2})
    assert planning_sites(config)[0]['score'] == 2


@pytest.mark.parametrize('weights', [{}, {'other': 1}, {'footfall': 0}, {'footfall': -1},
                                    {'footfall': float('nan')}, {'footfall': float('inf')}, {'footfall': True}])
def test_invalid_weights(config, weights):
    value(config, 'planner_score_weights', weights)
    with pytest.raises(ValueError, match='planner_score_weights'):
        planning_sites(config)


@pytest.mark.parametrize('field,new', [
    ('transformer_id', 'unknown'), ('id', 'T1'), ('requested_kw', -10),
    ('requested_kw', float('nan')), ('requested_kw', float('inf')), ('requested_kw', True),
    ('requested_kw', 5), ('requested_kw', 160), ('max_kw', -10), ('max_kw', 15),
    ('max_kw', float('inf')), ('footfall_score', -1), ('footfall_score', 11),
    ('footfall_score', float('nan')), ('eligible', 'yes'), ('name', ''),
])
def test_invalid_site_configuration(config, field, new):
    config['neighbourhood']['parameters']['sites']['value'][0][field] = new
    with pytest.raises(ValueError):
        planning_sites(config)


def test_duplicate_site_is_rejected(config):
    sites = config['neighbourhood']['parameters']['sites']['value']
    sites[1]['id'] = sites[0]['id']
    with pytest.raises(ValueError, match='id'):
        planning_sites(config)


@pytest.mark.parametrize('payload,field', [([], 'payload'), ({}, 'target_kw'),
    ({'target_kw': 20}, 'target_kw'), ({'target_kw': 300.0}, 'target_kw'),
    ({'target_kw': True}, 'target_kw'), ({'target_kw': -10}, 'target_kw'),
    ({'target_kw': 300, 'budget': 1000}, 'budget')])
def test_plan_request_gate(config, payload, field):
    with pytest.raises(InvalidInputError) as exc:
        validate_plan_request(payload, config)
    assert exc.value.field == field


def test_target_comes_from_config(config):
    value(config, 'target_kw_options', [0, 10])
    assert validate_plan_request({'target_kw': 10}, config) == 10
    assert validate_plan_request({'target_kw': 0}, config) == 0
    with pytest.raises(InvalidInputError):
        validate_plan_request({'target_kw': 300}, config)


@pytest.mark.parametrize('options', [[], [10, 10], [15], [float('nan')], [True], [[]]])
def test_invalid_target_options(config, options):
    value(config, 'target_kw_options', options)
    with pytest.raises(ValueError, match='target_kw_options'):
        validate_plan_request({'target_kw': 300}, config)


def test_shared_headroom_partial_allocation(config):
    visited = []
    def evaluate(identity, allocation):
        assert identity == 'T1'
        total = sum(e['kw'] for e in allocation)
        visited.append(total)
        return checked(total <= 40)
    result = allocate_sites([candidate('A'), candidate('B')], 60, headroom(), config, evaluate)
    assert result['allocation'] == [entry('A', 30), entry('B', 10)]
    assert result['unplaced_kw'] == 20
    assert result['sites'][0]['status'] == 'selected'
    assert result['sites'][1]['status'] == 'partial'
    assert result['sites'][1]['unserved_kw'] == 20
    assert result['sites'][1]['reason_code'] == 'electrical_constraint'
    assert any(v['constraint'] == 'loading_info_pct' for v in result['sites'][1]['limiting_constraints'])
    assert max(visited) == 60
    assert all(e['kw'] % 10 == 0 for e in result['allocation'])


@pytest.mark.parametrize('threshold,expected,status', [(0, 0, 'rejected'), (20, 20, 'partial'), (30, 30, 'selected')])
def test_single_site_capacity(config, threshold, expected, status):
    result = allocate_sites([candidate()], 30, headroom(), config,
                            lambda _, entries: checked(sum(e['kw'] for e in entries) <= threshold))
    assert sum(e['kw'] for e in result['allocation']) == expected
    assert result['sites'][0]['status'] == status
    assert result['unplaced_kw'] == 30 - expected


def test_target_budget_partial_and_rejected(config):
    result = allocate_sites([candidate('A'), candidate('B')], 10, headroom(), config,
                            lambda *_: checked(True))
    assert result['allocation'] == [entry('A', 10)]
    assert [s['status'] for s in result['sites']] == ['partial', 'rejected']
    assert all(s['reason_code'] == 'target_budget_exhausted' for s in result['sites'])


@pytest.mark.parametrize('site,hosting,reason', [
    (candidate(eligible=False), headroom(), 'site_ineligible'),
    (candidate(requested=0), headroom(), 'zero_demand'),
    (candidate(), headroom(False), 'baseline_violation'),
])
def test_skipped_candidates_never_simulated(config, site, hosting, reason):
    def forbidden(*_):
        pytest.fail('Ineligible candidate must not be evaluated')
    result = allocate_sites([site], 30, hosting, config, forbidden)
    assert result['allocation'] == [] and result['evaluations'] == 0
    assert result['sites'][0]['reason_code'] == reason
    assert result['sites'][0]['electrically_eligible'] == hosting['T1']['baseline']['feasible']


def test_zero_budget_does_not_allocate(config):
    result = allocate_sites([candidate()], 0, headroom(), config, lambda *_: pytest.fail('no budget'))
    assert result['allocation'] == [] and result['unplaced_kw'] == 0


def test_grid_search_does_not_assume_monotonicity(config):
    result = allocate_sites([candidate()], 30, headroom(), config,
                            lambda _, entries: checked(entries[-1]['kw'] in (10, 30)))
    assert result['allocation'] == [entry('A', 30)]
    assert result['evaluations'] == 15


def test_managed_mode_only_when_needed_and_cheapest(config):
    def evaluate(_, entries):
        last = entries[-1]
        # Uncontrolled supports 10 kW; managed supports 30 kW.
        return checked(last['managed'] or last['kw'] <= 10, energy=last['cap_fraction'] or 1)
    result = allocate_sites([candidate()], 30, headroom(), config, evaluate)
    assert result['allocation'] == [entry('A', 30, .8)]
    assert result['sites'][0]['managed']
    assert result['sites'][0]['alternatives'][0]['feasible'] is False


@pytest.mark.parametrize('budget', [0, -1, 1, 14, True, 15.0, float('nan'), float('inf')])
def test_invalid_evaluation_budget(config, budget):
    value(config, 'planner_max_evaluations', budget)
    with pytest.raises(ValueError, match='planner_max_evaluations'):
        allocate_sites([candidate()], 30, headroom(), config, lambda *_: checked(True))


@pytest.mark.parametrize('limit,expected', [
    ('voltage_min_pu', {'voltage_min_pu'}), ('loading_info_pct', {'loading_info_pct'}),
    ('hotspot_warning_c', {'hotspot_warning_c'}),
    ('multiple', {'voltage_min_pu', 'loading_info_pct', 'hotspot_warning_c'}),
])
def test_analytical_electrical_limits_and_equality(config, limit, expected):
    def evaluate(_, entries):
        kw = sum(e['kw'] for e in entries)
        # At 10 kW: exactly .95 p.u., 100% current and/or 110 C; 20 kW violates.
        raw = analytical_series(voltage=1 - kw / 200 if limit in ('voltage_min_pu', 'multiple') else 1,
                                loading=90 + kw if limit in ('loading_info_pct', 'multiple') else 50,
                                hotspot=100 + kw if limit in ('hotspot_warning_c', 'multiple') else 60)
        check = check_operating_series(raw, config)
        return checked(not check['violations'], check['violations'])
    result = allocate_sites([candidate()], 30, headroom(), config, evaluate)
    assert result['allocation'] == [entry('A', 10)]
    assert {v['constraint'] for v in result['sites'][0]['limiting_constraints']} == expected


def test_precision_not_display_rounding(config):
    def evaluate(_, entries):
        raw = analytical_series(voltage=.95000001 if entries[-1]['kw'] == 10 else .94999999)
        check = check_operating_series(raw, config)
        return checked(not check['violations'], check['violations'])
    assert allocate_sites([candidate()], 30, headroom(), config, evaluate)['allocation'] == [entry('A', 10)]


def test_combined_profile_uses_own_transformer_and_shared_engine(config, monkeypatch):
    transformers = config['neighbourhood']['parameters']['transformers']['value']
    sites = config['neighbourhood']['parameters']['sites']['value']
    t3 = transformers[2]
    calls = []
    original = planner_allocation.simulate_load_series_with_precision
    def capture(loads, cfg, echo):
        calls.append(loads)
        return original(loads, cfg, echo)
    monkeypatch.setattr(planner_allocation, 'simulate_load_series_with_precision', capture)
    result = evaluate_allocation(t3, [entry('S2', 20), entry('S3', 10), entry('S1', 100)], sites, config)
    assert len(calls) == 2
    assert calls[0].ev_kw[60] == 30
    assert calls[0].ev_kw[0] == pytest.approx(.6, abs=1e-12)
    assert max(calls[1].ev_kw) == 30
    assert len(calls[0].time) == 96 and calls[0].time[-1] == '23:45'
    # Commercial weekday peak at 13:00: .70 * 250 = 175 kW.
    assert calls[0].base_kw[52] == 175
    assert result['days']['summer_weekday']['additional_peak_kw'] == 30


def test_managed_energy_floor_uses_per_site_requested_energy(config):
    value(config, 'managed_cap_fractions', [.5])
    for day in DAYS:
        config['ev_daytime_profile']['parameters'][day]['value'] = [1] * 96
    transformers = config['neighbourhood']['parameters']['transformers']['value']
    sites = config['neighbourhood']['parameters']['sites']['value']
    checked_result = evaluate_allocation(transformers[3], [entry('S1', 10, .5)], sites, config)
    assert not checked_result['feasible']
    assert checked_result['days']['summer_weekday']['served_energy_pct']['S1'] == 50
    assert checked_result['days']['summer_weekday']['served_energy_kwh'] == 120
    assert all(v['constraint'] == 'min_served_energy_pct_for_managed' for v in checked_result['violations'])


def test_operating_solver_failure_is_infeasible(config, monkeypatch):
    from gridmind_engine.powerflow import PowerFlowError
    def fail(*_):
        raise PowerFlowError('test collapse')
    monkeypatch.setattr(planner_allocation, 'simulate_load_series_with_precision', fail)
    transformers = config['neighbourhood']['parameters']['transformers']['value']
    sites = config['neighbourhood']['parameters']['sites']['value']
    result = evaluate_allocation(transformers[0], [entry('S6', 10)], sites, config)
    assert not result['feasible']
    assert {v['constraint'] for v in result['violations']} == {'convergence_failed'}


@pytest.fixture(scope='module')
def full_plan():
    config = load_config_dir(ROOT / 'config')
    before = deepcopy(config)
    payload = {'target_kw': 300}
    result = plan_charging(payload, config)
    assert config == before and payload == {'target_kw': 300}
    return config, result


def test_six_transformer_integration_and_reference(full_plan):
    config, result = full_plan
    ids = [f'T{i}' for i in range(1, 7)]
    for key in ('existing', 'baseline', 'plan'):
        assert [t['transformer_id'] for t in result[key]['assessment']['transformers']] == ids
        for t in result[key]['assessment']['transformers']:
            assert len(t['simulation']['series']['voltage_pu']) == 96
    assert result['baseline']['description'] == 'Unplanned installation (modelled)'
    assert result['baseline']['allocation'] == [entry('S1', 150), entry('S2', 120), entry('S4', 30)]
    assert result['planning']['selected_site_ids'] == ['S1', 'S2', 'S5', 'S6']
    assert result['plan']['unplaced_kw'] == 0
    assert sum(e['kw'] for e in result['plan']['allocation']) == 300
    assert result['before_after']['feasibility']['additional_allocations_feasible']
    assert not result['before_after']['feasibility']['whole_neighbourhood_feasible']
    violations = result['before_after']['feasibility']['final_violations']
    assert violations == result['before_after']['feasibility']['baseline_violations']
    assert {v['transformer_id'] for v in violations} == {'T5'}
    hospital = next(s for s in result['planning']['sites'] if s['site_id'] == 'S4')
    assert hospital['reason_code'] == 'baseline_violation' and not hospital['electrically_eligible']
    assert not any(e['site_id'] == 'S4' for e in result['plan']['allocation'])
    assert result['plan']['cost']['controllers_inr'] == 150000
    assert result['plan']['cost']['connections_inr'] == 0
    assert result['plan']['cost']['total_inr'] == 150000
    assert result['planning']['evaluations'] <= 285
    json.dumps(result, allow_nan=False)


def test_final_allocation_is_jointly_feasible_and_energy_retained(full_plan):
    config, result = full_plan
    transformers = config['neighbourhood']['parameters']['transformers']['value']
    sites = config['neighbourhood']['parameters']['sites']['value']
    allocated = result['plan']['allocation']
    by_site = {s['id']: s['transformer_id'] for s in sites}
    selected_ids = {by_site[e['site_id']] for e in allocated}
    for t in transformers:
        if t['id'] in selected_ids:
            assessment = evaluate_allocation(t, allocated, sites, config)
            assert assessment['feasible']
            for d in DAYS:
                for e in allocated:
                    if e['managed'] and by_site[e['site_id']] == t['id']:
                        assert assessment['days'][d]['served_energy_pct'][e['site_id']] >= 90


def test_before_after_metrics_and_coincident_aggregation(full_plan):
    config, result = full_plan
    previous, raw_before = assess_network_with_precision({'allocation': []}, config)
    proposed, raw_after = assess_network_with_precision({'allocation': result['plan']['allocation']}, config)
    assert result['before_after']['impact'] == _present(compare_network_impacts(raw_before, raw_after, config))
    before, b = scenario_metrics(previous, raw_before, config)
    after, a = scenario_metrics(proposed, raw_after, config)
    assert result['before_after']['electrical'] == _present(before_after_electrical(b, a))
    coincident = [sum(raw_after[t]['summer_weekday']['ev_kw'][i] for t in raw_after) for i in range(96)]
    assert result['plan']['assessment']['totals']['served_kw_peak'] == round(max(coincident), 4)
    assert result['plan']['assessment']['totals']['served_energy_kwh_per_day'] == round(sum(coincident) / 4, 4)
    assert max(coincident) <= sum(max(raw_after[t]['summer_weekday']['ev_kw']) for t in raw_after)
    assert before['totals']['served_kw_peak'] == 0
    for item in result['before_after']['electrical']:
        for day in DAYS:
            assert item['days'][day]['delta']['peak_loading_pct'] >= 0
    assert all(t['life']['month']['additional_equivalent_aging_hours'] >= 0
               for t in result['before_after']['impact']['transformers'])


def test_staggered_branch_peaks_are_not_added(config):
    network, raw = assess_network_with_precision({'allocation': []}, config)
    for day in DAYS:
        raw['T1'][day]['ev_kw'][0] = 20
        raw['T2'][day]['ev_kw'][1] = 30
    assessment, _ = scenario_metrics(network, raw, config)
    assert assessment['totals']['served_kw_peak'] == 30  # Not 20 + 30.
    assert assessment['totals']['served_energy_kwh_per_day'] == 12.5


def test_full_plan_determinism_and_no_mutation(full_plan):
    config, expected = full_plan
    snapshot = deepcopy(config)
    assert plan_charging({'target_kw': 300}, config) == expected
    assert config == snapshot


def test_unplanned_reference_obeys_existing_footfall_definition(config):
    candidates = planning_sites(config)
    assert unplanned_allocation(candidates, 150, config) == [entry('S1', 150)]
    candidates[0]['eligible'] = False
    assert unplanned_allocation(candidates, 150, config) == [entry('S2', 120), entry('S4', 30)]


def test_comparison_rejects_mismatched_transformer_identity():
    with pytest.raises(ValueError, match='identities'):
        before_after_electrical([{'transformer_id': 'T1'}], [{'transformer_id': 'T2'}])


@pytest.mark.parametrize('key,new', [('managed_charging_cost_per_site_inr', -1),
                                    ('new_connection_cost_inr_per_kw', float('nan')),
                                    ('planner_max_evaluations', 1)])
def test_invalid_plan_settings_rejected_before_simulation(config, monkeypatch, key, new):
    from gridmind_engine import planner
    value(config, key, new)
    monkeypatch.setattr(planner, 'assess_hosting', lambda *_: pytest.fail('invalid settings reached physics'))
    with pytest.raises(ValueError, match=key):
        plan_charging({'target_kw': 300}, config)


def test_monthly_aggregation_has_defined_units_without_double_counting(config):
    network, raw = assess_network_with_precision({'allocation': []}, config)
    for branch in raw.values():
        for day in DAYS:
            branch[day]['aging_factor'] = [1] * 96
            branch[day]['hotspot_c'] = [60] * 96
            branch[day]['top_oil_c'] = [50] * 96
            branch[day]['voltage_pu'] = [1] * 96
    for day in DAYS:
        raw['T1'][day]['voltage_pu'][:2] = [.94, .94]
        raw['T3'][day]['voltage_pu'][0] = .94
    assessment, _ = scenario_metrics(network, raw, config)
    totals = assessment['totals']
    # Six units at FAA=1 consume 6*30 reference-equivalent transformer-days.
    assert totals['life_consumed_days_per_month'] == 180
    assert totals['depreciation_inr_per_month'] == 13200
    assert totals['connections_affected'] == 270  # T1 180 + T3 90, once each.
    assert totals['customer_hours_per_month'] == 3375  # (180*.5 + 90*.25)*30.
    assert totals['worst_min_voltage_v'] == pytest.approx(216.2)
    assert totals['worst_hotspot_c'] == 60
    assert totals['transformers_in_violation'] == 2


def test_zero_requested_demand_and_eligibility_configuration(config):
    sites = config['neighbourhood']['parameters']['sites']['value']
    sites[0]['requested_kw'] = 0
    sites[1]['eligible'] = False
    ranked = planning_sites(config)
    assert ranked[0]['requested_kw'] == 0
    assert not ranked[1]['eligible']


@pytest.mark.parametrize('increment', [0, -10, 2.5, True, float('nan'), float('inf')])
def test_invalid_allocation_increment(config, increment):
    value(config, 'allocation_block_kw', increment)
    with pytest.raises(ValueError, match='allocation_block_kw'):
        planning_sites(config)


def test_missing_connection_quote_parameter_is_named(config):
    del config['neighbourhood']['parameters']['new_connection_cost_inr_per_kw']
    with pytest.raises(ValueError, match='new_connection_cost_inr_per_kw'):
        plan_charging({'target_kw': 300}, config)


def stub_hosting(config):
    """Fast orchestration fixture; real hosting is exercised by full_plan."""
    return dict(hosting=dict(transformers=[
        dict(transformer_id=t['id'], baseline=dict(feasible=t['id'] != 'T5', violations=[]),
             hosting=dict(unmanaged_kw=0, managed_kw=0))
        for t in config['neighbourhood']['parameters']['transformers']['value']]),
        assumptions=[], limitations=[])


def test_zero_target_returns_existing_network_without_incremental_impact(config, monkeypatch):
    from gridmind_engine import planner
    value(config, 'target_kw_options', [0])
    monkeypatch.setattr(planner, 'assess_hosting', stub_hosting)
    result = plan_charging({'target_kw': 0}, config)
    assert result['plan']['allocation'] == result['baseline']['allocation'] == []
    assert result['plan']['cost']['total_inr'] == 0
    assert result['planning']['evaluations'] == 0
    assert result['comparison']['net']['payback_months'] is None
    assert result['before_after']['impact']['totals']['additional_equivalent_aging_hours_per_month'] == 0
    assert result['before_after']['feasibility']['additional_allocations_feasible']
    assert not result['before_after']['feasibility']['whole_neighbourhood_feasible']


def test_configured_connection_quote_applies_without_inventing_hardware_cost(config, monkeypatch):
    from gridmind_engine import planner
    value(config, 'target_kw_options', [10])
    value(config, 'new_connection_cost_inr_per_kw', 7.5)
    monkeypatch.setattr(planner, 'assess_hosting', stub_hosting)
    result = plan_charging({'target_kw': 10}, config)
    assert result['plan']['allocation'] == [entry('S1', 10)]
    assert result['plan']['cost'] == dict(controllers_inr=0, connections_inr=75,
                                        battery_inr=0, upgrade_inr=0, total_inr=75)


def test_final_network_is_checked_independently(config, monkeypatch):
    from gridmind_engine import planner
    value(config, 'target_kw_options', [10])
    monkeypatch.setattr(planner, 'assess_hosting', stub_hosting)
    original = planner.assess_network_with_precision
    calls = []
    def changed_final(payload, cfg):
        response, raw = original(payload, cfg)
        calls.append(payload)
        if len(calls) == 3:
            raw['T4']['summer_weekday']['voltage_pu'][0] = .94
        return response, raw
    monkeypatch.setattr(planner, 'assess_network_with_precision', changed_final)
    with pytest.raises(ValueError, match='Final combined plan'):
        plan_charging({'target_kw': 10}, config)


def test_misordered_assessment_is_rejected(config):
    response, raw = assess_network_with_precision({'allocation': []}, config)
    response['assessment']['transformers'].reverse()
    with pytest.raises(ValueError, match='identities'):
        scenario_metrics(response, raw, config)


def test_invalid_energy_floor_rejected_by_reusable_evaluator(config):
    value(config, 'min_served_energy_pct_for_managed', float('nan'))
    transformers = config['neighbourhood']['parameters']['transformers']['value']
    sites = config['neighbourhood']['parameters']['sites']['value']
    with pytest.raises(ValueError, match='min_served_energy_pct_for_managed'):
        evaluate_allocation(transformers[0], [], sites, config)
