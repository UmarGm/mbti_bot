from PIL import Image, ImageDraw, ImageFilter
import os, random, math

BASE = "app/data/images"
FREE = os.path.join(BASE, "free")
PAID = os.path.join(BASE, "paid")
os.makedirs(FREE, exist_ok=True)
os.makedirs(PAID, exist_ok=True)

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
    # мягкая виньетка
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

# 16 free
for i in range(1,17):
    make(1000+i).save(os.path.join(FREE, f"q{i}.jpg"), "JPEG", quality=88)
# 20 paid
for i in range(1,21):
    make(2000+i).save(os.path.join(PAID, f"q{i}.jpg"), "JPEG", quality=88)

print("✅ готово: app/data/images/free (16) и paid (20)")
