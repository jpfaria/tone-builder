"""Can the middle position (both humbuckers in parallel) be computed from the bridge and neck libraries?
Model: A_mid(n) = | sb(n)*A_bridge(n) + g*sn(n)*A_neck(n) |, sign s(n) = sign(sin(n*pi*x/Lf)), x = pickup distance
from the saddle, Lf = vibrating length at the fret. x_b, x_n, g fitted on the even frets, tested on the odd ones.
Shapes only (each take has its own pluck strength): every spectrum is centred on its mean over the harmonics used."""
import itertools, json
from pathlib import Path
import numpy as np, soundfile as sf
from tone_analyzer.notes import harmonic_levels
from tone_analyzer.take import take_onset
R = Path("/Users/joao.faria/Projetos/github.com/jpfaria/tone-builder/biblioteca/prs-se-pauls-guitar")
L = 635.0; NH = 10
def levels(pos, midi):
    f = next((R / pos).glob(f"c4-{midi}-*.wav")); x, sr = sf.read(f)
    on = (take_onset(x, sr) or 0) / sr
    h = harmonic_levels(x, sr, on + 0.05, 440 * 2 ** ((midi - 69) / 12), dur_s=0.5, n_harm=NH)
    return np.array(h["level_db"], dtype=float)
midis = list(range(50, 66))
B = {m: levels("bridge-hb", m) for m in midis}; N = {m: levels("neck-hb", m) for m in midis}; M = {m: levels("middle-hb", m) for m in midis}
c = lambda v: v - v.mean()
rms = lambda a, b: float(np.sqrt(np.mean((c(a) - c(b)) ** 2)))
def predict(m, xb, xn, g_db, signed=True):
    Lf = L * 2 ** (-(m - 50) / 12); n = np.arange(1, NH + 1)
    ab, an = 10 ** (B[m] / 20), 10 ** ((N[m] + g_db) / 20)
    if not signed: return 10 * np.log10(ab ** 2 + an ** 2)
    sb, sn = np.sign(np.sin(n * np.pi * xb / Lf)), np.sign(np.sin(n * np.pi * xn / Lf))
    return 20 * np.log10(np.abs(sb * ab + sn * an) + 1e-9)
fit, test = midis[0::2], midis[1::2]
best = min(((np.mean([rms(predict(m, xb, xn, g), M[m]) for m in fit]), xb, xn, g)
            for xb in range(25, 70, 3) for xn in range(120, 175, 3) for g in range(-12, 13, 2)), key=lambda t: t[0])
_, xb, xn, g = best
out = {"fitted": {"bridge_mm": xb, "neck_mm": xn, "neck_gain_db": g, "fit_error_db": round(best[0], 2)},
       "test_frets_error_db": {
         "model (signed sum)": round(np.mean([rms(predict(m, xb, xn, g), M[m]) for m in test]), 2),
         "power sum, no phase": round(np.mean([rms(predict(m, xb, xn, g, signed=False), M[m]) for m in test]), 2),
         "just use the bridge": round(np.mean([rms(B[m], M[m]) for m in test]), 2),
         "just use the neck": round(np.mean([rms(N[m], M[m]) for m in test]), 2)},
       "bridge vs neck (how different the two real positions are)": round(np.mean([rms(B[m], N[m]) for m in test]), 2)}
print(json.dumps(out, indent=1))
