from pathlib import Path

import numpy as np
import soundfile as sf

from tests.test_recorder import _note
from tone_builder import cli, library


def _lib(tmp_path: Path) -> Path:
    sr = 48000
    pos = tmp_path / "g" / "pos5"
    pos.mkdir(parents=True)
    library.write_yaml(tmp_path / "g" / "guitarra.yaml", {"name": "test"})
    rng = np.random.default_rng(1)
    for midi in (64, 65):
        x = np.concatenate([rng.standard_normal(int(0.02 * sr)) * 1e-4, _note(midi, sr, 1.0)]).astype(np.float32)
        sf.write(pos / library.note_filename(1, midi), x, sr, subtype="FLOAT")
    sf.write(pos / library.note_filename(1, 66), np.clip(_note(66, sr, 1.0, gain=3.0), -1, 1), sr, subtype="FLOAT")
    return tmp_path


def test_list(tmp_path: Path, capsys):
    root = _lib(tmp_path)
    assert cli.main(["library", "list", "--root", str(root)]) == 0
    assert "g pos5 3 notes" in capsys.readouterr().out


def test_check_flags_bad_note(tmp_path: Path, capsys):
    root = _lib(tmp_path)
    assert cli.main(["library", "check", "g", "pos5", "--root", str(root)]) == 1
    out = capsys.readouterr().out
    assert "c1-66-F#4" in out and "saturation" in out
    assert library.read_yaml(root / "g" / "pos5" / "medicao.yaml")["c1-64-E4"]["accepted"] is True


def test_record_requires_device_and_channel(tmp_path: Path, capsys):
    assert cli.main(["library", "record", "g", "pos5", "1", "--root", str(tmp_path)]) == 2
    assert "--device" in capsys.readouterr().err
