from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from tests.synth import note, write
from tone_builder.devices.openrig import OpenRigDevice, OpenRigRenderer, find_models, settings
from tone_builder.render import RenderError


def _plugins(root: Path) -> Path:
    def man(kind, name, data):
        d = root / kind / name
        d.mkdir(parents=True)
        (d / "manifest.yaml").write_text(yaml.safe_dump(data))
    man("nam", "ts", {"id": "nam_ibanez_tube_screamer_a2", "display_name": "Ibanez Tube Screamer", "brand": "fortin",
                      "type": "gain_pedal", "captures": [{"values": {"drive": 3.0, "tone": 8.0}, "file": "a"},
                                                         {"values": {"drive": 8.0, "tone": 5.0}, "file": "b"}]})
    man("nam", "dumble", {"id": "nam_dumble_ods_john_mayer_a2", "display_name": "Dumble ODS John Mayer",
                          "brand": "dumble", "type": "amp", "captures": [{"values": {"character": "hiz"}, "file": "c"}]})
    man("ir", "ac30", {"id": "ir_vox_ac30_bright_channel", "display_name": "AC30 Bright Channel", "brand": "vox",
                       "type": "cab", "parameters": [{"name": "preset", "values": ["beta91", "441_on_axis"]}]})
    return root


def test_captures_are_the_settings_not_the_cartesian_product(tmp_path):
    dev = OpenRigDevice(_plugins(tmp_path), tmp_path / "w")
    assert settings(dev.catalog["nam_ibanez_tube_screamer_a2"]) == [{"drive": 3.0, "tone": 8.0}, {"drive": 8.0, "tone": 5.0}]


def test_research_resolves_by_name_and_type(tmp_path):
    dev = OpenRigDevice(_plugins(tmp_path), tmp_path / "w")
    assert find_models(dev.catalog, "Ibanez Tube Screamer", ("gain_pedal",)) == ["nam_ibanez_tube_screamer_a2"]
    assert find_models(dev.catalog, "Ibanez Tube Screamer", ("amp",)) == []
    r = {"blocks": [{"class": "single_drive", "unit": "Ibanez Tube Screamer"},
                    {"class": "amp", "unit": "Dumble ODS John Mayer"},
                    {"class": "cab", "unit": "Vox AC30 Bright"},
                    {"class": "boost", "unit": "Klon Centaur"}]}
    opts, unresolved = dev.resolve(r)
    assert len(opts["single_drive"]) == 2
    assert opts["single_drive"][0].blocks[0] == {"type": "gain", "enabled": True,
                                                 "model": "nam_ibanez_tube_screamer_a2",
                                                 "params": {"drive": 3.0, "tone": 8.0}}
    assert len(opts["cab"]) == 2 and opts["amp"][0].blocks[0]["type"] == "amp"
    assert unresolved == ["boost: Klon Centaur"]


def test_ignored_block_rejects_the_render(tmp_path):
    di = write(tmp_path / "di.wav", note(62, start_s=0.02))

    def fake(cmd, **kw):
        Path(cmd[cmd.index("--output") + 1]).write_bytes(b"x")
        return SimpleNamespace(returncode=0, stdout="warning: ignoring block nam_x (unknown model)", stderr="")
    with pytest.raises(RenderError):
        OpenRigRenderer([], tmp_path, "render", fake)(di, tmp_path / "wet.wav")


def test_input_is_resampled_to_48k(tmp_path):
    import soundfile as sf
    di = tmp_path / "di44.wav"
    sf.write(str(di), note(62, start_s=0.02)[::2], 24000)
    seen = {}

    def fake(cmd, **kw):
        seen["sr"] = sf.info(cmd[cmd.index("--input") + 1]).samplerate
        Path(cmd[cmd.index("--output") + 1]).write_bytes(b"x")
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    OpenRigRenderer([], tmp_path, "render", fake)(di, tmp_path / "wet.wav")
    assert seen["sr"] == 48000


def test_eq_uses_the_plugin(tmp_path):
    dev = OpenRigDevice(_plugins(tmp_path), tmp_path / "w")
    b = dev.eq_blocks({250.0: 1.5, 2000.0: -2.0})[0]
    assert b["model"] == "lv2_x42_fil4"
    assert b["params"] == {"freq1": 250.0, "gain1": 1.5, "q1": 0.7, "freq2": 2000.0, "gain2": -2.0, "q2": 0.7}


def test_an_open_class_resolves_to_every_model_of_that_class(tmp_path):
    dev = OpenRigDevice(_plugins(tmp_path), tmp_path / "w")
    opts, unresolved = dev.resolve({"blocks": [{"class": "single_drive", "unit": "any"}]})
    assert unresolved == [] and {o.unit for o in opts["single_drive"]} == {"any"}
    assert len(opts["single_drive"]) == 2


def test_params_set_by_ear_override_the_model_defaults(tmp_path):
    dev = OpenRigDevice(_plugins(tmp_path), tmp_path / "w")
    opts, _ = dev.resolve({"blocks": [{"class": "cab", "unit": "Vox AC30 Bright", "params": {"preset": "beta91", "mix": 24.0}}]})
    assert [o.blocks[0]["params"] for o in opts["cab"]] == [{"preset": "beta91", "mix": 24.0}]
