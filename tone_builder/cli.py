"""tone-builder command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import soundfile as sf
import yaml

from tone_builder import lead, library, recorder
from tone_builder.audio import load_mono
from tone_builder.strings import library_by_midi
from tone_builder.target import build_target
from tone_builder.validator import known_truth

MAX_ERROR_DB = 2.0   # spec: known-truth error <= 2 dB at -6 dB dominance, zero false positives


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


def _target(a) -> int:
    import json
    by_midi = library_by_midi(_root(a), a.guitar, a.position)
    t = build_target(load_mono(Path(a.disc)), load_mono(Path(a.lead)), set(by_midi))
    Path(a.out).write_text(json.dumps(t, indent=1))
    for n in t:
        m, sec = divmod(n["start_s"], 60)
        print(f"{n['name']:4s} {int(m)}:{sec:04.1f}  {sum(n['accepted'])} harmonics")
    print(f"{len(t)} target notes -> {a.out}")
    return 0 if t else 1


def _build(a) -> int:
    import json
    from tone_builder.build import Unresolved, build_tone
    from tone_builder.render import RenderError
    from tone_builder.devices.openrig import OpenRigDevice
    from tone_builder.report import to_markdown
    from tone_builder.research import load_research
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.device == "openrig":
        if not a.plugins_root:
            print("build: --plugins-root is required for openrig", file=sys.stderr)
            return 2
        device = OpenRigDevice(Path(a.plugins_root), out / "work")
    elif a.device == "ampero2":
        from tone_builder.devices.pedal import AmperoDevice
        if not a.work_patch:
            print("build: --work-patch is required for ampero2 (an empty patch to build and re-amp in)",
                  file=sys.stderr)
            return 2
        device = AmperoDevice(out / "work", a.work_patch)
    elif a.device == "mvave":
        from tone_builder.devices.pedal import MvaveDevice
        device = MvaveDevice(out / "work")
    else:
        print(f"build: unknown device {a.device!r} (openrig, ampero2, mvave)", file=sys.stderr)
        return 2
    try:
        lead_path = lead.resolve_lead(Path(a.disc), Path(a.lead) if a.lead else None, lead.tone_analyzer_separate)
    except lead.LeadError as e:
        print(f"build: {e}", file=sys.stderr)
        return 5
    try:
        res = build_tone(load_mono(Path(a.disc)), load_mono(lead_path),
                         library_by_midi(_root(a), a.guitar, a.position), load_research(Path(a.research)),
                         device, out / "work", a.name)
    except Unresolved as e:
        print("researched units with no model in the catalog:", *e.args[0], sep="\n  ", file=sys.stderr)
        return 3
    except (ValueError, RenderError) as e:
        print(f"build: {e}", file=sys.stderr)
        return 4
    (out / "preset.yaml").write_text(yaml.safe_dump(res["preset"], sort_keys=False, allow_unicode=True))
    (out / "report.json").write_text(json.dumps(res["report"], indent=1, default=str))
    (out / "report.md").write_text(to_markdown(res["report"]))
    (out / "target.json").write_text(json.dumps(res["target"], indent=1))
    print(to_markdown(res["report"]))
    print(f"-> {out}")
    return 0


def _verify(a) -> int:
    import json
    from tone_builder.verify import verify
    out = Path(a.build_dir)
    report = json.loads((out / "report.json").read_text())
    target = json.loads((out / "target.json").read_text())
    if a.device == "openrig":
        from tone_builder.devices.openrig import OpenRigRenderer
        saved = yaml.safe_load(Path(a.saved).read_text())
        renderer = OpenRigRenderer(saved["blocks"], out / "verify")
    elif a.device in ("ampero2", "mvave"):
        from tone_builder.devices.pedal import Runner
        from tone_builder.render import RenderError
        run = Runner(a.device)

        def renderer(src, dst):
            cmds = [["load", a.saved], ["reamp", str(src), str(dst), "--mono"]]
            if a.device == "ampero2":
                cmds.insert(1, ["input-source", "usb34"])   # edit buffer only; the saved patch keeps `input`
            for cmd in cmds:
                code, text = run(cmd)
                if code != 0:
                    raise RenderError(f"{a.device} {' '.join(cmd)}: {text.strip()[:300]}")
    else:
        print(f"verify: unknown device {a.device!r}", file=sys.stderr)
        return 2
    r = verify(report, target, renderer, out / "verify")
    print(json.dumps(r, indent=1))
    return 0 if r["match"] else 1


def _validate(a) -> int:
    notes = library.list_notes(_root(a), a.guitar, a.position)
    print("dominance  notes  harmonics/note  error dB  false positives")
    rc = 0
    for d in a.dominance:
        r = known_truth(notes, dominance_db=d)
        err = r["error_db"]
        print(f"{d:+6.0f} dB  {r['notes']:5d}  {r['harmonics_per_note'] or 0:14.1f}  "
              f"{err if err is not None else float('nan'):8.2f}  {r['false_positives']:15d}")
        if d == -6 and (err is None or err > MAX_ERROR_DB or r["false_positives"] > 0):
            rc = 1
    return rc


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
    tp = sub.add_parser("target", help="target notes: located on the separated track, level read on the record")
    tp.add_argument("disc")
    tp.add_argument("lead")
    tp.add_argument("--guitar", required=True)
    tp.add_argument("--position", required=True)
    tp.add_argument("--out", required=True)
    tp.add_argument("--root")
    vp = sub.add_parser("validate", help="known-truth check of the target reading")
    vp.add_argument("--guitar", default="prs-silver-sky-se")
    vp.add_argument("--position", default="pos5")
    vp.add_argument("--dominance", type=float, nargs="+", default=[-6.0, -3.0, 0.0, 6.0])
    vp.add_argument("--root")
    bp = sub.add_parser("build", help="build one tone on one device")
    bp.add_argument("--device", required=True)
    bp.add_argument("--disc", required=True)
    bp.add_argument("--lead", help="separated guitar track; without it, <disc dir>/lead.wav is used, "
                                   "or made with `tone-analyzer separate` (needs demucs)")
    bp.add_argument("--research", required=True)
    bp.add_argument("--guitar", required=True)
    bp.add_argument("--position", required=True)
    bp.add_argument("--name", required=True)
    bp.add_argument("--out", required=True)
    bp.add_argument("--plugins-root")
    bp.add_argument("--work-patch")
    bp.add_argument("--root")
    wp = sub.add_parser("verify", help="render what was saved on the device and compare with the build report")
    wp.add_argument("--device", required=True)
    wp.add_argument("--build-dir", required=True)
    wp.add_argument("--saved", required=True, help="openrig: saved preset YAML; ampero2: patch (A30-3); mvave: preset number")
    a = p.parse_args(argv)
    if a.group == "verify":
        return _verify(a)
    if a.group == "build":
        return _build(a)
    if a.group == "target":
        return _target(a)
    if a.group == "validate":
        return _validate(a)
    return {"list": _list, "check": _check, "record": _record}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
