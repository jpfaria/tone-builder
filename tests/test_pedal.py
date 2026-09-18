import json

import pytest

from tone_builder.devices.pedal import AmperoDevice, MvaveDevice
from tone_builder.render import RenderError


class FakeAmpero:
    def __init__(self):
        self.calls = []

    def __call__(self, args):
        self.calls.append(args)
        if args[0] == "resolve":
            if "Bluesbreaker" in args[2] or "BluesBreaker" in args[2]:
                return 0, json.dumps([{"name": "Blues Butter", "score": 0.82}, {"name": "Grand Driver", "score": 0.4}])
            if "Dumble" in args[2] and args[1] == "AMP":
                return 0, json.dumps([{"name": "Dumbell ODS 1", "score": 0.812}, {"name": "Dumbell ODS 2", "score": 0.812}])
            return 0, json.dumps([{"name": "Nope", "score": 0.2}])
        if args[0] == "params" and args[1] == "EQ":
            return 0, "\n".join(f"{i:2d} {f:<16} default=     0 range=-12..12 type=0" for i, f in
                                enumerate(["31Hz", "63Hz", "125Hz", "250Hz", "500Hz", "1kHz", "2kHz", "4kHz", "8kHz", "16kHz"]))
        if args[0] == "params":
            return 0, " 0 Gain             default=    60 range=0..100 type=0\n 1 Tone             default=    50 range=0..100 type=0"
        return 0, ""


def test_ampero_resolves_ties_and_sweeps_gain(tmp_path):
    dev = AmperoDevice(tmp_path, "A60-5", FakeAmpero())
    r = {"blocks": [{"class": "amp", "unit": "Dumble ODS"}, {"class": "single_drive", "unit": "Marshall BluesBreaker"},
                    {"class": "boost", "unit": "Klon"}]}
    opts, unresolved = dev.resolve(r)
    assert {o.blocks[0]["model"] for o in opts["amp"]} == {"Dumbell ODS 1", "Dumbell ODS 2"}
    assert [o.blocks[0]["knobs"] for o in opts["single_drive"]] == [{}, {"Gain": 20}, {"Gain": 40}, {"Gain": 60}, {"Gain": 80}]
    assert unresolved == ["boost: Klon"]


def test_ampero_builds_inside_the_reamp_patch_and_empties_the_rest(tmp_path):
    fake = FakeAmpero()
    dev = AmperoDevice(tmp_path, "A60-5", fake)
    cmds = dev.apply_commands([{"category": "DRV", "model": "Blues Butter", "knobs": {"Gain": 40}},
                               {"category": "AMP", "model": "Dumbell ODS 1", "knobs": {}}])
    assert cmds[0] == ["load", "A60-5"]
    assert ["model", "0", "DRV", "Blues Butter"] in cmds and ["param", "0", "0", "40"] in cmds
    assert ["model", "11", "none"] in cmds
    assert cmds[-1] == ["powers", "1", "1", "1"] + ["0"] * 10


def test_ampero_render_fails_when_reamp_fails(tmp_path):
    def runner(args):
        return (3, "no signal: is the patch's input source USB OUT 3/4?") if args[0] == "reamp" else FakeAmpero()(args)
    dev = AmperoDevice(tmp_path, "A60-5", runner)
    with pytest.raises(RenderError, match="USB OUT 3/4"):
        dev.renderer([])(tmp_path / "di.wav", tmp_path / "wet.wav")


def test_ampero_eq_maps_bands_to_nearest_knob(tmp_path):
    dev = AmperoDevice(tmp_path, "A60-5", FakeAmpero())
    assert dev.eq_blocks({250.0: 2.4, 700.0: -1.6, 2000.0: 0.0, 5000.0: 3.0})[0]["knobs"] == \
        {"250Hz": 2, "500Hz": -2, "2kHz": 0, "4kHz": 3}


class FakeMvave:
    def __call__(self, args):
        if args[0] == "resolve":
            return (0, "0.92    1  2TS8\n0.50    6  7M-VAVE_TS1\n") if "Screamer" in args[2] else (0, "")
        if args[0] == "params":
            return 0, " 0  Gain         default ?\n 1  Level        default ?"
        return 0, ""


def test_mvave_resolve_and_fixed_chain(tmp_path):
    dev = MvaveDevice(tmp_path, FakeMvave())
    opts, unresolved = dev.resolve({"blocks": [{"class": "single_drive", "unit": "Ibanez Tube Screamer"}]})
    assert {o.blocks[0]["model"] for o in opts["single_drive"]} == {"2TS8"}
    cmds = dev.apply_commands([{"category": "DS", "model": "2TS8", "knobs": {"Gain": 40}}])
    assert ["enable", "AMP", "off"] in cmds and ["model", "DS", "2TS8"] in cmds and ["enable", "DS", "on"] in cmds
    with pytest.raises(RenderError):
        dev.apply_commands([{"category": "DS", "model": "a", "knobs": {}}, {"category": "DS", "model": "b", "knobs": {}}])


def test_ampero_sets_usb_input_for_reamp_and_restores_it_in_the_preset(tmp_path):
    dev = AmperoDevice(tmp_path, "A58-2", FakeAmpero())
    blocks = [{"category": "DRV", "model": "Blues Butter", "knobs": {}}]
    cmds = dev.apply_commands(blocks)
    assert cmds[:2] == [["load", "A58-2"], ["input-source", "usb34"]]
    preset = dev.preset(blocks, "x")
    assert preset["commands"][-1] == ["input-source", "input"]
    assert ["input-source", "usb34"] not in preset["commands"]


def test_runner_prefers_the_cli_installed_beside_the_interpreter(tmp_path, monkeypatch):
    """mvave/ampero2 are dependencies: they live in this venv, which need not be on PATH."""
    import sys

    from tone_builder.devices.pedal import resolve_exe

    fake_python = tmp_path / "bin" / "python"
    fake_python.parent.mkdir()
    fake_python.write_text("")
    (tmp_path / "bin" / "mvave").write_text("")
    monkeypatch.setattr(sys, "executable", str(fake_python))
    assert resolve_exe("mvave") == [str(tmp_path / "bin" / "mvave")]
    assert resolve_exe("ampero2") == ["ampero2"]                  # not in the venv: PATH decides
    assert resolve_exe("python -m mvave") == ["python", "-m", "mvave"]


def test_runner_retries_a_device_call_that_hangs(tmp_path):
    # MK-300, 18/09/2026: `mvave enable EQ on` hung 1h40 in rtmidi close_port and froze the build.
    from tone_builder.devices.pedal import Runner
    flag = tmp_path / "hung-once"
    exe = tmp_path / "dev"
    exe.write_text(f"#!/bin/sh\nif [ ! -e {flag} ]; then touch {flag}; sleep 30; fi\necho ok $@\n")
    exe.chmod(0o755)
    code, out = Runner(str(exe), timeout_s=1)(["enable", "EQ", "on"])
    assert code == 0 and "ok enable EQ on" in out


def test_runner_gives_up_on_a_device_that_always_hangs(tmp_path):
    from tone_builder.devices.pedal import Runner
    exe = tmp_path / "dev"
    exe.write_text("#!/bin/sh\nsleep 30\n")
    exe.chmod(0o755)
    code, out = Runner(str(exe), timeout_s=0.5, attempts=2)(["show"])
    assert code != 0 and "timed out" in out
