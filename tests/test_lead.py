"""The separated track: given, cached beside the record, or separated on demand."""
from pathlib import Path

import pytest

from tests.synth import note, write
from tone_builder.lead import LeadError, resolve_lead


def _fake_separator(calls: list):
    def separate(disc: Path, out_dir: Path) -> None:
        calls.append(disc)
        write(out_dir / "guitar.wav", note(62))
    return separate


def test_a_given_lead_is_used_and_nothing_is_separated(tmp_path: Path):
    disc = write(tmp_path / "refs" / "original.wav", note(62))
    lead = write(tmp_path / "mine.wav", note(62))
    calls: list = []
    assert resolve_lead(disc, lead, _fake_separator(calls)) == lead
    assert calls == []


def test_without_a_lead_the_record_is_separated_beside_itself(tmp_path: Path):
    disc = write(tmp_path / "refs" / "original.wav", note(62))
    calls: list = []
    got = resolve_lead(disc, None, _fake_separator(calls))
    assert got == tmp_path / "refs" / "lead.wav"
    assert got.is_file() and calls == [disc]


def test_a_lead_already_separated_is_reused(tmp_path: Path):
    disc = write(tmp_path / "refs" / "original.wav", note(62))
    calls: list = []
    resolve_lead(disc, None, _fake_separator(calls))
    resolve_lead(disc, None, _fake_separator(calls))
    assert len(calls) == 1


def test_a_separator_that_writes_no_guitar_is_an_error(tmp_path: Path):
    disc = write(tmp_path / "refs" / "original.wav", note(62))
    with pytest.raises(LeadError, match="guitar.wav"):
        resolve_lead(disc, None, lambda d, o: None)
    assert not (tmp_path / "refs" / "lead.wav").exists()


def test_a_given_lead_that_does_not_exist_is_an_error(tmp_path: Path):
    disc = write(tmp_path / "refs" / "original.wav", note(62))
    with pytest.raises(LeadError, match="nope.wav"):
        resolve_lead(disc, tmp_path / "nope.wav", _fake_separator([]))
