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


STATEMENT = {"who": "the player", "date": "2026-09-17", "channel": "private message", "quote": "AC30 + Fender. compressor."}


def test_a_first_hand_statement_is_a_source_even_without_a_url():
    r = {**GOOD, "blocks": [{"class": "amp", "unit": "Vox AC30", "era": "record", "statement": STATEMENT}]}
    assert validate(r) == []
    assert sourced_units(r) == {"amp": {"Vox AC30"}}


def test_a_statement_with_no_quote_is_not_a_source():
    r = {**GOOD, "blocks": [{"class": "amp", "unit": "Vox AC30", "era": "record",
                             "statement": {**STATEMENT, "quote": ""}}]}
    assert len(validate(r)) == 1


def test_a_class_named_without_a_unit_is_open_to_the_whole_class():
    r = {**GOOD, "blocks": [{"class": "compressor", "unit": "any", "era": "record", "statement": STATEMENT}]}
    assert validate(r) == []


def test_time_fx_cannot_be_open_to_the_whole_class():
    r = {**GOOD, "blocks": [{"class": "time_fx", "unit": "any", "era": "record", "statement": STATEMENT}]}
    assert any("time_fx" in e for e in validate(r))
