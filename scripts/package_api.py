"""Build a reproducible Lambda zip containing only code and model JSON data."""

import argparse
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def application_files(root):
    """Explicit application directories exclude tests, events, credentials and caches."""
    root = Path(root)
    files = {}
    for folder, prefix in ((root / 'lambda', ''),
                           (root / 'engine' / 'gridmind_engine', 'gridmind_engine/')):
        for path in sorted(folder.glob('*.py')):
            files[prefix + path.name] = path
    for directory in (root / 'config', root / 'config' / 'profiles'):
        for path in sorted(directory.glob('*.json')):
            files[path.relative_to(root).as_posix()] = path
    required = ['handler.py', 'api_routes.py', 'api_http.py',
                'gridmind_engine/__init__.py', 'gridmind_engine/simulate.py',
                'gridmind_engine/network.py', 'gridmind_engine/impact.py',
                'gridmind_engine/bess.py', 'gridmind_engine/telemetry.py',
                'gridmind_engine/hosting.py', 'gridmind_engine/planner.py',
                'config/neighbourhood.json', 'config/profiles/base_load_mixed_profile.json',
                'config/profiles/base_load_commercial_profile.json', 'config/profiles/ev_daytime_profile.json']
    if any(name not in files for name in required):
        raise ValueError('deployment package is missing required application files')
    for name, path in files.items():
        if path.is_symlink():
            raise ValueError(f'package source must not be a symlink: {name}')
        if name.endswith('.json'):
            json.loads(path.read_text(encoding='utf-8'))
    return files


def build_package(destination, root=ROOT):
    """Write deterministic members; Lambda finds handler and config at the zip root."""
    files = application_files(root)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(files.items()):
            # Fixed zip timestamp and ordinary read permissions make builds reproducible.
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'out' / 'gridmind-api.zip')
    args = parser.parse_args(argv)
    destination = build_package(args.out)
    with zipfile.ZipFile(destination) as archive:
        print(f'Package: {destination}; files: {len(archive.namelist())}; bytes: {destination.stat().st_size}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
