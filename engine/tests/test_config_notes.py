"""Checks that every config parameter carries a unit and a source/assumption note.

Rule (from the project plan): no number lives in config without saying where it
came from. Each object under "parameters" needs:
  - "value"  (may be null while the value is still TBD)
  - "unit"   (a string)
  - "source" or "assumption": a non-empty string
Standard library only.
"""

import json
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _all_parameters():
    """Yield (file_name, parameter_name, parameter_object) for every config entry."""
    for path in sorted(CONFIG_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data.get("parameters"), dict), f"{path.name}: parameters must be an object"
        for name, param in data["parameters"].items():
            yield path.name, name, param


def test_config_files_exist():
    assert list(CONFIG_DIR.glob("*.json")), f"no JSON files found in {CONFIG_DIR}"


def test_every_parameter_has_value_unit_and_note():
    for file_name, name, param in _all_parameters():
        where = f"{file_name}: parameter '{name}'"
        assert isinstance(param, dict), f"{where} must be an object"
        assert "value" in param, f"{where} is missing 'value'"
        assert isinstance(param.get("unit"), str), f"{where} is missing a string 'unit'"
        notes = [param.get("source"), param.get("assumption")]
        has_note = any(isinstance(n, str) and n.strip() for n in notes)
        assert has_note, f"{where} needs a non-empty 'source' or 'assumption'"
