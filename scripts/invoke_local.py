"""Invoke a local handler using only the HTTP API event file supplied as an argument."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine'))
sys.path.insert(0, str(ROOT / 'lambda'))

from handler import lambda_handler


def main(argv=None):
    """Print the proxy response, or a short summary; return success only for HTTP 200."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('event_file', type=Path)
    parser.add_argument('--pretty', action='store_true')
    parser.add_argument('--summary', action='store_true')
    args = parser.parse_args(argv)
    event = json.loads(args.event_file.read_text(encoding='utf-8'))
    response = lambda_handler(event, None)
    if args.summary:
        print(f"Status: {response['statusCode']}")
        body = json.loads(response['body'])
        if response['statusCode'] == 200 and 'summary' in body:
            print(f"Verdict: {body['verdict']['message']}")
            print(f"Minimum voltage: {body['summary']['min_voltage_pu']} p.u.")
            print(f"Peak hot-spot: {body['summary']['peak_hotspot_c']} °C")
            print(f"Peak loading: {body['summary']['peak_loading_pct']} % rated current")
        elif 'error' in body:
            error = body['error']
            print(f"Error: {error['code']}; field: {error['field']}; message: {error['message']}")
    else:
        print(json.dumps(response, allow_nan=False, indent=2 if args.pretty else None))
    return 0 if response['statusCode'] == 200 else 1


if __name__ == '__main__':
    sys.exit(main())
