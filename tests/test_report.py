from tone_builder.battery import CLASSES
from tone_builder.report import build, to_markdown

OK_MARGIN = {0: {"peak_db": -4, "saturated": 0}, 12: {"peak_db": -2, "saturated": 0}, 18: {"peak_db": -2, "saturated": 0}}


def _measured():
    return {c: {"status": "measured", "sourced": {"best": "x", "test_db": 8.0, "accepted": False},
                "unsourced_best": None, "reason": None} for c in CLASSES}


def test_everything_measured_with_margin_is_pronto():
    rep = build(_measured(), OK_MARGIN, 8.2)
    assert rep["status"] == "pronto"
    assert "pronto" in to_markdown(rep)


def test_missing_class_is_parcial_and_never_says_pronto():
    b = _measured()
    b["cab"] = {"status": "no_candidate", "sourced": None, "unsourced_best": None, "reason": None}
    rep = build(b, OK_MARGIN, 8.2)
    assert rep["status"] == "parcial"
    assert rep["missing"] == ["cab"]
    assert "pronto" not in to_markdown(rep)


def test_class_with_a_reason_counts():
    b = _measured()
    b["time_fx"] = {"status": "no_candidate", "sourced": None, "unsourced_best": None,
                    "reason": "no source for the record"}
    assert build(b, OK_MARGIN, 8.2)["status"] == "pronto"


def test_saturation_is_parcial():
    m = {**OK_MARGIN, 18: {"peak_db": 0.0, "saturated": 12}}
    rep = build(_measured(), m, 8.2)
    assert rep["status"] == "parcial"
    assert "pronto" not in to_markdown(rep)
