from tone_builder import cifra

YAML = """source: https://www.cifraclub.com.br/green-day/welcome-to-paradise/
tuning_semitones: -1
chords:
  - name: Eb5
    shape: {5: 7, 4: 9, 3: 9}
  - name: Eb5 low
    shape: {6: 0, 5: 2, 4: 2}
  - name: Db5
    shape: {5: 5, 4: 7, 3: 7}
"""


def _chords(tmp_path):
    p = tmp_path / "cifra.yaml"
    p.write_text(YAML)
    return cifra.load(p)


def test_shapes_become_the_pitches_the_record_sounds(tmp_path):
    ch = {c["name"]: c for c in _chords(tmp_path)}
    assert ch["Eb5"]["midis"] == [51, 58, 63]
    assert ch["Eb5"]["shape"] == [(5, 51), (4, 58), (3, 63)]
    assert ch["Eb5 low"]["midis"] == [39, 46, 51]


def test_a_detected_attack_is_the_cifra_chord_holding_its_pitch_classes(tmp_path):
    chords = _chords(tmp_path)
    assert cifra.match([51, 58], chords)["name"] == "Eb5"
    assert cifra.match([39, 46], chords)["name"] == "Eb5 low"     # same pitch classes, lower register
    assert cifra.match([49, 56], chords)["name"] == "Db5"
    assert cifra.match([58, 63, 67], chords) is None               # a G is in no chord of the song
    assert cifra.match([51], chords) is None


def test_a_shape_below_the_standard_tuned_library_is_not_playable(tmp_path):
    ch = {c["name"]: c for c in _chords(tmp_path)}
    by_midi = {}
    for c in ch.values():
        for s, m in c["shape"]:
            if m >= 40:
                by_midi.setdefault(m, []).append(tmp_path / f"c{s}-{m}-C4.wav")
    assert cifra.playable(ch["Eb5"], by_midi)
    assert not cifra.playable(ch["Eb5 low"], by_midi)            # low Eb2 is under the open E
