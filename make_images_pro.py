from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
import os, json, random, math, colorsys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MBTI_FREE  = ROOT / "app" / "data" / "images" / "free"
MBTI_PAID  = ROOT / "app" / "data" / "images" / "paid"
TESTS_ROOT = ROOT / "app" / "data" / "tests"

MBTI_FREE.mkdir(parents=True, exist_ok=True)
MBTI_PAID.mkdir(parents=True, exist_ok=True)

BASE_PALETTES = [
    [(36,55,84),(117,131,154),(200,175,150)],
    [(30,84,76),(92,124,108),(182,166,150)],
    [(76,58,96),(128,98,144),(205,170,185)],
    [(54,46,40),(105,86,74),(190,160,120)],
    [(52,86,55),(96,132,96),(170,186,160)],
    [(66,76,96),(112,128,156),(170,180,200)],
    [(84,68,72),(130,110,116),(200,180,176)],
    [(68,78,58),(112,126,100),(186,180,160)],
]

def choice_palette(seed):
    random.seed(seed)
    pal = random.choice(BASE_PALETTES)[:]
    def tweak(rgb):
        r,g,b = [c/255 for c in rgb]
        h,l,s = colorsys.rgb_to_hls(r,g,b)
        h = (h + random.uniform(-0.03,0.03)) % 1.0
        s = max(0.25, min(0.65, s + random.uniform(-0.1,0.1)))
        l = max(0.25, min(0.75, l + random.uniform(-0.05,0.05)))
        rr,gg,bb = colorsys.hls_to_rgb(h,l,s)
        return (int(rr*255), int(gg*255), int(bb*255))
    return [tweak(c) for c in pal]

def blend(c1, c2, t):
    return tuple(int(c1[i]*(1-t)+c2[i]*t) for i in range(3))

def make_blend(size, seed):
    random.seed(seed)
    pal = choice_palette(seed); base, mid, acc = pal
    w = h = size
    img = Image.new("RGB", (w,h), base)
    px = img.load()
    foci = [(random.uniform(.2*w,.8*w), random.uniform(.2*h,.8*h), random.uniform(.9,1.4)) for _ in range(2)]
    for y in range(h):
        for x in range(w):
            t_vals = []
            for (cx,cy,exp) in foci:
                d = math.hypot(x-cx, y-cy)/max(w,h)
                t_vals.append(min(1.0, d**exp))
            t = sum(t_vals)/len(t_vals)
            px[x,y] = blend(mid, acc, t*0.9)
    dr = ImageDraw.Draw(img, 'RGBA')
    for _ in range(8):
        r = random.randint(int(.05*w), int(.17*w))
        x = random.randint(-int(.1*w), int(1.1*w))
        y = random.randint(-int(.1*h), int(1.1*h))
        t = random.uniform(.2,.8)
        col = (*blend(base, acc, t), random.randint(70,130))
        dr.ellipse([(x-r,y-r),(x+r,y+r)], fill=col)
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    return img

def make_geo(size, seed):
    random.seed(seed)
    pal = choice_palette(seed+77); base, mid, acc = pal
    w = h = size
    img = Image.new("RGB", (w,h), base)
    dr = ImageDraw.Draw(img, 'RGBA')
    for _ in range(10):
        n = random.randint(3,6)
        pts = [(random.randint(-int(.1*w), int(1.1*w)),
                random.randint(-int(.1*h), int(1.1*h))) for __ in range(n)]
        t = random.uniform(.25,.8)
        col = (*blend(mid, acc, t), random.randint(60,120))
        dr.polygon(pts, fill=col)
    for _ in range(4):
        x1,y1 = random.randint(0,w), random.randint(0,h)
        x2,y2 = random.randint(0,w), random.randint(0,h)
        col = (*blend(base, acc, random.uniform(.3,.7)), 90)
        dr.line((x1,y1,x2,y2), fill=col, width=random.randint(6,14))
    img = img.filter(ImageFilter.GaussianBlur(1.0))
    return img

def make_grain(size, seed):
    random.seed(seed)
    pal = choice_palette(seed+123); base, mid, acc = pal
    w = h = size
    img = Image.new("RGB", (w,h), mid)
    dr = ImageDraw.Draw(img, 'RGBA')
    for _ in range(7):
        r = random.randint(int(.08*w), int(.22*w))
        x = random.randint(-int(.1*w), int(1.1*w))
        y = random.randint(-int(.1*h), int(1.1*h))
        t = random.uniform(.15,.85)
        col = (*blend(base, acc, t), random.randint(80,140))
        dr.ellipse([(x-r,y-r),(x+r,y+r)], fill=col)
    noise = Image.effect_noise((w,h), random.randint(8,18)).convert("L")
    noise = noise.filter(ImageFilter.GaussianBlur(0.6))
    img = Image.composite(img, Image.new("RGB",(w,h),(0,0,0)), noise.point(lambda v: int(v*0.22)))
    vign = Image.new("L", (w,h), 0); d2 = ImageDraw.Draw(vign)
    d2.ellipse([(-.15*w,-.15*h),(1.15*w,1.15*h)], fill=220)
    vign = vign.filter(ImageFilter.GaussianBlur(80))
    img.putalpha(255)
    img = Image.composite(img, Image.new("RGBA",(w,h), (*base,255)), vign).convert("RGB")
    return img

def enhance(img, seed):
    random.seed(seed)
    img = ImageEnhance.Color(img).enhance(random.uniform(0.9, 1.25))
    img = ImageEnhance.Contrast(img).enhance(random.uniform(0.95, 1.2))
    img = ImageEnhance.Brightness(img).enhance(random.uniform(0.95, 1.08))
    return img

def make_one(size, seed, mode):
    if mode == "blend": img = make_blend(size, seed)
    elif mode == "geo": img = make_geo(size, seed)
    else: img = make_grain(size, seed)
    return enhance(img, seed+999)

def cycle_modes(i): return ["blend","geo","grain"][i % 3]

def save_mbti():
    created = 0
    for i in range(1,17):
        p = MBTI_FREE / f"q{i}.jpg"
        mode = cycle_modes(i)
        img = make_one(900, 1000+i, mode)
        img.save(p, "JPEG", quality=90); created += 1
    for i in range(1,21):
        p = MBTI_PAID / f"q{i}.jpg"
        mode = cycle_modes(i+16)
        img = make_one(900, 2000+i, mode)
        img.save(p, "JPEG", quality=90); created += 1
    print(f"MBTI: создано {created} изображений →")
    print("  ", MBTI_FREE)
    print("  ", MBTI_PAID)

def ensure_images_for_test(slug_path: Path):
    qfile = slug_path / "questions.json"
    if not qfile.exists(): return 0, 0
    try:
        data = json.load(open(qfile, "r", encoding="utf-8"))
        questions = data.get("questions") or []
    except Exception:
        return 0, 0
    n = len(questions)
    if n == 0: return 0, 0
    img_dir = slug_path / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    created = 0
    for i in range(1, n+1):
        path = img_dir / f"q{i}.jpg"
        mode = cycle_modes(i)
        img = make_one(900, 3000 + abs(hash(slug_path.name)) % 100000 + i, mode)
        img.save(path, "JPEG", quality=90); created += 1
    return n, created

def save_tests():
    if not TESTS_ROOT.exists():
        print("Нет папки с тестами:", TESTS_ROOT); return
    total_tests=total_imgs=created_imgs=0
    for p in sorted(TESTS_ROOT.iterdir(), key=lambda x: x.name):
        if not p.is_dir(): continue
        n, c = ensure_images_for_test(p)
        if n>0:
            total_tests += 1; total_imgs += n; created_imgs += c
            print(f"• {p.name}: вопросов {n}, картинок {c}")
    print(f"Тесты: {total_tests} шт., вопросов {total_imgs}, создано картинок {created_imgs}")

if __name__ == "__main__":
    save_mbti()
    save_tests()
    print("✅ Готово.")
