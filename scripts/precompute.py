"""Regenerate or verify small, reproducible engine snapshots; no cloud access."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine'))
from gridmind_engine import __version__
from gridmind_engine.profiles import load_config_dir
from gridmind_engine.simulate import run_simulation


def generate(generated_at):
    """Record all configuration and engine source hashes with actual engine outputs."""
    parsed = datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError('generated_at must be a UTC timestamp')
    files = sorted((ROOT / 'config').rglob('*.json')) + sorted((ROOT / 'engine/gridmind_engine').glob('*.py'))
    hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    fingerprint = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    config = load_config_dir(ROOT / 'config')
    p = config['scenarios']['parameters']
    default = {name: p['default_' + name]['value'] for name in ('ev_kw', 'pv_kwp', 'day_type', 'load_level', 'bess')}
    candidates = [default, dict(default, ev_kw=min(p['ev_kw_options']['value']), day_type='winter_weekday', load_level='moderate'), dict(default, ev_kw=max(p['ev_kw_options']['value']), pv_kwp=min(p['pv_kwp_options']['value']), load_level='critical')]
    artifacts = []
    for index, inputs in enumerate(candidates):
        result = run_simulation(inputs, config)
        result['meta']['source'] = 'cached'
        artifacts.append(dict(id=f'scenario-{index + 1}', inputs=result['meta']['inputs'], result=result))
    return dict(schema_version=1, engine_version=__version__, generated_at=generated_at, model_sha256=fingerprint, source_hashes=hashes, artifacts=artifacts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--generated-at')
    parser.add_argument('--out', type=Path, default=ROOT / 'frontend/public/precomputed/scenarios.json')
    args = parser.parse_args()
    existing = json.loads(args.out.read_text()) if args.out.exists() else None
    stamp = args.generated_at or (existing['generated_at'] if existing else datetime.now(timezone.utc).isoformat())
    data = json.dumps(generate(stamp), indent=2, allow_nan=False) + '\n'
    if args.verify:
        if not existing or args.out.read_text() != data:
            raise SystemExit('FAIL: snapshot differs from current engine/configuration or serialization')
        print('PASS: all three snapshots reproduce byte-for-byte with matching provenance')
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(data)
        print(f'Generated three real engine snapshots: {args.out}')

if __name__ == '__main__':
    main()
