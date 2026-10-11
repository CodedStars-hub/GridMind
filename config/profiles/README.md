# 15-Minute Load, Generation & Weather Profiles

Authoritative documentation of the 96-interval (15-minute) normalized diurnal curves used by the GridMind digital twin.

---

## Profile Datasets

Each profile JSON file contains 96 deterministic floating-point values corresponding to the quarter-hour intervals from `00:00` to `23:45`:

| Profile File | Archetype / Domain | Characteristics & Diurnal Peak |
| :--- | :--- | :--- |
| [`ambient_profile.json`](ambient_profile.json) | Ambient Temperature (°C) | Summer curve: 30°C night minimum up to 43°C-45°C peak afternoon (14:00-16:00). Winter curve: 7°C to 21°C. |
| [`base_load_profile.json`](base_load_profile.json) | Residential Demand | Typical residential dual peak: morning domestic surge (07:00-09:00) and evening residential cooling/lighting peak (19:00-22:00). |
| [`base_load_commercial_profile.json`](base_load_commercial_profile.json) | Commercial Demand | Business-hours diurnal load curve spanning 09:00 to 20:00 with sustained midday HVAC air-conditioning consumption. |
| [`base_load_mixed_profile.json`](base_load_mixed_profile.json) | Mixed Utility Demand | Blended curve reflecting hospitals, civic infrastructure, and multi-use developments with continuous 24-hour baseload. |
| [`ev_profile.json`](ev_profile.json) | Evening EV Hub Charging | Commuter charging curve with high concentrated demand during the post-work window (18:00-22:00). |
| [`ev_daytime_profile.json`](ev_daytime_profile.json) | Daytime Commercial EV Charging | Fleet and workplace charging curve peaking between 10:00 and 16:00, ideal for absorbing midday solar PV generation. |
| [`pv_profile.json`](pv_profile.json) | Rooftop Solar PV Generation | Solar insolation curve normalized to 1.0 peak; active daylight span 06:30 to 18:00 peaking at solar noon (12:00-13:00) with temperature derating. |

---

## Deterministic Regeneration

All profiles are authored deterministically from anchor points using the generation tool:

```bash
python scripts/generate_profiles.py
```
This script linearly interpolates between specified hourly anchor points and formats output values to 4 decimal places.
