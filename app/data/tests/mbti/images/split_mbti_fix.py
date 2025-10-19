from PIL import Image, ImageOps
import os, sys, argparse, math, re

def try_grids(n):
    cand = []
    for r in range(1, n+1):
        if n % r == 0:
            c = n // r
            cand.append((r,c))
    # самые логичные сначала
    pref = [(5,8),(8,5),(4,10),(10,4),(2,20),(20,2),(1,40),(40,1)]
    return pref + [g for g in cand if g not in pref]

def slice_sprite(img, rows, cols, trim=0):
    W, H = img.size
    tile_w = W // cols
    tile_h = H // rows
    tiles = []
    for r in range(rows):
        for c in range(cols):
            x0 = c * tile_w
            y0 = r * tile_h
            x1 = W if c==cols-1 else (c+1)*tile_w
            y1 = H if r==rows-1 else (r+1)*tile_h
            # аккуратно “подрезаем” швы
            x0 += trim; y0 += trim; x1 -= trim; y1 -= trim
            x0 = max(0, x0); y0 = max(0, y0)
            x1 = max(x0+1, x1); y1 = max(y0+1, y1)
            tiles.append(img.crop((x0,y0,x1,y1)))
    return tiles

def make_square(im, size=1024, mode="pad", bg=(0,0,0)):
    if mode == "crop":
        # центр-кроп до квадрата, затем resize
        w,h = im.size
        side = min(w,h)
        left = (w - side)//2
        top  = (h - side)//2
        im = im.crop((left, top, left+side, top+side))
        return im.resize((size,size), Image.LANCZOS)
    else:
        # pad (без обрезания)
        im = ImageOps.contain(im, (size,size), Image.LANCZOS)
        bg_img = Image.new("RGB", (size,size), bg)
        x = (size - im.size[0])//2
        y = (size - im.size[1])//2
        bg_img.paste(im, (x,y))
        return bg_img

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sprite", help="Путь к большому изображению на 40 тайлов", default="A_collection_of_40_square_digital_abstract_artwork.png")
    ap.add_argument("--out", default=".", help="Куда сохранять q1..q40.jpg")
    ap.add_argument("--count", type=int, default=40)
    ap.add_argument("--grid", default="", help="Фиксированная сетка, напр. 5x8 (иначе auto)")
    ap.add_argument("--trim", type=int, default=6, help="Сколько пикселей убрать на швах (0-12)")
    ap.add_argument("--square", choices=["pad","crop","none"], default="pad", help="Как сделать квадрат: pad (без обрезания), crop, none")
    ap.add_argument("--size", type=int, default=1024, help="Размер стороны квадрата при square!=none")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--fix_existing", action="store_true", help="Не резать спрайт, а починить уже существующие q*.jpg (выравнять/квадрат)")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    if args.fix_existing:
        # правим уже существующие q*.jpg
        files = []
        for i in range(1, args.count+1):
            fp = os.path.join(args.out, f"q{i}.jpg")
            if os.path.exists(fp):
                files.append(fp)
        if not files:
            print("❌ Не нашёл существующих q*.jpg для фикса. Сначала разрежь спрайт.")
            sys.exit(1)
        for fp in files:
            im = Image.open(fp).convert("RGB")
            if args.square != "none":
                im = make_square(im, size=args.size, mode=args.square)
            im.save(fp, quality=92)
        print(f"✅ Исправил {len(files)} картинок (fix_existing).")
        return

    if not os.path.exists(args.sprite):
        print(f"❌ Не найден спрайт: {args.sprite}")
        sys.exit(1)

    base = Image.open(args.sprite).convert("RGB")
    # Выбираем сетку
    grids = [tuple(map(int, args.grid.lower().split("x")))] if args.grid else try_grids(args.count)
    used = None
    for (r,c) in grids:
        if r*c == args.count:
            used = (r,c); break
    if not used:
        print("❌ Не удалось подобрать сетку.")
        sys.exit(1)

    rows, cols = used
    tiles = slice_sprite(base, rows, cols, trim=max(0,min(args.trim, 20)))
    if len(tiles) != args.count:
        print(f"❌ Ожидал {args.count} тайлов, получил {len(tiles)}")
        sys.exit(1)

    for i, im in enumerate(tiles, 1):
        if args.square != "none":
            im = make_square(im, size=args.size, mode=args.square)
        outp = os.path.join(args.out, f"q{i}.jpg")
        if not args.overwrite and os.path.exists(outp):
            print(f"skip {outp} (exists)")
            continue
        im.save(outp, quality=92)

    print(f"✅ Готово: сохранено {args.count} изображений (q1..q{args.count}.jpg) в {args.out}")
    print(f"   Сетка: {rows}x{cols}, trim={args.trim}, square={args.square}, size={args.size}")

if __name__ == "__main__":
    main()
