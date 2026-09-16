from pathlib import Path

from tone_builder import library


def test_note_filename_roundtrip():
    assert library.note_filename(1, 64) == "c1-64-E4.wav"
    assert library.note_filename(2, 61) == "c2-61-C#4.wav"
    assert library.parse_note_filename("c2-61-C#4.wav") == (2, 61)
    assert library.parse_note_filename("c6-bruto.wav") is None
    assert library.parse_note_filename("readme.txt") is None


def test_expected_midis_standard_tuning():
    assert library.expected_midis(6)[:3] == [40, 41, 42]
    assert library.expected_midis(1)[-1] == 64 + 15


def test_listing(tmp_path: Path):
    pos = tmp_path / "prs-silver-sky-se" / "pos5"
    pos.mkdir(parents=True)
    for n in ("c1-64-E4.wav", "c1-65-F4.wav", "c1-bruto.wav"):
        (pos / n).write_bytes(b"")
    (tmp_path / "prs-silver-sky-se" / "guitarra.yaml").write_text("name: x\n")
    assert library.list_guitars(tmp_path) == ["prs-silver-sky-se"]
    assert library.list_positions(tmp_path, "prs-silver-sky-se") == ["pos5"]
    assert [p.name for p in library.list_notes(tmp_path, "prs-silver-sky-se", "pos5")] == ["c1-64-E4.wav", "c1-65-F4.wav"]


def test_yaml_roundtrip(tmp_path: Path):
    p = tmp_path / "a.yaml"
    library.write_yaml(p, {"b": 1, "a": [1, 2]})
    assert library.read_yaml(p) == {"b": 1, "a": [1, 2]}


def test_library_dir_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TONE_BUILDER_LIBRARY", str(tmp_path))
    assert library.library_dir() == tmp_path
