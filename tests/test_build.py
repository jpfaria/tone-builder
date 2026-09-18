"""build_tone with a fake device: each block adds per-harmonic gains to the note."""
import numpy as np
import pytest
import soundfile as sf

from tests.synth import note, write
from tone_builder.build import Option, Unresolved, build_tone
from tone_builder.research import CLASSES

TARGET = [0, 4, -4, 4, -4, 4, -4, 4]
MIDIS = [60, 62, 64, 65, 67, 69, 71, 72]


class FakeDevice:
    """Blocks are dicts {"model": name, "gains": [8 dB]}; the chain sums them."""

    def __init__(self, options, unresolved=()):
        self._options = options
        self._unresolved = list(unresolved)
        self.gr = {}

    def resolve(self, research):
        return self._options, self._unresolved

    def renderer(self, blocks):
        total = np.sum([b["gains"] for b in blocks], axis=0) if blocks else np.zeros(8)

        def render(src, dst):
            midi = int(src.stem.split("-")[-2] if src.stem.count("-") >= 3 else src.stem.split("-")[1])
            sf.write(str(dst), note(midi, start_s=0.02, gains_db=list(total)), 48000, subtype="FLOAT")
        return render

    def gain_reduction(self, blocks, dis, workdir):
        return self.gr.get(blocks[0]["model"], 0.0)

    def eq_blocks(self, band_gains):
        return [{"model": "eq", "gains": [0.0] * 8, "band_gains": band_gains}]

    def preset(self, blocks, name):
        return {"name": name, "blocks": [b["model"] for b in blocks]}


def _opt(name, klass, unit, gains):
    return Option(name=name, klass=klass, unit=unit, blocks=[{"model": name, "gains": gains}])


def _inputs(tmp_path):
    disc = np.concatenate([note(m, gains_db=TARGET) for m in MIDIS])
    by_midi = {m: [write(tmp_path / "lib" / f"c1-{m}-X.wav", note(m, start_s=0.02))] for m in MIDIS}
    return disc, by_midi


RESEARCH = {
    "blocks": [
        {"class": "amp", "unit": "Amp", "era": "record", "sources": ["https://a"]},
        {"class": "single_drive", "unit": "TS", "era": "record", "sources": ["https://b"]},
    ],
    "not_found": [{"class": c, "searched": ["https://c"]}
                  for c in ("stacked_drives", "boost", "compressor", "cab", "time_fx")],
}


def test_sourced_drive_is_kept_and_report_is_complete(tmp_path):
    disc, by_midi = _inputs(tmp_path)
    dev = FakeDevice({
        "amp": [_opt("amp", "amp", "Amp", [0, 2, -2, 2, -2, 2, -2, 2])],
        "single_drive": [_opt("ts", "single_drive", "TS", [0, 2, -2, 2, -2, 2, -2, 2])],
    })
    out = build_tone(disc, disc, by_midi, RESEARCH, dev, tmp_path / "w", "song")
    assert out["preset"]["blocks"][:2] == ["ts", "amp"]
    assert out["report"]["classes"]["single_drive"]["sourced"]["accepted"] is True
    assert set(out["report"]["classes"]) == set(CLASSES)
    assert out["report"]["status"] == "pronto"


def test_unresolved_research_stops(tmp_path):
    disc, by_midi = _inputs(tmp_path)
    with pytest.raises(Unresolved):
        build_tone(disc, disc, by_midi, RESEARCH, FakeDevice({}, unresolved=["TS"]), tmp_path / "w", "s")


def test_invalid_research_stops(tmp_path):
    disc, by_midi = _inputs(tmp_path)
    bad = {"blocks": [{"class": "amp", "unit": "Amp", "era": "tour", "sources": ["https://a"]}]}
    with pytest.raises(ValueError):
        build_tone(disc, disc, by_midi, bad, FakeDevice({}), tmp_path / "w", "s")


def test_class_without_research_answer_is_parcial(tmp_path):
    disc, by_midi = _inputs(tmp_path)
    r = {**RESEARCH, "not_found": RESEARCH["not_found"][:-1]}   # time_fx never searched
    dev = FakeDevice({"amp": [_opt("amp", "amp", "Amp", [0, 4, -4, 4, -4, 4, -4, 4])]})
    out = build_tone(disc, disc, by_midi, r, dev, tmp_path / "w", "s")
    assert out["report"]["status"] == "parcial"
    assert "time_fx" in out["report"]["missing"]


def test_unit_without_catalog_model_becomes_the_class_reason(tmp_path):
    disc, by_midi = _inputs(tmp_path)
    r = {**RESEARCH, "blocks": RESEARCH["blocks"] + [
        {"class": "cab", "unit": "Dumble 4x12", "era": "record", "sources": ["https://d"], "absent_from_catalog": True}],
         "not_found": [n for n in RESEARCH["not_found"] if n["class"] != "cab"]}
    dev = FakeDevice({"amp": [_opt("amp", "amp", "Amp", [0, 4, -4, 4, -4, 4, -4, 4])]})
    out = build_tone(disc, disc, by_midi, r, dev, tmp_path / "w", "s")
    assert "Dumble 4x12" in out["report"]["classes"]["cab"]["reason"]
    assert out["report"]["absent_from_catalog"] == {"cab": ["Dumble 4x12"]}


import re

from tone_builder import library as lib_mod

CHORD = [40, 47, 56]
CHORD_STRINGS = (6, 5, 3)


class ChordDevice(FakeDevice):
    """Renders any DI by re-synthesizing each note found in its file name with the chain's gains."""

    def renderer(self, blocks):
        total = np.sum([b["gains"] for b in blocks], axis=0) if blocks else np.zeros(8)

        def render(src, dst):
            # a library note (c6-40-E2.wav) or a summed chord DI (c6-40_c5-47_c3-56.wav), possibly
            # copied under a prefix/suffix (margin: 00-c6-40_c5-47_c3-56+0.wav)
            midis = [int(m) for m in re.findall(r"(?<![0-9])c[1-6]-([0-9]+)", src.stem)]
            y = sum(note(m, seconds=1.0, start_s=0.02, gains_db=list(total)) for m in midis)
            sf.write(str(dst), y, 48000, subtype="FLOAT")
        return render


def _chord(gains=None):
    return sum(note(m, seconds=1.0, gains_db=gains) for m in CHORD)


def test_build_on_a_chord_only_part(tmp_path):
    disc = np.concatenate([_chord(TARGET) for _ in range(6)])
    by_midi = {m: [write(tmp_path / "lib" / lib_mod.note_filename(s, m), note(m, seconds=1.0, start_s=0.02))]
               for s, m in zip(CHORD_STRINGS, CHORD)}
    amp = _opt("amp1", "amp", "Amp", [0.0] * 8)
    drive = _opt("ts", "single_drive", "TS", TARGET)
    dev = ChordDevice({"amp": [amp], "single_drive": [drive]})
    res = build_tone(disc, disc, by_midi, RESEARCH, dev, tmp_path / "w", "x",
                     chords={"detector": "salience", "recorded": {}})
    kinds = {n["kind"] for n in res["report"]["notes"]}
    assert kinds == {"chord"}
    assert {n["source"] for n in res["report"]["notes"]} == {"summed"}
    assert res["report"]["final_deviation_db"] is not None


def test_empty_target_says_what_was_seen(tmp_path):
    disc = _chord()
    dev = ChordDevice({"amp": [_opt("amp1", "amp", "Amp", [0.0] * 8)]})
    with pytest.raises(ValueError, match=r"chords_seen=1"):
        build_tone(disc, disc, {}, RESEARCH, dev, tmp_path / "w", "x",
                   chords={"detector": "salience", "recorded": {}})
