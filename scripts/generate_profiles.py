"""Author illustrative profile JSON; the engine must never import this script."""

import argparse
import json
from pathlib import Path


BASE = {
    'summer_weekday': [(0, .55), (3, .42), (6, .48), (9, .65), (12, .72), (15, .75), (18, .82), (21, 1), (23, .75), (24, .55)],
    'winter_weekday': [(0, .50), (3, .38), (6, .50), (8, .70), (12, .62), (15, .60), (18, .90), (20, 1), (22, .80), (24, .50)],
    'weekend': [(0, .52), (3, .40), (7, .45), (10, .72), (14, .85), (18, .92), (21, 1), (23, .72), (24, .52)],
}
EV_WEEKDAY = [(0, .02), (6, .05), (8, .20), (12, .25), (16, .30), (17, .55), (18, 1), (21, 1), (22, .60), (23, .15), (24, .02)]
EV = {
    'summer_weekday': EV_WEEKDAY,
    'winter_weekday': EV_WEEKDAY,
    'weekend': [(0, .03), (10, .30), (14, .40), (17, .70), (18, 1), (21, 1), (22, .70), (23, .20), (24, .03)],
}
PV_SUMMER = [(0, 0), (6, 0), (7, .08), (8, .30), (9, .52), (10, .68), (12, .80), (14, .70), (15, .58), (16, .38), (17, .15), (18, .02), (19, 0), (24, 0)]
PV = {
    'summer_weekday': PV_SUMMER,
    'winter_weekday': [(0, 0), (7, 0), (8, .12), (9, .35), (10, .52), (12, .65), (14, .58), (15, .40), (16, .18), (17, .03), (17.5, 0), (24, 0)],
    'weekend': PV_SUMMER,
}
AMBIENT_SUMMER = [(0, 34), (5, 30), (9, 36), (12, 41), (15, 43), (18, 40), (21, 36), (24, 34)]
AMBIENT = {
    'summer_weekday': AMBIENT_SUMMER,
    'winter_weekday': [(0, 11), (6, 7), (9, 12), (12, 18), (15, 21), (18, 15), (21, 11), (24, 11)],
    'weekend': AMBIENT_SUMMER,
}


def interpolate(anchors):
    """Sample the supplied day anchors every quarter hour, rounded to four decimals."""
    values = []
    segment = 0
    for index in range(96):
        hour = index * .25
        while hour > anchors[segment + 1][0]:
            segment += 1
        start_hour, start_value = anchors[segment]
        end_hour, end_value = anchors[segment + 1]
        value = start_value + (end_value - start_value) * (hour - start_hour) / (end_hour - start_hour)
        values.append(round(value, 4))
    return values


def generate(output_dir):
    """Write deterministic UTF-8 JSON files to the chosen authoring directory."""
    definitions = [
        ('base_load_profile', BASE, 'fraction of base peak; peak = 1.0',
         'assumption: illustrative residential/commercial mix with an evening peak; not measured data'),
        ('ev_profile', EV, 'fraction of EV hub rating; 1.0 = hub at full rated power',
         'assumption: stress-test case; hub at full rated output during the evening window; PRD v2.0 section 6 gives a 6-10 PM peak'),
        ('pv_profile', PV, 'fraction of installed kWp, includes derating for temperature, soiling and inverter losses',
         'assumption: typical clear-sky Delhi shape with derating; generation spans roughly 7 AM to 6 PM, wider than the PRD 9 AM to 5 PM example; weekend uses the summer shape'),
        ('ambient_profile', AMBIENT, 'degC',
         'assumption: typical Delhi day; summer range 30-43 C within the PRD range of 30-45 C; weekend uses summer weather; winter values are illustrative'),
    ]
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, anchors_by_day, unit, note in definitions:
        data = {
            '_meta': {'purpose': f'Illustrative daily {name} samples at 15-minute intervals.', 'schema_version': 1},
            'parameters': {
                day: {'value': interpolate(anchors), 'unit': unit, 'assumption': note}
                for day, anchors in anchors_by_day.items()
            },
        }
        (output_dir / f'{name}.json').write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'config' / 'profiles')
    generate(parser.parse_args().output_dir)
