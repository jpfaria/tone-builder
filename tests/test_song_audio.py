"""The song's audio lives in tone-analyzer's library; tone-builder only reads it, or asks
tone-analyzer to store it."""
import json
from pathlib import Path

import pytest

from tests.synth import note, write
from tone_builder.song_audio import SongAudioError, song_audio


def _store(root: Path, artist: str, song: str, role: str = "guitars") -> Path:
    from tone_analyzer import tones
    entry = root / tones.slug(artist, song)
    write(entry / "track.wav", note(62))
    write(entry / role / "reference.wav", note(62))
    (entry / "tone.json").write_text(json.dumps({
        "slug": entry.name, "artist": artist, "song": song, "aliases": [], "schema_version": 1,
        "roles": {role: {"reference": {"kind": "separated", "file": f"{role}/reference.wav"},
                         "track": {"file": "track.wav"}}}}))
    return entry


def _ingest(root: Path, calls: list):
    def ingest(disc, lead, artist, song, role):
        calls.append((disc, lead))
        _store(root, artist, song, role)
    return ingest


def test_a_song_already_in_the_library_is_read_from_it(tmp_path: Path):
    entry = _store(tmp_path, "Pearl Jam", "Alive")
    calls: list = []
    track, ref = song_audio("Pearl Jam", "Alive", "guitars", None, None, _ingest(tmp_path, calls), [tmp_path])
    assert (track, ref) == (entry / "track.wav", entry / "guitars" / "reference.wav")
    assert calls == []


def test_a_new_song_is_handed_to_tone_analyzer_and_then_read_from_the_library(tmp_path: Path):
    disc = write(tmp_path / "in" / "alive.wav", note(62))
    lib = tmp_path / "lib"
    calls: list = []
    track, ref = song_audio("Pearl Jam", "Alive", "guitars", disc, None, _ingest(lib, calls), [lib])
    assert calls == [(disc, None)]
    assert lib in track.parents and lib in ref.parents


def test_a_separated_track_handed_over_is_stored_too(tmp_path: Path):
    disc = write(tmp_path / "in" / "alive.wav", note(62))
    lead = write(tmp_path / "in" / "lead.wav", note(62))
    calls: list = []
    song_audio("Pearl Jam", "Alive", "guitars", disc, lead, _ingest(tmp_path / "lib", calls), [tmp_path / "lib"])
    assert calls == [(disc, lead)]


def test_a_song_in_neither_place_is_an_error_that_says_what_to_give(tmp_path: Path):
    with pytest.raises(SongAudioError, match="--disc"):
        song_audio("Pearl Jam", "Alive", "guitars", None, None, _ingest(tmp_path, []), [tmp_path])


def test_an_ingest_that_stores_nothing_is_an_error(tmp_path: Path):
    disc = write(tmp_path / "alive.wav", note(62))
    with pytest.raises(SongAudioError, match="pearl-jam-alive"):
        song_audio("Pearl Jam", "Alive", "guitars", disc, None, lambda *a: None, [tmp_path / "lib"])


def test_a_role_missing_from_a_stored_song_is_ingested(tmp_path: Path):
    _store(tmp_path, "Pearl Jam", "Alive", role="rhythm")
    disc = write(tmp_path / "in" / "alive.wav", note(62))
    calls: list = []
    with pytest.raises(SongAudioError):   # the fake stores nothing: what matters is that ingest was asked
        song_audio("Pearl Jam", "Alive", "lead", disc, None, lambda *a: calls.append(a), [tmp_path])
    assert len(calls) == 1
