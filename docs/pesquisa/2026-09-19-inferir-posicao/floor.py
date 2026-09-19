"""Repeatability floor: the same notes, same string, same pickup position, two independent takes
(bridge-split: strings 3 and 2 were played once under the wrong string's turn and once under their own)."""
import numpy as np, soundfile as sf
from pathlib import Path
from tone_analyzer.notes import harmonic_levels
from tone_builder import recorder, library
T = Path("/Users/joao.faria/Projetos/github.com/jpfaria/tone-builder/biblioteca/prs-se-pauls-guitar/bridge-split/_takes")
c = lambda v: v - v.mean()
def notes(path, string):
    x, sr = sf.read(path, dtype="float32"); out = {}
    for midi, a, end in recorder.note_spans_all(x, sr, library.expected_midis(string)):
        h = harmonic_levels(x, sr, a / sr + 0.05, 440 * 2 ** ((midi - 69) / 12), dur_s=0.5, n_harm=NH)
        if h: out[midi] = np.array(h["level_db"], dtype=float)
    return out
for NH in (10, 6):
    for real, wrong, string in (("c3.wav", "wrong-string/c4.wav", 3), ("c2.wav", "wrong-string/c3.wav", 2)):
        a, b = notes(T / real, string), notes(T / wrong, string)
        common = sorted(set(a) & set(b))
        e = [float(np.sqrt(np.mean((c(a[m]) - c(b[m])) ** 2))) for m in common]
        print(f"harmonics 1-{NH}  string {string}: {len(common)} notes, take-to-take {np.mean(e):.2f} dB (median {np.median(e):.2f})")
