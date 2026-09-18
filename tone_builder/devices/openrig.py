"""OpenRig device: catalog from the plugin manifests, render with openrig-render.

Known traps (measured 15-16/09):
- an invalid block is ignored silently and the renderer exits 0 -> "ignoring" in
  its output rejects the candidate;
- NAM model ids carry the `nam_` prefix (the manifest `id`);
- enumerate the manifest `captures:`, never the cartesian product of parameters;
- the renderer does not resample its input -> the DI is brought to 48 kHz first.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
import yaml

from tone_builder.audio import SR
from tone_builder.render import RenderError

DEFAULT_RENDER = "/Applications/OpenRig.app/Contents/MacOS/openrig-render"

# manifest `type` -> chain block `type`
BLOCK_TYPE = {"gain_pedal": "gain", "amp": "amp", "preamp": "preamp", "cab": "cab", "dyn": "dynamics",
              "filter": "filter", "mod": "modulation", "delay": "delay", "reverb": "reverb", "body": "body"}


def render_bin() -> str:
    return os.environ.get("OPENRIG_RENDER", DEFAULT_RENDER)


def load_catalog(plugins_root: Path) -> dict[str, dict]:
    out = {}
    for m in sorted(Path(plugins_root).glob("*/*/manifest.yaml")):
        d = yaml.safe_load(m.read_text()) or {}
        if d.get("id"):
            d["_dir"] = str(m.parent)
            out[d["id"]] = d
    return out


def settings(manifest: dict) -> list[dict]:
    """Every real setting of a model: its captures, or one axis at a time for
    grab-bag IRs, or the defaults."""
    caps = manifest.get("captures")
    if caps:
        return [dict(c.get("values") or {}) for c in caps]
    params = manifest.get("parameters") or []
    if len(params) == 1 and params[0].get("values"):
        return [{params[0]["name"]: v} for v in params[0]["values"]]
    return [{}]


def block(manifest: dict, params: dict | None = None) -> dict:
    t = BLOCK_TYPE.get(manifest.get("type"))
    if t is None:
        raise ValueError(f"no chain block type for manifest type {manifest.get('type')!r}")
    return {"type": t, "enabled": True, "model": manifest["id"], "params": dict(params or {})}


def chain(blocks: list[dict], name: str = "tone-builder") -> dict:
    return {"id": name, "name": name, "blocks": blocks}


class OpenRigRenderer:
    def __init__(self, blocks: list[dict], workdir: Path, binary: str | None = None, run=subprocess.run):
        self.blocks = blocks
        self.workdir = Path(workdir)
        self.binary = binary or render_bin()
        self.run = run

    def __call__(self, src: Path, dst: Path) -> None:
        self.workdir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.workdir) as tmp:
            chain_path = Path(tmp) / "chain.yaml"
            chain_path.write_text(yaml.safe_dump(chain(self.blocks), sort_keys=False))
            x, sr = sf.read(str(src), always_2d=False)
            inp = Path(src)
            if sr != SR:
                from tone_builder.audio import to_mono_48k
                inp = Path(tmp) / "di48k.wav"
                sf.write(str(inp), to_mono_48k(x, sr).astype(np.float32), SR, subtype="FLOAT")
            r = self.run([self.binary, "--chain", str(chain_path), "--input", str(inp), "--output", str(dst)],
                         capture_output=True, text=True)
            text = ((r.stdout or "") + (r.stderr or "")).lower()
            if "ignoring" in text:
                raise RenderError(f"openrig-render ignored a block: {text.strip()[:300]}")
            if r.returncode != 0 or not Path(dst).exists():
                raise RenderError(f"openrig-render failed ({r.returncode}): {text.strip()[:300]}")


CLASS_TYPES = {
    "single_drive": ("gain_pedal",), "stacked_drives": ("gain_pedal",), "boost": ("gain_pedal",),
    "compressor": ("dyn",), "amp": ("amp", "preamp"), "cab": ("cab",), "eq": ("filter",),
    "time_fx": ("delay", "reverb", "mod"),
}
# Compressor sweep for LV2 dynamics without captures. Only settings whose gain
# reduction measures >= 3 dB count (round 8: -40/-30/-20 dB removed 1.2/0.1/0.0 dB
# on the quiet library DI; -70 dB with ratio 8 removed 23 dB).
COMP_THRESHOLDS_DB = (-30.0, -50.0, -70.0)
COMP_RATIOS = (4.0, 8.0)
EQ_MODEL = "lv2_x42_fil4"   # plugin first; accepts freqN/gainN/qN in openrig-render (measured 16/09)
EQ_Q = 0.7


def _tokens(text: str) -> set[str]:
    import re
    import unicodedata
    t = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).casefold()
    return set(re.findall(r"[a-z0-9]+", t))


def find_models(catalog: dict[str, dict], unit: str, types: tuple[str, ...]) -> list[str]:
    """Models whose id, name or brand contain every word of the researched unit."""
    want = _tokens(unit)
    out = []
    for mid, m in catalog.items():
        if m.get("type") not in types:
            continue
        have = _tokens(" ".join(str(m.get(k) or "") for k in ("id", "display_name", "brand")))
        if want and want <= have:
            out.append(mid)
    return sorted(out)


def lv2_ports(manifest: dict) -> set[str]:
    import re
    d = Path(manifest.get("_dir", ""))
    symbols: set[str] = set()
    for ttl in d.glob("data/**/*.ttl"):
        symbols |= set(re.findall(r'lv2:symbol\s+"([^"]+)"', ttl.read_text(errors="ignore")))
    return symbols


def compressor_settings(manifest: dict) -> list[dict]:
    ports = lv2_ports(manifest)
    thr = next((p for p in ("thr", "threshold") if p in ports), None)
    rat = next((p for p in ("rat", "ratio") if p in ports), None)
    if not (thr and rat):
        return settings(manifest)
    mak = next((p for p in ("mak", "makeup") if p in ports), None)
    out = []
    for t in COMP_THRESHOLDS_DB:
        for r in COMP_RATIOS:
            s = {thr: t, rat: r}
            if mak:
                s[mak] = 0.0
            out.append(s)
    return out


class OpenRigDevice:
    jobs = int(os.environ.get("TONE_BUILDER_JOBS", "6"))   # offline renders: safe in parallel
    def __init__(self, plugins_root: Path, workdir: Path, binary: str | None = None, run=subprocess.run):
        self.catalog = load_catalog(plugins_root)
        self.workdir = Path(workdir)
        self.binary = binary
        self.run = run

    def resolve(self, research: dict):
        from tone_builder.build import Option
        options: dict[str, list] = {}
        unresolved = []
        for b in research.get("blocks") or []:
            if b.get("absent_from_catalog"):
                continue
            klass = b["class"]
            types = CLASS_TYPES.get(klass, ())
            models = (sorted(k for k, m in self.catalog.items() if m.get("type") in types) if b["unit"] == "any"
                      else find_models(self.catalog, b["unit"], types))
            if not models:
                unresolved.append(f"{klass}: {b['unit']}")
                continue
            for mid in models:
                m = self.catalog[mid]
                sets = compressor_settings(m) if klass == "compressor" else settings(m)
                if b.get("params"):
                    sets = [dict(b["params"])]            # fixed by ear in the research: shipped as given
                for s in sets:
                    label = ",".join(f"{k}={v}" for k, v in s.items())
                    options.setdefault(klass, []).append(
                        Option(name=f"{mid}[{label}]", klass=klass, unit=b["unit"], blocks=[block(m, s)]))
        return options, unresolved

    def renderer(self, blocks: list[dict]):
        return OpenRigRenderer(blocks, self.workdir / "chains", self.binary, self.run)

    def gain_reduction(self, blocks: list[dict], dis: list[Path], workdir: Path) -> float:
        from tone_builder.audio import load_mono
        from tone_builder.compressor import gain_reduction_db
        from tone_builder.render import render_note
        grs = []
        for i, di in enumerate(dis):
            wet = render_note(self.renderer(blocks), di, Path(workdir), f"gr{i:02d}")
            grs.append(gain_reduction_db(load_mono(di), wet))
        return float(np.mean(grs)) if grs else 0.0

    def eq_blocks(self, band_gains: dict[float, float]) -> list[dict]:
        params: dict = {}
        for n, (hz, g) in enumerate(sorted(band_gains.items()), start=1):
            params.update({f"freq{n}": float(hz), f"gain{n}": float(g), f"q{n}": EQ_Q})
        return [{"type": "filter", "enabled": True, "model": EQ_MODEL, "params": params}]

    def preset(self, blocks: list[dict], name: str) -> dict:
        return {"version": 1, "id": name, "name": name, "instrument": "electric_guitar", "blocks": blocks}
