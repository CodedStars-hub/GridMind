"""Run the shared engine and emit JSON or a plain-English simulation report."""

import argparse
import json
from pathlib import Path
import sys

from .powerflow import PowerFlowError
from .profiles import load_config_dir
from .simulate import run_simulation
from .validate import InvalidInputError


def _summary_report(result):
    """Format inputs, all summary fields, alerts and samples on the hour."""
    lines = [f"Inputs: {json.dumps(result['meta']['inputs'])}",
             f"Verdict: {result['verdict']['status']} — {result['verdict']['message']}"]
    labels = {
        'min_voltage_pu': ('Minimum voltage', 'p.u.'), 'min_voltage_time': ('Minimum voltage time', 'HH:MM'),
        'peak_voltage_deviation_pu': ('Peak voltage deviation', 'p.u.'),
        'peak_hotspot_c': ('Peak hot-spot', '°C'), 'peak_hotspot_time': ('Peak hot-spot time', 'HH:MM'),
        'peak_loading_pct': ('Peak loading', '% rated current'), 'peak_loading_time': ('Peak loading time', 'HH:MM'),
        'peak_aging_factor': ('Peak aging factor', 'unitless'),
        'daily_equivalent_aging_hours': ('Daily equivalent aging', 'h/day'),
        'insulation_life_years': ('Insulation life', 'years'),
    }
    for key, (label, unit) in labels.items():
        lines.append(f"{label}: {result['summary'][key]} {unit}")
    lines.append('Alerts:')
    if not result['alerts']:
        lines.append('None')
    for event in result['alerts']:
        lines.append(f"{event['severity']} {event['type']} {event['start']}–{event['end']}: "
                     f"{event['peak_value']} {event['unit']}")
    lines.append('time  | net_kw   | voltage_pu | loading_pct | hotspot_c | aging_factor')
    series = result['series']
    for index, time in enumerate(series['time']):
        if time.endswith(':00'):
            lines.append(f"{time} | {series['net_kw'][index]:8.4f} | {series['voltage_pu'][index]:10.4f} | "
                         f"{series['loading_pct'][index]:11.4f} | {series['hotspot_c'][index]:9.4f} | "
                         f"{series['aging_factor'][index]:12.4f}")
    return '\n'.join(lines)


def main(argv=None):
    """Return an exit code and keep expected input, solver and file errors traceback-free."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ev', type=int, required=True)
    parser.add_argument('--pv', type=int, required=True)
    parser.add_argument('--day', required=True)
    parser.add_argument('--load', required=True)
    parser.add_argument('--config-dir', type=Path, default=Path(__file__).resolve().parents[2] / 'config')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--pretty', action='store_true')
    parser.add_argument('--summary', action='store_true')
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code
    try:
        config = load_config_dir(args.config_dir)
        result = run_simulation(dict(ev_kw=args.ev, pv_kwp=args.pv, day_type=args.day, load_level=args.load), config)
        if args.summary:
            output = _summary_report(result)
        else:
            output = json.dumps(result, allow_nan=False, indent=2 if args.pretty else None,
                                separators=None if args.pretty else (',', ':'))
        if args.out:
            args.out.write_text(output + '\n', encoding='utf-8')
        else:
            print(output)
        return 0
    except InvalidInputError as exc:
        print(f'{exc.field}: {exc.message}', file=sys.stderr)
        return 2
    except PowerFlowError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 4


if __name__ == '__main__':
    sys.exit(main())
