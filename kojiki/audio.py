"""Procedural soundtrack for KOJIKI — every sound is synthesized here, cued from timeline.json."""
import json
import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 48000
TL = json.load(open('timeline.json'))
C = TL['cues']
DUR = TL['duration'] + 0.5
N = int(DUR * SR)
rng = np.random.default_rng(7)

music = np.zeros((N, 2))   # reverberant bus
dry = np.zeros((N, 2))     # drier bus (impacts, fx)


def tt(d):
    return np.arange(int(d * SR)) / SR


def place(bus, t0, x, gain=1.0, pan=0.0):
    """mix mono or stereo x into bus at time t0 with constant-power pan (-1..1)."""
    i = int(t0 * SR)
    if i >= N:
        return
    if x.ndim == 1:
        a = (pan + 1) * np.pi / 4
        x = np.stack([x * np.cos(a), x * np.sin(a)], 1)
    j = min(N, i + len(x))
    bus[i:j] += x[: j - i] * gain


def filt(x, kind, f, order=2):
    sos = signal.butter(order, f, btype=kind, fs=SR, output='sos')
    return signal.sosfilt(sos, x, axis=0)


def noise(d):
    return rng.standard_normal(int(d * SR))


def brown(d):
    x = np.cumsum(noise(d))
    x = filt(x, 'high', 15)
    return x / (np.abs(x).max() + 1e-9)


def env_ar(n, a, r):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-np.maximum(0, t - a) / r)


def swell(d, curve=2.0):
    t = np.linspace(0, 1, int(d * SR))
    return t ** curve


# ---------------------------------------------------------------- instruments
def taiko(f0=62, big=1.0, d=2.2):
    t = tt(d)
    f = f0 * (1 + 1.2 * np.exp(-t * 35))
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * (5.5 / big))
    over = np.sin(ph * 2.31) * np.exp(-t * 18) * 0.35
    click = filt(noise(d), 'low', 2500) * np.exp(-t * 70) * 0.5
    skin = filt(noise(d), 'band', [150, 600]) * np.exp(-t * 14) * 0.25
    return np.tanh((body + over + click + skin) * 1.4)


def boom(d=5.0, f0=46):
    t = tt(d)
    f = f0 * (1 + 0.6 * np.exp(-t * 4))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 0.9) * np.minimum(1, t * 200)


def rin(f0, d=7.0):
    """temple bowl / bell: inharmonic partials with beating"""
    t = tt(d)
    out = np.zeros_like(t)
    for r, a, dec in [(1, 1, .6), (2.76, .5, 1.1), (5.40, .3, 1.8), (8.93, .15, 2.8), (13.34, .06, 4)]:
        for det in (-0.6, 0.6):
            out += a * np.sin(2 * np.pi * (f0 * r + det * r) * t) * np.exp(-t * dec)
    return out * np.minimum(1, t * 800) * 0.3


def suzu(d=1.2):
    """kagura bells: a shimmering cluster"""
    t = tt(d)
    out = np.zeros_like(t)
    for k in range(9):
        f = rng.uniform(3200, 7800)
        out += np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) * np.exp(-t * rng.uniform(4, 9)) * (0.6 + 0.4 * np.sin(2 * np.pi * rng.uniform(15, 30) * t))
    return out * np.minimum(1, t * 300) * 0.12


def shakuhachi(freq, d, vib=5.2, bend=True):
    t = tt(d)
    f = freq * np.ones_like(t)
    if bend:  # meri: scoop up into the note
        f *= 1 - 0.04 * np.exp(-t * 7)
    f *= 1 + 0.008 * np.sin(2 * np.pi * vib * t) * np.clip((t - 0.4) / 0.8, 0, 1)
    ph = 2 * np.pi * np.cumsum(f) / SR
    tone = np.sin(ph) + 0.25 * np.sin(2 * ph) + 0.08 * np.sin(3 * ph)
    breath = filt(noise(d), 'band', [freq * 0.8, min(freq * 4, 9000)]) * 0.35
    e = np.minimum(1, t / 0.18) * np.minimum(1, (d - t) / 0.5)
    e *= 0.85 + 0.15 * np.sin(2 * np.pi * 0.7 * t)
    breath_e = 0.25 + 0.75 * np.exp(-t * 3)
    return (tone * e + breath * e * breath_e) * 0.25


def voice_pad(freqs, d, bright=1.0, vowel=(700, 1150, 2600)):
    """choir-like pad: many detuned sawtooths through vowel formants"""
    t = tt(d)
    out = np.zeros_like(t)
    for f in freqs:
        for k in range(4):
            det = f * (1 + rng.uniform(-0.004, 0.004))
            vib = 1 + 0.004 * np.sin(2 * np.pi * rng.uniform(4.5, 5.8) * t + rng.uniform(0, 6))
            ph = np.cumsum(det * vib) / SR
            out += (2 * (ph % 1.0) - 1) * 0.25
    y = np.zeros_like(out)
    for fm, g in zip(vowel, (1.0, 0.6 * bright, 0.25 * bright)):
        y += filt(out, 'band', [fm * 0.8, fm * 1.25]) * g
    return y * 0.25


def koto(f0, d=3.5):
    t = tt(d)
    out = np.zeros_like(t)
    for k in range(1, 9):
        fk = f0 * k * (1 + 0.0009 * k * k)
        out += np.sin(2 * np.pi * fk * t) * np.exp(-t * (1.1 + 0.9 * k)) / k ** 0.9
    pluck = filt(noise(0.03), 'high', 2000) * 0.2
    out[: len(pluck)] += pluck
    return out * 0.35


def drone(freqs, d, cutoff=900, lfo=0.07):
    t = tt(d)
    out = np.zeros_like(t)
    for f in freqs:
        for det in (-0.25, 0.0, 0.3):
            ph = np.cumsum(np.full_like(t, f + det)) / SR
            out += 2 * (ph % 1.0) - 1
    out = filt(out, 'low', cutoff)
    out *= 0.75 + 0.25 * np.sin(2 * np.pi * lfo * t)
    return out / max(1, len(freqs) * 3) * 0.6


def thunder(d=6.0):
    t = tt(d)
    crack = filt(noise(d), 'high', 900) * np.exp(-t * 18) * 0.9
    rumble = filt(brown(d), 'low', 180) * np.exp(-t * 0.8) * (0.6 + 0.4 * np.abs(filt(noise(d), 'low', 3)) * 3)
    return np.tanh((crack + rumble * 1.8) * 1.2)


def roar(d=3.2):
    t = tt(d)
    f = 48 + 10 * np.sin(2 * np.pi * 3.1 * t) + 6 * filt(noise(d), 'low', 12) * 20
    ph = np.cumsum(f) / SR
    saw = 2 * (ph % 1.0) - 1
    gr = saw * (1 + 0.8 * filt(noise(d), 'low', 60) * 8)
    gr += filt(noise(d), 'band', [200, 1200]) * 0.6
    y = np.tanh(filt(gr, 'low', 700) * 3)
    return y * np.minimum(1, t / 0.25) * np.exp(-np.maximum(0, t - 1.6) * 1.8) * 0.5


def shing(d=5.0):
    t = tt(d)
    out = np.zeros_like(t)
    for f, a, dec in [(2093, 1, .9), (3163, .7, 1.2), (4428, .5, 1.6), (5911, .35, 2.1), (7822, .2, 2.8), (1047, .5, .7)]:
        out += a * np.sin(2 * np.pi * f * t) * np.exp(-t * dec) * (1 + 0.3 * np.sin(2 * np.pi * 4.3 * t))
    return out * np.minimum(1, t * 3000) * 0.18


def whoosh(d, f0, f1, curve=2.5):
    x = noise(d)
    n = len(x)
    out = np.zeros(n)
    seg = 2048
    for i in range(0, n, seg):
        k = (i / n) ** curve
        fc = f0 + (f1 - f0) * k
        out[i:i + seg] = filt(x[i:i + seg], 'band', [fc * 0.7, min(fc * 1.4, SR / 2 - 100)])
    return out * np.sin(np.linspace(0, np.pi, n)) ** 2


def riser(d, f0=200, f1=4000):
    return whoosh(d, f0, f1, 2.0) * swell(d, 2.5)


# notes (miyako-bushi on D, yo scale on D for the dawn)
def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


D2, A2, D3, Eb3, G3, A3, Bb3, D4, Eb4, G4, A4, Bb4, D5 = [hz(m) for m in (38, 45, 50, 51, 55, 57, 58, 62, 63, 67, 69, 70, 74)]
E4, Fs4, B4, E5, Fs5, A5 = [hz(m) for m in (64, 66, 71, 76, 78, 81)]

# ================================================================= S1 chaos 0-15
place(music, 0.0, drone([D2, A2], 15.2, cutoff=500) * swell(15.2, 0.6) * np.minimum(1, (15.2 - tt(15.2)) / 0.6), 0.9)
place(dry, 0.0, filt(brown(15), 'low', 120) * swell(15, 1.5), 0.35)
place(dry, C['spark'] - 0.02, boom(6, 40), 0.9)
place(music, C['spark'], rin(D5 * 2, 8), 0.5, 0.1)
place(music, C['spark'] + 0.05, filt(noise(3), 'high', 6000) * env_ar(3 * SR, 0.001, 0.6), 0.08)
# shakuhachi: the first voice in the void
for (st, f, d) in [(3.0, D4, 2.6), (5.4, Eb4, 1.2), (6.5, D4, 2.4), (8.6, A3, 1.2)]:
    place(music, st, shakuhachi(f, d), 0.85, -0.15)
place(dry, C['divide'] - 1.6, riser(1.6, 300, 7000), 0.45)
place(dry, C['divide'], taiko(52, 2.0, 3.5), 1.0)
place(dry, C['divide'], boom(6.5, 38), 1.0)
place(music, C['divide'], voice_pad([D3, A3, D4], 5.5) * env_ar(int(5.5 * SR), 0.4, 3.0), 1.2)
for i, g in enumerate(C['gods']):
    place(music, g, rin([D5, A5, D5 * 2][i], 6), 0.55, [-0.4, 0.0, 0.4][i])
place(dry, 13.6, riser(1.4, 400, 9000), 0.5)

# ================================================================= S2 kuniumi 15-32
s2 = 17.0
place(dry, C['cut1'], taiko(55, 1.6, 3.0), 0.9)
place(dry, C['cut1'], boom(4, 42), 0.7)
sea = filt(brown(s2), 'low', 400) + filt(noise(s2), 'band', [300, 1800]) * 0.15
sea *= 0.6 + 0.4 * np.sin(2 * np.pi * 0.11 * tt(s2)) ** 2
place(dry, 15.0, sea * np.minimum(1, tt(s2) / 1.5) * np.minimum(1, (s2 - tt(s2)) / 1.0), 0.35)
place(music, 15.0, drone([D2, A2, D3], s2, cutoff=700, lfo=0.1) * np.minimum(1, (s2 - tt(s2)) / 1.0), 0.8)
# the spear descends: glassy descending shimmer
for k in range(14):
    place(music, 15.6 + k * 0.26, rin(hz(98 - k * 2), 3.5), 0.13, np.sin(k) * 0.6)
# the stir: whirlpool roar
wd = C['lift'] - C['stir'] + 2.0
place(dry, C['stir'], whoosh(wd, 120, 900, 1.0) * 3.5 + filt(brown(wd), 'low', 200) * swell(wd, 0.8) * 0.8, 0.55)
for k, bt in enumerate(np.arange(C['stir'], C['lift'], 1.0)):
    place(dry, bt, taiko(70 if k % 2 else 58, 1.0, 1.6), 0.45 + 0.05 * k)
place(music, 20.2, shakuhachi(G4, 2.2), 0.6, 0.2)
place(music, 22.4, shakuhachi(A4, 1.4), 0.6, 0.2)
# the drop: suspended tension
place(music, C['lift'] + 1.0, voice_pad([D4, Eb4], 3.0, 0.6) * swell(3.0, 1.2), 0.9)
place(music, C['impact'] - 1.9, rin(D5 * 2, 2.2), 0.4)
place(dry, C['impact'] - 0.6, riser(0.6, 500, 8000), 0.4)
place(dry, C['impact'], taiko(48, 2.2, 4.0), 1.1)
place(dry, C['impact'], boom(7, 36), 1.1)
place(dry, C['impact'], filt(noise(3), 'low', 1200) * env_ar(3 * SR, 0.002, 0.5), 0.5)
place(music, C['impact'], voice_pad([D3, A3, D4, A4], 5.0, 1.2) * env_ar(int(5.0 * SR), 0.1, 2.5), 1.4)
place(music, C['impact'] + 0.3, drone([D2, A2], 4.0, 400) * swell(4.0, 0.3)[::-1], 0.8)

# ================================================================= S3 iwato 32-50
s3 = 18.0
wind = whoosh(s3, 250, 500, 1.0) * 2.0 + filt(noise(s3), 'band', [400, 1400]) * 0.25 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.13 * tt(s3)))
place(dry, 32.0, wind * np.minimum(1, tt(s3) / 2), 0.35)
# fire crackle
cr = np.zeros(int(13 * SR))
for i in rng.integers(0, len(cr) - 2000, 260):
    cr[i:i + 400] += filt(noise(400 / SR), 'high', 2500) * np.exp(-np.arange(400) / 60) * rng.uniform(0.2, 1)
place(dry, 32.5, cr, 0.25, -0.3)
place(dry, 32.5, cr[::-1], 0.2, 0.3)
place(music, 32.0, drone([D2, Eb3 / 2], 13.0, cutoff=380, lfo=0.05) * np.minimum(1, tt(13) / 3), 0.9)
place(music, 34.0, shakuhachi(D4, 2.8), 0.55, -0.3)
place(music, 36.8, shakuhachi(Eb4, 1.2), 0.55, -0.3)
# the dance of Ame-no-Uzume: drums + suzu accelerate
for k, b in enumerate(TL['iwato_beats']):
    g = 0.55 + 0.45 * k / len(TL['iwato_beats'])
    place(dry, b, taiko(64 if k % 3 else 54, 1.0, 1.5), g, (-0.25 if k % 2 else 0.25))
    place(music, b + 0.01, suzu(1.0), 0.8 * g, (0.4 if k % 2 else -0.4))
place(dry, 42.0, riser(2.6, 150, 3000), 0.5)
# the rock rolls
rd = C['burst'] - C['door'] + 1.2
grind = filt(brown(rd), 'low', 140) * 1.4 + filt(noise(rd), 'band', [80, 400]) * 0.5 * (1 + np.sin(2 * np.pi * 7 * tt(rd)))
place(dry, C['door'], np.tanh(grind * 2) * np.minimum(1, tt(rd) / 0.2), 0.8)
# the sun returns
place(dry, C['burst'], taiko(46, 2.5, 5.0), 1.2)
place(dry, C['burst'], boom(8, 34), 1.2)
place(music, C['burst'], voice_pad([D3, A3, D4, Fs4, A4, D5], 7.0, 1.4, vowel=(800, 1300, 2800)) * env_ar(int(7 * SR), 0.05, 3.5), 1.6)
place(music, C['burst'], rin(D5, 7), 0.5, -0.3)
place(music, C['burst'] + 0.05, rin(A5, 7), 0.4, 0.3)
for k in range(10):
    place(music, C['burst'] + 0.3 + k * 0.17, rin(hz(86 + [0, 2, 4, 7, 9][k % 5]), 3), 0.1, np.sin(k * 2) * 0.7)
place(dry, 48.0, riser(2.0, 600, 12000), 0.5)

# ================================================================= S4 orochi 50-65
s4 = 15.0
rain = filt(noise(s4), 'high', 1500) * 0.35 + filt(noise(s4), 'band', [500, 3000]) * 0.2
place(dry, 50.0, np.stack([rain, filt(noise(s4), 'high', 1500) * 0.35], 1) * np.minimum(1, (s4 - tt(s4))[:, None] / 0.5), 0.3)
place(music, 50.0, drone([D2, Eb3 / 2, A2 * 1.0], 13.6, cutoff=450, lfo=0.2), 1.0)
for k, lt in enumerate(C['lightning']):
    place(dry, lt, thunder(6), 0.9 if k == 0 else 0.7, [0, -0.5, 0.3, -0.2, 0.5][k])
# heartbeat of the serpent
hb = 51.0
k = 0
while hb < 63.2:
    place(dry, hb, taiko(44, 1.8, 2.0), 0.7)
    place(dry, hb + 0.28, taiko(40, 1.4, 1.5), 0.45)
    hb += max(0.75, 1.6 - k * 0.09)
    k += 1
place(dry, C['eyes'], roar(3.4), 1.3, -0.1)
place(dry, C['eyes'] + 0.25, roar(3.0), 0.9, 0.35)
place(dry, C['eyes'], boom(5, 32), 1.0)
place(music, 54.0, voice_pad([D3, Eb3], 6.0, 0.5, vowel=(450, 800, 2400)) * swell(6.0, 0.5) * np.minimum(1, (6 - tt(6)) / 1.0), 0.9)
place(music, 60.4, shakuhachi(A4, 1.6, vib=6.5), 0.6, 0.3)
place(music, 62.0, shakuhachi(Bb4, 1.3, vib=6.5), 0.6, 0.3)
place(dry, 61.2, riser(2.3, 200, 6000), 0.6)
# the slash
place(dry, C['slash'] - 0.12, whoosh(0.35, 800, 9000, 1.0) * 4, 0.9, -0.3)
place(music, C['slash'], shing(6), 1.0, 0.0)
place(dry, C['slash'], taiko(60, 1.2, 2.0), 0.8)
place(dry, 64.2, riser(0.8, 800, 10000), 0.5)

# ================================================================= S5 dawn 65-84
s5 = 19.0
place(dry, C['cut4'], taiko(50, 2.2, 4.5), 1.1)
place(dry, C['cut4'], boom(6, 36), 1.0)
place(music, C['cut4'], voice_pad([D3, A3, D4, Fs4, A4], s5, 0.9, vowel=(650, 1100, 2600)) * np.minimum(1, tt(s5) / 2.0) * np.minimum(1, (s5 - tt(s5)) / 4.0), 1.0)
gentle = filt(brown(s5), 'low', 350) * 0.6 + filt(noise(s5), 'band', [600, 2000]) * 0.05
place(dry, 65.0, gentle * np.minimum(1, tt(s5) / 2) * np.minimum(1, (s5 - tt(s5)) / 3), 0.3)
# koto arpeggios on the yo scale
yo = [D4, E4, Fs4, A4, B4, D5, E5, Fs5]
pat = [0, 2, 3, 5, 3, 2, 4, 6, 5, 3, 2, 0, 1, 3, 5, 7]
for i, n_ in enumerate(pat * 2):
    st = 66.2 + i * 0.36
    if st > 79:
        break
    place(music, st, koto(yo[n_]), 0.5, np.sin(i * 0.9) * 0.5)
for (st, f, d) in [(68.0, A4, 2.0), (70.2, B4, 1.0), (71.2, D5, 3.2), (75.0, B4, 1.4), (76.6, A4, 3.6)]:
    place(music, st, shakuhachi(f, d), 0.7, -0.2)
# the title
place(dry, C['title'] + 0.2, taiko(56, 1.6, 3.5), 0.8)
place(music, C['title'] + 0.2, rin(D5, 9), 0.55, -0.2)
place(music, C['title'] + 0.65, rin(A5, 9), 0.45, 0.2)
place(music, C['title'] + 1.1, rin(D5 * 2, 9), 0.35, 0.0)
place(music, 79.0, rin(D5, 7), 0.35)

# ================================================================= mix
def reverb_ir(d=3.8):
    t = tt(d)
    irs = []
    for ch in range(2):
        n = rng.standard_normal(len(t)) * np.exp(-t * 1.6)
        n = filt(n, 'low', 5500)
        n[: int(0.012 * SR)] *= 0.2
        irs.append(n / np.sqrt(np.sum(n ** 2)))
    return np.stack(irs, 1)


ir = reverb_ir()
wet = np.stack([signal.fftconvolve(music[:, c], ir[:, c])[:N] for c in range(2)], 1)
wet_dry = np.stack([signal.fftconvolve(dry[:, c], ir[:, c])[:N] for c in range(2)], 1)
mix = music * 0.55 + wet * 0.9 + dry * 0.9 + wet_dry * 0.25
mix = filt(mix, 'high', 25)
# gentle glue + limiter
peak = np.percentile(np.abs(mix), 99.95)
mix = mix / peak * 0.8
mix = np.tanh(mix * 1.15) / np.tanh(1.15)
t = np.arange(N) / SR
mix *= np.clip((TL['duration'] - t) / 2.5, 0, 1)[:, None] ** 1.5
mix *= 0.94 / np.abs(mix).max()
wavfile.write('out/score.wav', SR, (mix * 32767).astype(np.int16))
print('wrote out/score.wav', mix.shape, 'peak', np.abs(mix).max())
