"""Hardware pedals driven through their own command lines (`ampero2`, `mvave`).

tone-builder never speaks a pedal protocol: it shells out to the device plugin's
CLI through an injectable runner. A digital model has no captures, so its
settings are the model defaults plus its gain knob swept over the range —
the counterpart of enumerating a NAM model's captures.

Rendering plays the DI through the pedal over USB audio (`reamp`):
- Ampero II: everything is built in a work patch (an empty slot) whose chain A input
  SOURCE is switched to USB OUT 3/4 with `ampero2 input-source usb34`; the preset's
  commands switch it back to `input` so the saved patch plays the guitar.
- MK-300: `mvave reamp` switches USB Audio to RESAMPLE and restores it.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

import numpy as np

from tone_builder.render import RenderError

GAIN_SWEEP = (0.2, 0.4, 0.6, 0.8)          # fraction of the gain knob range
GAIN_NAMES = ("gain", "drive", "sustain", "fuzz")


def resolve_exe(exe: str) -> list[str]:
    """The device CLIs are dependencies of this package: prefer the one installed beside the
    interpreter (the venv's bin need not be on PATH); otherwise let PATH decide."""
    parts = shlex.split(exe)
    beside = Path(sys.executable).parent / parts[0]
    if len(parts) == 1 and beside.is_file():
        return [str(beside)]
    return parts


class Runner:
    def __init__(self, exe: str):
        self.exe = exe

    def __call__(self, args: list[str]) -> tuple[int, str]:
        p = subprocess.run([*resolve_exe(self.exe), *args], capture_output=True, text=True)
        return p.returncode, (p.stdout or "") + (p.stderr or "")


def _eq_knob(freqs: dict[str, float], hz: float) -> str:
    return min(freqs, key=lambda k: abs(np.log2(freqs[k] / hz)))


def _hz(label: str) -> float | None:
    m = re.match(r"^([\d.]+)\s*(k?)Hz$", label.strip(), re.I)
    return float(m.group(1)) * (1000.0 if m.group(2) else 1.0) if m else None


class PedalDevice:
    exe = ""
    categories: dict[str, tuple[str, ...]] = {}

    def __init__(self, workdir: Path, runner=None):
        self.workdir = Path(workdir)
        self.run = runner or Runner(self.exe)

    # --- to be provided by each pedal -------------------------------------------------
    def find(self, category: str, unit: str) -> list[str]:
        raise NotImplementedError

    def knobs(self, category: str, model: str) -> list[dict]:
        """[{"index", "name", "default", "min", "max"}]"""
        raise NotImplementedError

    def apply_commands(self, blocks: list[dict]) -> list[list[str]]:
        raise NotImplementedError

    def eq_blocks(self, band_gains: dict[float, float]) -> list[dict]:
        raise NotImplementedError

    # --- shared -----------------------------------------------------------------------
    def _ok(self, args: list[str]) -> str:
        code, out = self.run(args)
        if code != 0:
            raise RenderError(f"{self.exe} {' '.join(args)} failed ({code}): {out.strip()[:300]}")
        return out

    def settings(self, category: str, model: str) -> list[dict]:
        ks = self.knobs(category, model)
        out = [{}]
        gain = next((k for k in ks if k["name"].strip().lower() in GAIN_NAMES), None)
        if gain is not None and gain["max"] > gain["min"]:
            for f in GAIN_SWEEP:
                out.append({gain["name"]: round(gain["min"] + f * (gain["max"] - gain["min"]))})
        return out

    def resolve(self, research: dict):
        from tone_builder.build import Option
        options: dict[str, list] = {}
        unresolved = []
        for b in research.get("blocks") or []:
            if b.get("absent_from_catalog"):
                continue
            klass = b["class"]
            found = []
            for cat in self.categories.get(klass, ()):
                found += [(cat, m) for m in self.find(cat, b["unit"])]
            if not found:
                unresolved.append(f"{klass}: {b['unit']}")
                continue
            for cat, model in found:
                for s in self.settings(cat, model):
                    label = ",".join(f"{k}={v}" for k, v in s.items())
                    options.setdefault(klass, []).append(Option(
                        name=f"{cat}:{model}[{label}]", klass=klass, unit=b["unit"],
                        blocks=[{"category": cat, "model": model, "knobs": s}]))
        return options, unresolved

    def renderer(self, blocks: list[dict]):
        def render(src: Path, dst: Path) -> None:
            for cmd in self.apply_commands(blocks):
                self._ok(cmd)
            self._ok(["reamp", str(src), str(dst), "--mono"])
            if not Path(dst).exists():
                raise RenderError(f"{self.exe} reamp wrote nothing: {dst}")
        return render

    def gain_reduction(self, blocks: list[dict], dis: list[Path], workdir: Path) -> float:
        from tone_builder.audio import load_mono
        from tone_builder.compressor import gain_reduction_db
        from tone_builder.render import render_note
        grs = [gain_reduction_db(load_mono(di), render_note(self.renderer(blocks), di, Path(workdir), f"gr{i:02d}"))
               for i, di in enumerate(dis)]
        return float(np.mean(grs)) if grs else 0.0

    def preset(self, blocks: list[dict], name: str) -> dict:
        return {"device": self.exe, "name": name, "blocks": blocks, "commands": self.apply_commands(blocks)}


class AmperoDevice(PedalDevice):
    exe = "ampero2"
    categories = {"single_drive": ("DRV",), "stacked_drives": ("DRV",), "boost": ("DRV",), "compressor": ("DYN",),
                  "amp": ("AMP", "PRE AMP"), "cab": ("CAB",), "eq": ("EQ",), "time_fx": ("DLY", "RVB", "MOD")}
    SLOTS = 12
    EQ_MODEL = "Graphic EQ"
    TIE = 0.05

    def __init__(self, workdir: Path, work_patch: str, runner=None):
        super().__init__(workdir, runner)
        self.work_patch = work_patch

    def find(self, category: str, unit: str) -> list[str]:
        code, out = self.run(["resolve", category, unit, "--json"])
        if code != 0:
            return []
        hits = json.loads(out.strip().splitlines()[-1]) if out.strip() else []
        if not hits or hits[0].get("score", 0) < 0.5:
            return []
        top = hits[0]["score"]
        return [h["name"] for h in hits if h["score"] >= top - self.TIE]

    def knobs(self, category: str, model: str) -> list[dict]:
        out = []
        for line in self._ok(["params", category, model]).splitlines():
            m = re.match(r"^\s*(\d+)\s+(.+?)\s+default=\s*(-?[\d.]+)\s+range=(-?[\d.]+)\.\.(-?[\d.]+)", line)
            if m:
                out.append({"index": int(m.group(1)), "name": m.group(2).strip(), "default": float(m.group(3)),
                            "min": float(m.group(4)), "max": float(m.group(5))})
        return out

    def apply_commands(self, blocks: list[dict]) -> list[list[str]]:
        if len(blocks) > self.SLOTS:
            raise RenderError(f"{len(blocks)} blocks do not fit the {self.SLOTS} slots")
        cmds = [["load", self.work_patch], ["input-source", "usb34"]]
        for i in range(self.SLOTS):
            if i < len(blocks):
                b = blocks[i]
                cmds.append(["model", str(i), b["category"], b["model"]])
                ks = {k["name"]: k["index"] for k in self.knobs(b["category"], b["model"])}
                for name, v in b["knobs"].items():
                    cmds.append(["param", str(i), str(ks[name]), f"{v:g}"])
            else:
                cmds.append(["model", str(i), "none"])
        cmds.append(["powers", "1", *["1" if i < len(blocks) else "0" for i in range(self.SLOTS)]])
        return cmds

    def eq_blocks(self, band_gains: dict[float, float]) -> list[dict]:
        freqs = {k["name"]: _hz(k["name"]) for k in self.knobs("EQ", self.EQ_MODEL) if _hz(k["name"])}
        knobs = {_eq_knob(freqs, hz): round(g) for hz, g in band_gains.items()}
        return [{"category": "EQ", "model": self.EQ_MODEL, "knobs": knobs}]


    def preset(self, blocks: list[dict], name: str) -> dict:
        cmds = [c for c in self.apply_commands(blocks) if c != ["input-source", "usb34"]]
        cmds.append(["input-source", "input"])
        return {"device": self.exe, "name": name, "blocks": blocks, "commands": cmds}


class MvaveDevice(PedalDevice):
    """MK-300: fixed chain WAH FX GATE DS AMP CAB EQ MOD DLY REV VOL; one model per block."""
    exe = "mvave"
    categories = {"single_drive": ("DS",), "stacked_drives": ("DS", "FX"), "boost": ("FX", "DS"),
                  "compressor": ("FX",), "amp": ("AMP",), "cab": ("CAB",), "eq": ("EQ",),
                  "time_fx": ("DLY", "REV", "MOD")}
    BLOCKS = ("WAH", "FX", "GATE", "DS", "AMP", "CAB", "EQ", "MOD", "DLY", "REV", "VOL")
    EQ_MODEL = "Normal EQ 10"
    TIE = 0.05

    def find(self, category: str, unit: str) -> list[str]:
        code, out = self.run(["resolve", category, unit])
        if code != 0:
            return []
        hits = []
        for line in out.splitlines():
            m = re.match(r"^\s*([\d.]+)\s+(\d+)\s+(\S.*)$", line)
            if m:
                hits.append((float(m.group(1)), m.group(3).strip()))
        if not hits or hits[0][0] < 0.5:
            return []
        return [n for s, n in hits if s >= hits[0][0] - self.TIE]

    def knobs(self, category: str, model: str) -> list[dict]:
        out = []
        for line in self._ok(["params", category, model]).splitlines():
            m = re.match(r"^\s*(\d+)\s+(\S+)\s+default\s+(\S+)", line)
            if m:
                d = None if m.group(3) == "?" else float(m.group(3))
                out.append({"index": int(m.group(1)), "name": m.group(2), "default": d, "min": 0.0, "max": 100.0})
        return out

    def settings(self, category: str, model: str) -> list[dict]:
        return [{}] if category == "EQ" else super().settings(category, model)

    def apply_commands(self, blocks: list[dict]) -> list[list[str]]:
        used = {}
        for b in blocks:
            if b["category"] in used:
                raise RenderError(f"the MK-300 has one {b['category']} block; two were asked")
            used[b["category"]] = b
        cmds = []
        for blk in self.BLOCKS:
            b = used.get(blk)
            if b is None:
                if blk != "VOL":
                    cmds.append(["enable", blk, "off"])
                continue
            cmds.append(["model", blk, b["model"]])
            for name, v in b["knobs"].items():
                cmds.append(["param", blk, name, f"{v:g}"])
            cmds.append(["enable", blk, "on"])
        return cmds

    def eq_blocks(self, band_gains: dict[float, float]) -> list[dict]:
        freqs = {k["name"]: _hz(k["name"]) for k in self.knobs("EQ", self.EQ_MODEL) if _hz(k["name"])}
        knobs = {_eq_knob(freqs, hz): round(g) for hz, g in band_gains.items()}
        return [{"category": "EQ", "model": self.EQ_MODEL, "knobs": knobs}]
