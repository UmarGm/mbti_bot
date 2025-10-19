from PIL import Image, ImageDraw, ImageFilter
import os, json, random, math

ROOT = "app/data/tests"

def blend(c1, c2, t): 
    return tuple(int(c1[i]*(1-t)+c2[i]*t) for i in range(3))

def palette(seed):
    random.seed(seed)
    bases=[(40,70,110),(26,90,82),(108,66,117),(96,73,58),(52,86,55),(92,72,95),(74,84,102),(55,72,92)]
    accs=[(190,160,120),(160,175,150),(205,155,160),(180,150,205),(160,180,205),(210,165,130),(175,170,155),(165,150,180)]
    return random.choice(bases), random.choice(accs)

def radial(size, base, acc, seed):
    random.seed(seed); w=h=size
    cx,cy=random.uniform(.3*w,.7*w),random.uniform(.3*h,.7*h)
    img=Image.new("RGB",(w,h),base); px=img.load()
    maxr=math.hypot(max(cx,w-cx),max(cy,h-cy))
    for y in range(h):
        for x in range(w):
            d=math.hypot(x-cx,y-cy)/maxr
            t=min(1.0,d**1.2)*.85
            px[x,y]=blend(tuple(min(255,int(c*1.05)) for c in base),
                          tuple(min(255,int(c*1.05)) for c in acc), t)
    mask=Image.new("L",(w,h),0); dr=ImageDraw.Draw(mask)
    dr.ellipse([(-.2*w,-.2*h),(1.2*w,1.2*h)],fill=220)
    mask=mask.filter(ImageFilter.GaussianBlur(80))
    img.putalpha(255)
    img=Image.composite(img, Image.new("RGBA",(w,h),(*base,255)), mask)
    return img.convert("RGB")

def shapes(img, base, acc, seed):
    random.seed(seed); w,h=img.size; dr=ImageDraw.Draw(img,'RGBA')
    for _ in range(6):
        r=random.randint(int(.05*w), int(.15*w))
        x=random.randint(-int(.1*w), int(1.1*w))
        y=random.randint(-int(.1*h), int(1.1*h))
        t=random.uniform(.2,.8); col=(*blend(base,acc,t), random.randint(80,140))
        dr.ellipse([(x-r,y-r),(x+r,y+r)], fill=col)
    for _ in range(3):
        x1,y1=random.randint(0,w),random.randint(0,h)
        x2,y2=random.randint(0,w),random.randint(0,h)
        t=random.uniform(.3,.7); col=(*blend(base,acc,t),90)
        dr.line((x1,y1,x2,y2), fill=col, width=random.randint(8,14))
    return img.filter(ImageFilter.GaussianBlur(1.5))

def make(seed, size=768):
    base, acc = palette(seed)
    img = radial(size, base, acc, seed)
    img = shapes(img, base, acc, seed+12345)
    return img

def ensure_images_for_test(slug_path):
    qfile = os.path.join(slug_path, "questions.json")
    if not os.path.exists(qfile):
        return 0, 0
    try:
        data = json.load(open(qfile, "r", encoding="utf-8"))
        questions = data.get("questions") or []
    except Exception:
        return 0, 0

    n = len(questions)
    if n == 0:
        return 0, 0

    img_dir = os.path.join(slug_path, "images")
    os.makedirs(img_dir, exist_ok=True)

    created = 0
    for i in range(1, n+1):
        path = os.path.join(img_dir, f"q{i}.jpg")
        if os.path.exists(path):  # не перезаписываем, если уже есть
            continue
        img = make(seed=3000 + hash(slug_path) % 100000 + i)
        img.save(path, "JPEG", quality=88)
        created += 1
    return n, created

def main():
    if not os.path.exists(ROOT):
        print("Нет папки с тестами:", ROOT)
        return
    total_tests = 0
    total_imgs = 0
    created_imgs = 0
    for name in sorted(os.listdir(ROOT)):
        slug_path = os.path.join(ROOT, name)
        if not os.path.isdir(slug_path):
            continue
        n, c = ensure_images_for_test(slug_path)
        if n > 0:
            total_tests += 1
            total_imgs += n
            created_imgs += c
            print(f"• {name}: вопросов {n}, добавлено картинок {c}")
    print(f"✅ Готово: тестов {total_tests}, всего вопросов {total_imgs}, новых картинок создано {created_imgs}")

if __name__ == "__main__":
    main()
