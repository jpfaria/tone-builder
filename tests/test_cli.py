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


def test_check_covers_chords(tmp_path: Path, capsys):
    from tests.synth import SR as SYNTH_SR
    from tests.synth import note as snote

    root = _lib(tmp_path)
    (root / "g" / "pos5" / library.CHORDS_DIR).mkdir()
    good = sum(snote(m, seconds=1.0, start_s=0.3) for m in (40, 47, 56))
    sf.write(root / "g" / "pos5" / library.CHORDS_DIR / library.chord_filename(
        [(6, 40), (5, 47), (3, 56)], 1), good, SYNTH_SR, subtype="FLOAT")
    bad = snote(41, seconds=1.0, start_s=0.3)
    sf.write(root / "g" / "pos5" / library.CHORDS_DIR / library.chord_filename(
        [(6, 41), (5, 48), (3, 57)], 1), bad, SYNTH_SR, subtype="FLOAT")
    rc = cli.main(["library", "check", "g", "pos5", "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "ok       acordes/c6-40_c5-47_c3-56-t1" in out
    assert "REJECTED acordes/c6-41_c5-48_c3-57-t1" in out


def test_record_requires_device_and_channel(tmp_path: Path, capsys):
    assert cli.main(["library", "record", "g", "pos5", "1", "--root", str(tmp_path)]) == 2
    assert "--device" in capsys.readouterr().err


def test_record_chord_requires_device_and_channel(tmp_path: Path, capsys):
    assert cli.main(["library", "record-chord", "g", "pos5", "c6-40_c5-47",
                      "--root", str(tmp_path)]) == 2
    assert "--device" in capsys.readouterr().err


def test_target_writes_notes_with_a_library_pair(tmp_path: Path, capsys):
    import json

    from tests.synth import note, write

    pos = tmp_path / "lib" / "g" / "pos5"
    write(pos / "c2-62-D4.wav", note(62, start_s=0.02))
    library.write_yaml(tmp_path / "lib" / "g" / "guitarra.yaml", {"name": "g"})
    disc = write(tmp_path / "disc.wav", note(62))
    out = tmp_path / "target.json"
    rc = cli.main(["target", str(disc), str(disc), "--guitar", "g", "--position", "pos5",
                   "--root", str(tmp_path / "lib"), "--out", str(out)])
    assert rc == 0
    t = json.loads(out.read_text())
    assert [n["midi"] for n in t] == [62]
    assert "D4" in capsys.readouterr().out


def test_target_drops_the_note_that_fires_at_a_chords_attack(tmp_path: Path, capsys):
    import json

    from tests.synth import note, write

    pos = tmp_path / "lib" / "g" / "pos5"
    write(pos / library.note_filename(6, 40), note(40, start_s=0.02))
    write(pos / library.note_filename(5, 47), note(47, start_s=0.02))
    library.write_yaml(tmp_path / "lib" / "g" / "guitarra.yaml", {"name": "g"})
    disc = write(tmp_path / "disc.wav", note(40, seconds=1.0, amp=0.5) + note(47, seconds=1.0, amp=0.08))
    out = tmp_path / "target.json"
    rc = cli.main(["target", str(disc), str(disc), "--guitar", "g", "--position", "pos5",
                   "--root", str(tmp_path / "lib"), "--out", str(out)])
    assert rc == 0
    t = json.loads(out.read_text())
    assert [n["kind"] for n in t] == ["chord"]


def test_validate_passes_on_the_shipped_library(capsys):
    import pytest

    notes = library.list_notes(library.library_dir(), "prs-silver-sky-se", "pos5")
    if not notes or notes[0].stat().st_size < 1024:
        pytest.skip("LFS objects not pulled")
    assert cli.main(["validate", "--dominance", "-6", "0"]) == 0
    out = capsys.readouterr().out
    assert "-6" in out and "false positives" in out


def test_validate_chords_skips_basic_pitch_when_not_installed(tmp_path: Path, capsys):
    from tests.synth import note, write

    pos = tmp_path / "g" / "pos5"
    pos.mkdir(parents=True)
    library.write_yaml(tmp_path / "g" / "guitarra.yaml", {"name": "g"})
    for s, m in ((6, 40), (5, 47)):
        write(pos / library.note_filename(s, m), note(m, start_s=0.02, n_harm=12))
    rc = cli.main(["validate", "--chords", "--root", str(tmp_path), "--guitar", "g", "--position", "pos5"])
    out = capsys.readouterr().out
    assert "basic-pitch: skipped" in out
    assert rc in (0, 1)


def test_build_on_ampero_needs_the_work_patch(tmp_path, capsys):
    rc = cli.main(["build", "--device", "ampero2", "--artist", "A", "--song", "S", "--research", "r.yaml",
                   "--guitar", "g", "--position", "p", "--name", "n", "--out", str(tmp_path)])
    assert rc == 2
    assert "--work-patch" in capsys.readouterr().err


def test_parse_time():
    assert cli.parse_time("2:50") == 170.0
    assert cli.parse_time("95.5") == 95.5


def test_build_asks_tone_analyzer_for_a_song_that_is_not_in_its_library(tmp_path, capsys, monkeypatch):
    from tests.synth import note, write
    from tone_builder import song_audio

    disc = write(tmp_path / "in" / "alive.wav", note(62))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("TONE_ANALYZER_TONES_PATH", str(tmp_path / "lib"))
    seen = []

    def failing(d, lead, artist, song, role):
        seen.append((d, artist, song, role))
        raise song_audio.SongAudioError("demucs not found")

    monkeypatch.setattr(song_audio, "tone_analyzer_ingest", failing)
    rc = cli.main(["build", "--device", "mvave", "--artist", "Nobody", "--song", "Nothing Here Zzz", "--disc", str(disc),
                   "--research", "r.yaml", "--guitar", "g", "--position", "pos5", "--name", "n",
                   "--out", str(tmp_path / "o")])
    assert rc == 5
    assert seen == [(disc, "Nobody", "Nothing Here Zzz", "guitars")]
    assert "demucs not found" in capsys.readouterr().err


def test_check_keeps_the_noise_read_at_recording_when_the_saved_note_has_no_room_for_it(tmp_path: Path, capsys):
    # a note saved with its attack inside the first 10 ms: the file holds no silence to read a noise floor from
    sr = 48000
    pos = tmp_path / "g" / "pos1"
    pos.mkdir(parents=True)
    sf.write(pos / library.note_filename(1, 64), _note(64, sr, 1.0), sr, subtype="FLOAT")
    library.write_yaml(pos / "medicao.yaml", {"c1-64-E4": {"midi": 64, "snr_db": 24.0, "accepted": True, "reasons": []}})
    assert cli.main(["library", "check", "g", "pos1", "--root", str(tmp_path)]) == 0
    assert library.read_yaml(pos / "medicao.yaml")["c1-64-E4"]["snr_db"] == 24.0
