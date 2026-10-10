import math, os, sys, random, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from multiprocessing import Pool

W = H = 1080
S = 2                      # supersampling
FPS = 60
DUR = 2.0
NF = int(FPS * DUR)
OUT = sys.argv[1]
os.makedirs(OUT + "/frames", exist_ok=True)

CX, CY = 540, 700          # bowl rim center
BX, BY, BRX, BRY = 540, 712, 388, 148   # broth ellipse
GX, GY0 = 545, 400         # chopstick grip
MOUTH = (550, -90)

def P(x, y): return (x * S, y * S)
def box(cx, cy, rx, ry): return [(cx - rx) * S, (cy - ry) * S, (cx + rx) * S, (cy + ry) * S]
def smooth(a, b, x):
    t = min(1, max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t)

rng = random.Random(7)

# ---------- pull distance D(t) ----------
ts = np.linspace(0, DUR, 4001)
vel = np.array([1500 * smooth(0.35, 0.8, t) for t in ts])
Dcum = np.concatenate([[0], np.cumsum((vel[1:] + vel[:-1]) / 2 * np.diff(ts))])
def D(t): return float(np.interp(t, ts, Dcum))
def grip_y(t): return GY0 + 30 * (1 - smooth(0, 0.35, t)) + 4 * math.sin(t * 9) * smooth(0.3, 0.6, t)

# ---------- strands ----------
NS = 13
strands = []
for i in range(NS):
    off = -1 + 2 * i / (NS - 1) + rng.uniform(-0.08, 0.08)
    strands.append(dict(
        off=off, ph=rng.uniform(0, 6.28), ph2=rng.uniform(0, 6.28),
        lam=rng.uniform(38, 52), lam2=rng.uniform(180, 260),
        amp=rng.uniform(3.5, 5.5), sway=rng.uniform(6, 14),
        yb=BY + rng.uniform(-10, 25),
        T=rng.uniform(0.95, 1.32),
        depth=rng.random(),
        col=(rng.randint(232, 246), rng.randint(190, 206), rng.randint(92, 112)),
    ))
strands.sort(key=lambda s: s["depth"])

def strand_x(s, y, t, ybot):
    gy = grip_y(t)
    if y >= gy:
        u = (y - gy) / max(1, s["yb"] - gy)
        xc = GX + s["off"] * (8 + 115 * u ** 0.85)
        A = s["sway"] * u
    else:
        u = (gy - y) / (gy - MOUTH[1])
        xc = GX + s["off"] * (8 + 22 * u) + (MOUTH[0] - GX) * u
        A = 3 * u
    d = D(t)
    w = s["amp"] * math.sin(2 * math.pi * (y + d) / s["lam"] + s["ph"])
    w += A * math.sin(2 * math.pi * (y + 0.35 * d) / s["lam2"] + s["ph2"] + 2.2 * t)
    if t > s["T"]:      # tail whip
        dist = max(0.0, ybot - y)
        w += 18 * math.exp(-dist / 70) * math.sin(dist / 18 + t * 30 + s["ph"])
    return xc + w

def strand_bottom(s, t):
    if t < s["T"]: return s["yb"]
    return s["yb"] - (D(t) - D(s["T"]))

def strand_pts(s, t):
    yb = strand_bottom(s, t)
    if yb < MOUTH[1]: return None, yb
    ys = np.arange(yb, MOUTH[1] - 1, -5.0)
    return [(strand_x(s, y, t, yb), y) for y in ys], yb

# ---------- drips, splashes, ripples ----------
G = 2600.0
drops, ripples = [], []
for _ in range(80):
    s = rng.choice(strands); t0 = rng.uniform(0.25, 1.9)
    yb = strand_bottom(s, t0); gy = grip_y(t0)
    lo, hi = max(gy + 20, MOUTH[1]), min(yb, s["yb"] - 15)
    if hi <= lo: continue
    y0 = rng.uniform(lo, hi)
    x0 = strand_x(s, y0, t0, yb)
    land = BY + rng.uniform(-20, 40)
    vx = rng.uniform(-40, 40)
    tl = t0 + math.sqrt(2 * (land - y0) / G)
    drops.append(dict(x0=x0, y0=y0, vx=vx, vy=0, t0=t0, tl=tl, r=rng.uniform(2.5, 4.5)))
    ripples.append(dict(x=x0 + vx * (tl - t0), y=land, t0=tl, big=False))
for s in strands:
    x0 = strand_x(s, s["yb"], s["T"], s["yb"]); y0 = s["yb"]
    ripples.append(dict(x=x0, y=y0, t0=s["T"], big=True))
    for _ in range(9):
        vx, vy = rng.uniform(-260, 260), rng.uniform(-850, -380)
        land = y0 + rng.uniform(-10, 30)
        # solve y0 + vy t + G t^2/2 = land
        a, b, c = G / 2, vy, y0 - land
        tl = s["T"] + (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a)
        drops.append(dict(x0=x0, y0=y0, vx=vx, vy=vy, t0=s["T"], tl=tl, r=rng.uniform(2, 4)))
        ripples.append(dict(x=x0 + vx * (tl - s["T"]), y=land, t0=tl, big=False))

oil = []
while len(oil) < 110:
    x, y = rng.uniform(-1, 1), rng.uniform(-1, 1)
    if x * x + y * y < 0.85:
        oil.append((BX + x * BRX, BY + y * BRY, rng.uniform(3, 11), rng.uniform(0, 6.28), rng.uniform(2, 5)))

steam = [dict(x=rng.uniform(250, 830), ph=rng.random(), sp=rng.uniform(0.5, 0.9),
              r=rng.uniform(25, 60), sw=rng.uniform(15, 45), f=rng.uniform(1, 3)) for _ in range(34)]

# ---------- static layers ----------
def build_static():
    WS, HS = W * S, H * S
    yy, xx = np.mgrid[0:HS, 0:WS].astype(np.float32) / S
    # counter: warm dark wood
    g = (yy / H)[..., None]
    top = np.array([40, 22, 12], np.float32); bot = np.array([22, 11, 5], np.float32)
    bg = top * (1 - g) + bot * g
    grain = 1 + 0.06 * np.sin(yy * 0.9 + 6 * np.sin(xx * 0.004 + yy * 0.01)) + 0.03 * np.sin(yy * 3.1)
    bg *= grain[..., None]
    img = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8)).convert("RGBA")
    # bokeh lights (izakaya)
    bk = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(bk)
    for _ in range(14):
        x, y, r = rng.uniform(0, W), rng.uniform(0, 330), rng.uniform(25, 70)
        c = rng.choice([(255, 170, 70), (255, 120, 50), (255, 210, 140)])
        d.ellipse(box(x, y, r, r), fill=c + (rng.randint(40, 90),))
    bk = bk.filter(ImageFilter.GaussianBlur(8 * S))
    img = Image.alpha_composite(img, bk)
    d = ImageDraw.Draw(img)
    # shadow
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse(box(CX + 20, 1010, 400, 70), fill=(0, 0, 0, 200))
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(25 * S)))
    # bowl body (lower half ellipse)
    body = Image.new("L", img.size, 0)
    ImageDraw.Draw(body).ellipse(box(CX, CY, 420, 330), fill=255)
    ImageDraw.Draw(body).rectangle([0, 0, W * S, CY * S], fill=0)
    ImageDraw.Draw(body).ellipse(box(CX, CY, 420, 170), fill=255)
    shade = np.clip(1 - (xx - CX) / 420, 0, 2)  # lighter left
    bcol = np.stack([18 + 22 * np.exp(-((xx - 330) / 60) ** 2) * (yy > CY),
                     14 + 18 * np.exp(-((xx - 330) / 60) ** 2) * (yy > CY),
                     20 + 22 * np.exp(-((xx - 330) / 60) ** 2) * (yy > CY)], -1) * (0.8 + 0.2 * shade[..., None])
    bimg = Image.fromarray(np.clip(bcol, 0, 255).astype(np.uint8)).convert("RGBA")
    img.paste(bimg, (0, 0), body)
    d = ImageDraw.Draw(img)
    # red band + white line (raimon-ish)
    d.arc(box(CX, CY + 40, 414, 180), 8, 172, fill=(150, 25, 22), width=16 * S)
    d.arc(box(CX, CY + 58, 410, 185), 10, 170, fill=(200, 190, 175), width=2 * S)
    d.arc(box(CX, CY + 24, 416, 176), 8, 172, fill=(200, 190, 175), width=2 * S)
    # rim and inner wall
    d.ellipse(box(CX, CY, 420, 170), fill=(28, 12, 12))
    d.ellipse(box(CX, CY + 3, 407, 161), fill=(70, 30, 20))
    d.arc(box(CX, CY, 418, 168), 195, 300, fill=(150, 110, 100), width=3 * S)
    # broth radial gradient
    nx, ny = (xx - BX) / BRX, (yy - BY) / BRY
    r = np.sqrt(nx * nx + ny * ny)
    c0 = np.array([214, 132, 48], np.float32); c1 = np.array([92, 42, 14], np.float32)
    k = np.clip(r, 0, 1)[..., None] ** 1.4
    broth = c0 * (1 - k) + c1 * k
    # window reflection
    refl = np.exp(-(((xx - 420) / 150) ** 2 + ((yy - 640) / 28) ** 2))
    broth += refl[..., None] * np.array([90, 80, 60])
    bm = Image.new("L", img.size, 0)
    ImageDraw.Draw(bm).ellipse(box(BX, BY, BRX, BRY), fill=255)
    bm = bm.filter(ImageFilter.GaussianBlur(1.5 * S))
    img.paste(Image.fromarray(np.clip(broth, 0, 255).astype(np.uint8)).convert("RGBA"), (0, 0), bm)
    return img, np.asarray(bm, np.float32) / 255

def build_toppings():
    L = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    # submerged noodles
    sub = Image.new("RGBA", L.size, (0, 0, 0, 0)); ds = ImageDraw.Draw(sub)
    for j in range(16):
        y0 = BY + rng.uniform(-60, 70); x0 = rng.uniform(380, 680)
        pts = [P(x0 + u * 3.2, y0 + 6 * math.sin(u / 6 + j) + 0.3 * u * rng.choice([-1, 1])) for u in range(-30, 31)]
        ds.line(pts, fill=(235, 195, 95, 110), width=7 * S, joint="curve")
    L = Image.alpha_composite(L, sub.filter(ImageFilter.GaussianBlur(2.5 * S))); d = ImageDraw.Draw(L)
    # nori
    d.polygon([P(215, 650), P(335, 640), P(350, 455), P(232, 470)], fill=(22, 32, 24))
    d.polygon([P(225, 640), P(250, 638), P(262, 470), P(240, 472)], fill=(40, 55, 40))
    # menma
    for j in range(5):
        x, y, a = 450 + j * 18, 640 + rng.uniform(-8, 8), rng.uniform(-0.5, 0.5)
        ca, sa = math.cos(a), math.sin(a)
        pts = [(x + dx * ca - dy * sa, y + dx * sa + dy * ca) for dx, dy in [(-36, -6), (36, -6), (36, 6), (-36, 6)]]
        d.polygon([P(*p) for p in pts], fill=(176, 122, 52))
        d.line([P(*pts[0]), P(*pts[1])], fill=(225, 175, 100), width=2 * S)
    # chashu x2
    for (x, y, rx, ry) in [(700, 655, 105, 48), (745, 700, 120, 55)]:
        d.ellipse(box(x, y, rx, ry), fill=(92, 38, 18))
        d.ellipse(box(x - 3, y - 3, rx - 10, ry - 8), fill=(178, 102, 74))
        d.ellipse(box(x + 10, y + 2, rx * 0.55, ry * 0.5), fill=(195, 120, 92))
        d.arc(box(x - 15, y, rx * 0.6, ry * 0.55), 200, 340, fill=(238, 212, 188), width=6 * S)
        d.arc(box(x + 20, y + 4, rx * 0.35, ry * 0.3), 20, 200, fill=(238, 212, 188), width=5 * S)
        d.arc(box(x - 5, y - 5, rx - 18, ry - 14), 210, 280, fill=(255, 240, 225), width=3 * S)
    # ajitama
    d.ellipse(box(395, 778, 64, 40), fill=(190, 140, 80))
    d.ellipse(box(395, 776, 58, 35), fill=(246, 240, 226))
    d.ellipse(box(392, 776, 36, 22), fill=(238, 142, 28))
    d.ellipse(box(392, 778, 22, 13), fill=(214, 96, 18))
    d.ellipse(box(380, 768, 9, 4), fill=(255, 245, 220))
    # naruto
    d.ellipse(box(655, 795, 46, 25), fill=(250, 248, 244))
    d.arc(box(655, 795, 26, 14), 0, 300, fill=(232, 90, 130), width=4 * S)
    d.arc(box(652, 795, 13, 7), 60, 360, fill=(232, 90, 130), width=4 * S)
    # negi
    for _ in range(30):
        x, y = BX + rng.uniform(-200, 120), BY + rng.uniform(-30, 110)
        if ((x - BX) / BRX) ** 2 + ((y - BY) / BRY) ** 2 > 0.85: continue
        d.ellipse(box(x, y, 8, 5), fill=(212, 232, 160), outline=(110, 170, 60), width=3 * S)
    return L.filter(ImageFilter.GaussianBlur(0.6 * S))

STATIC, BMASK = build_static()
TOP = build_toppings()

# ---------- per frame ----------
def chopstick(d, base, tip, wb, wt, col, hl):
    (x0, y0), (x1, y1) = base, tip
    dx, dy = x1 - x0, y1 - y0; n = math.hypot(dx, dy); px, py = -dy / n, dx / n
    poly = [P(x0 + px * wb, y0 + py * wb), P(x1 + px * wt, y1 + py * wt), P(x1 - px * wt, y1 - py * wt), P(x0 - px * wb, y0 - py * wb)]
    d.polygon(poly, fill=col)
    d.line([P(x0 + px * wb * 0.4, y0 + py * wb * 0.4), P(x1 + px * wt * 0.4, y1 + py * wt * 0.4)], fill=hl, width=3 * S)

def render(fi):
    t = fi / FPS
    img = STATIC.copy()
    # oil + ripples, masked to broth
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    for (x, y, r, ph, f) in oil:
        jx = 2 * math.sin(t * f + ph)
        d.ellipse(box(x + jx, y, r, r * 0.45), fill=(240, 170, 60, 150))
        tw = 0.5 + 0.5 * math.sin(t * f * 3 + ph)
        d.ellipse(box(x + jx - r * 0.3, y - r * 0.12, r * 0.28, r * 0.12), fill=(255, 250, 220, int(120 + 135 * tw)))
    for rp in ripples:
        a = t - rp["t0"]
        if a <= 0 or a > (1.1 if rp["big"] else 0.7): continue
        life = a / (1.1 if rp["big"] else 0.7)
        for k in range(3 if rp["big"] else 1):
            rr = (14 + (170 if rp["big"] else 55) * (a ** 0.6)) - k * 16
            if rr <= 2: continue
            d.ellipse(box(rp["x"], rp["y"], rr, rr * 0.36), outline=(255, 225, 170, int(190 * (1 - life))), width=int(2.5 * S))
    la = np.asarray(lay).copy(); la[..., 3] = (la[..., 3] * BMASK).astype(np.uint8)
    img = Image.alpha_composite(img, Image.fromarray(la))
    img = Image.alpha_composite(img, TOP)

    d = ImageDraw.Draw(img)
    gy = grip_y(t)
    # back chopstick
    chopstick(d, (1180, -60), (GX - 22, gy - 14), 13, 5, (92, 18, 16), (200, 90, 80))
    # meniscus at entry points
    for s in strands:
        if t < s["T"]:
            x = strand_x(s, s["yb"], t, s["yb"])
            d.ellipse(box(x, s["yb"], 12, 4), outline=(255, 230, 180), width=2 * S)
    # noodles
    nl = Image.new("RGBA", img.size, (0, 0, 0, 0)); dn = ImageDraw.Draw(nl)
    for s in strands:
        pts, yb = strand_pts(s, t)
        if not pts: continue
        sp = [P(x, y) for x, y in pts]
        dk = 0.82 + 0.18 * s["depth"]
        c = tuple(int(v * dk) for v in s["col"])
        dn.line(sp, fill=(150, 98, 30, 255), width=int(10 * S), joint="curve")
        dn.line(sp, fill=c + (255,), width=int(7.5 * S), joint="curve")
        dn.line([P(x - 1.8, y) for x, y in pts], fill=(255, 248, 215, 210), width=int(2.2 * S), joint="curve")
        # sparkles travelling with the noodle
        d_ = D(t)
        for y in range(int(MOUTH[1]), int(yb)):
            if (y + int(d_) + int(s["ph"] * 50)) % 160 == 0:
                x = strand_x(s, y, t, yb) - 2
                dn.ellipse(box(x, y, 3.2, 3.2), fill=(255, 255, 245, 255))
    img = Image.alpha_composite(img, nl)
    d = ImageDraw.Draw(img)
    # drops
    for dr in drops:
        a = t - dr["t0"]
        if a < 0 or t > dr["tl"]: continue
        x = dr["x0"] + dr["vx"] * a; y = dr["y0"] + dr["vy"] * a + G * a * a / 2
        v = dr["vy"] + G * a; st = min(2.2, 1 + abs(v) / 900)
        r = dr["r"]
        d.ellipse(box(x, y, r, r * st), fill=(235, 170, 70, 220))
        d.ellipse(box(x - r * 0.3, y - r * 0.4 * st, r * 0.35, r * 0.35), fill=(255, 255, 240))
    # front chopstick
    chopstick(d, (1150, 20), (GX - 30, gy + 16), 14, 5.5, (110, 22, 20), (230, 120, 105))

    # steam
    st = Image.new("RGBA", (W // 4, H // 4), (0, 0, 0, 0)); ds = ImageDraw.Draw(st)
    for w in steam:
        life = (w["ph"] + t * w["sp"] * 0.5) % 1.0
        y = 680 - life * 620
        x = w["x"] + w["sw"] * math.sin(life * 6 + w["f"] * t)
        al = int(70 * math.sin(math.pi * life) ** 1.5)
        r = w["r"] * (0.6 + life)
        ds.ellipse([(x - r) / 4, (y - r * 1.4) / 4, (x + r) / 4, (y + r * 1.4) / 4], fill=(255, 245, 235, al))
    st = st.filter(ImageFilter.GaussianBlur(6)).resize(img.size, Image.BICUBIC)
    img = Image.alpha_composite(img, st)

    # downsample + slow push-in
    img = img.convert("RGB").resize((W, H), Image.LANCZOS)
    z = 1 + 0.06 * smooth(0, DUR, t)
    cw = W / z; cx, cy = 545, 520
    img = img.crop((cx - cw / 2, cy - cw / 2, cx + cw / 2, cy + cw / 2)).resize((W, H), Image.LANCZOS)

    # bloom + warm grade + vignette
    a = np.asarray(img, np.float32)
    lum = a.mean(-1, keepdims=True)
    hi = np.clip((lum - 185) / 70, 0, 1) * a
    bl = np.asarray(Image.fromarray(hi.astype(np.uint8)).filter(ImageFilter.GaussianBlur(14)), np.float32)
    a = a + 0.75 * bl
    a = a * np.array([1.06, 1.0, 0.9])
    a = 255 * (a / 255) ** 0.95
    yy, xx = np.mgrid[0:H, 0:W]
    vig = 1 - 0.55 * np.clip(((xx - 540) ** 2 + (yy - 560) ** 2) / 620 ** 2 - 0.25, 0, 1)
    a *= vig[..., None]
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(f"{OUT}/frames/{fi:04d}.png")
    return fi

# ---------- audio: ズズッ ----------
def audio():
    sr = 48000; n = int(sr * DUR); r = np.random.default_rng(3)
    t = np.arange(n) / sr
    noise = r.standard_normal(n)
    F = np.fft.rfft(noise); f = np.fft.rfftfreq(n, 1 / sr)
    band = np.exp(-((np.log(f + 1) - np.log(1800)) / 0.55) ** 2)
    slurp = np.fft.irfft(F * band, n)
    slurp /= np.abs(slurp).max()
    env = np.zeros(n)
    for a, b in [(0.42, 0.62), (0.68, 0.9), (0.98, 1.58)]:
        env += np.clip(np.minimum((t - a) / 0.03, (b - t) / 0.025), 0, 1) * (t > a) * (t < b)
    flutter = 0.55 + 0.45 * np.sin(2 * np.pi * 23 * t + 3 * np.sin(2 * np.pi * 3 * t))
    sig = 0.6 * slurp * env * flutter
    # wet plips at splashes
    for s in strands:
        for k in range(2):
            t0 = s["T"] + k * 0.11 + 0.05
            m = (t > t0) & (t < t0 + 0.06)
            tt = t[m] - t0
            sig[m] += 0.12 * np.sin(2 * np.pi * (900 + 2600 * tt / 0.06) * tt) * np.exp(-tt * 70)
    # room hiss
    sig += 0.01 * np.fft.irfft(F * np.exp(-((f - 5000) / 3000) ** 2), n) / 40
    sig = np.tanh(sig * 1.3) * 0.85
    with wave.open(f"{OUT}/slurp.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((sig * 32767).astype(np.int16).tobytes())

if __name__ == "__main__":
    audio()
    with Pool(4) as p:
        for fi in p.imap_unordered(render, range(NF)):
            pass
    print("done")
