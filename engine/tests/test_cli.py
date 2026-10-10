"""Check CLI output and expected failures without launching another process."""

import json

from gridmind_engine import cli
from gridmind_engine.powerflow import PowerFlowError

ARGS = ['--ev', '50', '--pv', '30', '--day', 'summer_weekday', '--load', 'heavy']


def test_default_json(capsys):
    assert cli.main(ARGS) == 0
    captured = capsys.readouterr()
    assert captured.err == ''
    assert set(json.loads(captured.out)) == {'meta', 'series', 'summary', 'alerts', 'verdict', 'bess', 'cost'}


def test_summary(capsys):
    assert cli.main(ARGS + ['--summary']) == 0
    captured = capsys.readouterr()
    assert captured.err == ''
    assert all(text in captured.out for text in ('Peak hot-spot', 'Verdict', '00:00', '23:00'))


def test_out_file(capsys, tmp_path):
    assert cli.main(ARGS) == 0
    expected = json.loads(capsys.readouterr().out)
    output = tmp_path / 'result.json'
    assert cli.main(ARGS + ['--out', str(output)]) == 0
    captured = capsys.readouterr()
    assert captured.out == captured.err == ''
    assert json.loads(output.read_text()) == expected


def test_invalid_ev(capsys):
    assert cli.main(['--ev', '20'] + ARGS[2:]) == 2
    captured = capsys.readouterr()
    assert captured.out == ''
    assert 'ev_kw' in captured.err
    assert 'Traceback' not in captured.err


def test_powerflow_failure(monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise PowerFlowError('test convergence failure')
    monkeypatch.setattr(cli, 'run_simulation', fail)
    assert cli.main(ARGS) == 3
    captured = capsys.readouterr()
    assert captured.out == ''
    assert 'test convergence failure' in captured.err
    assert 'Traceback' not in captured.err


def test_missing_config_dir(capsys, tmp_path):
    missing = tmp_path / 'missing'
    assert cli.main(ARGS + ['--config-dir', str(missing)]) == 4
    captured = capsys.readouterr()
    assert captured.out == ''
    assert str(missing) in captured.err
    assert 'Traceback' not in captured.err


def test_pretty(capsys):
    assert cli.main(ARGS + ['--pretty']) == 0
    output = capsys.readouterr().out
    assert '\n  "meta":' in output
    assert json.loads(output)['meta']['inputs']['ev_kw'] == 50


def test_output_file_failure(capsys, tmp_path):
    missing_parent = tmp_path / 'missing' / 'result.json'
    assert cli.main(ARGS + ['--out', str(missing_parent)]) == 4
    captured = capsys.readouterr()
    assert captured.out == ''
    assert str(missing_parent) in captured.err
    assert 'Traceback' not in captured.err
