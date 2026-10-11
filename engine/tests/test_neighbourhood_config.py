"""Check supplied neighbourhood references, limits and map spacing."""

from itertools import combinations
import math
from pathlib import Path

from gridmind_engine.profiles import load_config_dir


def test_neighbourhood_config():
    config = load_config_dir(Path(__file__).resolve().parents[2] / 'config')
    entries = config['neighbourhood']['parameters']
    values = {name: entry['value'] for name, entry in entries.items()}
    for name, entry in entries.items():
        assert 'value' in entry and isinstance(entry['unit'], str), name
        note = entry.get('source') or entry.get('assumption')
        assert isinstance(note, str) and note.strip(), name
        assert entry.get('source') or note.startswith('assumption: illustrative'), name
    transformers, sites = values['transformers'], values['sites']
    nodes = transformers + sites
    assert len({node['id'] for node in nodes}) == len(nodes)
    transformer_ids = {node['id'] for node in transformers}
    assert all(site['transformer_id'] in transformer_ids for site in sites)
    assert {site['transformer_id'] for site in sites} == transformer_ids
    suffix = '_base_peak_pct_of_rating'
    load_levels = {key.removesuffix(suffix) for key in config['load_levels']['parameters'] if key.endswith(suffix)}
    for node in transformers:
        assert node['archetype'] in {'residential', 'commercial', 'mixed'}
        assert node['ev_usage'] in {'evening', 'daytime'}
        assert node['load_level'] in load_levels
    block = values['allocation_block_kw']
    for site in sites:
        assert 1 <= site['footfall_score'] <= 10
        assert site['max_kw'] > 0 and site['max_kw'] % block == 0
    assert all(target % block == 0 for target in values['target_kw_options'])
    assert values['target_kw_default'] in values['target_kw_options']
    assert sum(site['max_kw'] for site in sites) >= max(values['target_kw_options'])
    assert values['month_weekday_count'] + values['month_weekend_count'] == 30
    for node in nodes:
        assert 0 <= node['x'] <= 100 and 0 <= node['y'] <= 100
    for a, b in combinations(nodes, 2):
        assert math.hypot(a['x'] - b['x'], a['y'] - b['y']) >= 8, (a['id'], b['id'])
    fractions = values['managed_cap_fractions']
    assert all(0 < value < 1 for value in fractions)
    assert all(a > b for a, b in zip(fractions, fractions[1:]))
