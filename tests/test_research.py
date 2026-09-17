from tone_builder.research import sourced_units, validate

GOOD = {
    "song": "s", "part": "solo",
    "blocks": [
        {"class": "single_drive", "unit": "Ibanez Tube Screamer", "era": "record",
         "sources": ["https://example.com/a"]},
        {"class": "amp", "unit": "Dumble ODS", "era": "record", "sources": ["https://example.com/b"]},
    ],
    "not_found": [{"class": "time_fx", "searched": ["https://example.com/c"]}],
}


def test_valid_research_has_no_errors():
    assert validate(GOOD) == []


def test_block_without_url_is_an_error():
    r = {**GOOD, "blocks": [{**GOOD["blocks"][0], "sources": ["forum said so"]}]}
    assert len(validate(r)) == 1


def test_tour_rig_is_not_a_record_source():
    r = {**GOOD, "blocks": [{**GOOD["blocks"][0], "era": "tour"}]}
    assert len(validate(r)) == 1


def test_unknown_class_is_an_error():
    r = {**GOOD, "blocks": [{**GOOD["blocks"][0], "class": "vibes"}]}
    assert len(validate(r)) == 1


def test_sourced_units_by_class():
    assert sourced_units(GOOD) == {"single_drive": {"Ibanez Tube Screamer"}, "amp": {"Dumble ODS"}}
