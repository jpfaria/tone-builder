"""tone-builder command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import soundfile as sf

from tone_builder import library, recorder


def _root(a) -> Path:
    return Path(a.root) if a.root else library.library_dir()


def _list(a) -> int:
    root = _root(a)
    for g in library.list_guitars(root):
        for p in library.list_positions(root, g):
            print(f"{g} {p} {len(library.list_notes(root, g, p))} notes")
    return 0


def _check(a) -> int:
    root = _root(a)
    med_path = root / a.guitar / a.position / "medicao.yaml"
    med = library.read_yaml(med_path) if med_path.exists() else {}
    bad = 0
    for path in library.list_notes(root, a.guitar, a.position):
        _, midi = library.parse_note_filename(path.name)
        x, sr = sf.read(path, dtype="float32", always_2d=False)
        if x.ndim == 2:
            x = x.T
        entry = recorder.measure_and_judge(x, sr, midi)
        med[path.stem] = entry
        if entry["accepted"]:
            print(f"ok       {path.stem}")
        else:
            bad += 1
            print(f"REJECTED {path.stem}: {', '.join(entry['reasons'])}")
    library.write_yaml(med_path, med)
    return 1 if bad else 0


def _record(a) -> int:
    if a.device is None or a.channel is None:
        print("record: pass --device and --channel — where to listen is never assumed", file=sys.stderr)
        return 2
    x = recorder.record(a.seconds, a.device, a.channel)
    rep = recorder.save_string(_root(a), a.guitar, a.position, a.string, x, recorder.SR)
    print(f"accepted: {rep['accepted']}")
    print(f"rejected: {rep['rejected']}")
    print(f"missing:  {rep['missing']}")
    return 0 if not rep["rejected"] and not rep["missing"] else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tone-builder")
    sub = p.add_subparsers(dest="group", required=True)
    lib = sub.add_parser("library").add_subparsers(dest="cmd", required=True)
    lp = lib.add_parser("list")
    lp.add_argument("--root")
    cp = lib.add_parser("check")
    cp.add_argument("guitar")
    cp.add_argument("position")
    cp.add_argument("--root")
    rp = lib.add_parser("record")
    rp.add_argument("guitar")
    rp.add_argument("position")
    rp.add_argument("string", type=int)
    rp.add_argument("--device")
    rp.add_argument("--channel", type=int)
    rp.add_argument("--seconds", type=float, default=45.0)
    rp.add_argument("--root")
    a = p.parse_args(argv)
    return {"list": _list, "check": _check, "record": _record}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
