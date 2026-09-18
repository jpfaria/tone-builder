"""The song's audio is tone-analyzer's: the full track and the separated guitar live in its
library (`~/.tone-analyzer/tones/<artist>-<song>/`). tone-builder reads them from there, and when
the song is not there yet it asks tone-analyzer to separate, analyze and store it. Nothing about
the song's audio is ever written under `~/.tone-builder/`."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

Ingest = Callable[[Path, "Path | None", str, str, str], None]
SEPARATOR = "demucs htdemucs_6s"


class SongAudioError(Exception):
    pass


def _tone_analyzer(args: list[str]) -> None:
    exe = Path(sys.executable).parent / "tone-analyzer"
    p = subprocess.run([str(exe), *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise SongAudioError(f"tone-analyzer {args[0]} failed (exit {p.returncode}): {(p.stderr or p.stdout).strip()}")


def tone_analyzer_ingest(disc: Path, lead: Path | None, artist: str, song: str, role: str) -> None:
    """separate (unless a stem was handed over) -> analyze -> tones add, all by tone-analyzer."""
    with tempfile.TemporaryDirectory(prefix="tone-builder-ingest-") as tmp:
        tmp = Path(tmp)
        kind, reference = "stem", lead
        if reference is None:
            _tone_analyzer(["separate", str(disc), "--out-dir", str(tmp / "sep")])
            kind, reference = "separated", tmp / "sep" / "guitar.wav"
        _tone_analyzer(["analyze", str(reference), "--out-dir", str(tmp / "analysis")])
        add = ["tones", "add", "--artist", artist, "--song", song, "--role", role, "--analysis", str(tmp / "analysis"),
               "--reference-kind", kind, "--reference", str(reference), "--track", str(disc)]
        _tone_analyzer(add + (["--separator", SEPARATOR] if kind == "separated" else []))


def _stored(artist: str, song: str, role: str, roots: list[Path] | None) -> tuple[Path, Path] | None:
    from tone_analyzer import tones
    wanted = tones.slug(artist, song)
    for e in tones.list_entries(roots):
        if e["slug"] != wanted:
            continue
        entry = Path(e["path"])
        meta = json.loads((entry / "tone.json").read_text(encoding="utf-8"))["roles"].get(role)
        if meta and meta.get("track") and meta.get("reference"):
            track, ref = entry / meta["track"]["file"], entry / meta["reference"]["file"]
            if track.is_file() and ref.is_file():
                return track, ref
    return None


def song_audio(artist: str, song: str, role: str, disc: Path | None, lead: Path | None,
               ingest: Ingest = tone_analyzer_ingest, roots: list[Path] | None = None) -> tuple[Path, Path]:
    """(full track, separated guitar), both inside tone-analyzer's library."""
    found = _stored(artist, song, role, roots)
    if found:
        return found
    if disc is None:
        raise SongAudioError(f"'{artist} - {song}' ({role}) is not in tone-analyzer's library "
                             f"(`tone-analyzer tones find`): give the record with --disc")
    if not Path(disc).is_file():
        raise SongAudioError(f"record not found: {disc}")
    ingest(Path(disc), lead, artist, song, role)
    found = _stored(artist, song, role, roots)
    if not found:
        from tone_analyzer import tones
        raise SongAudioError(f"tone-analyzer stored no '{role}' with track and reference for {tones.slug(artist, song)}")
    return found
