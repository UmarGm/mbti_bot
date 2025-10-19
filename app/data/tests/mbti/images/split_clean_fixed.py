from PIL import Image, ImageOps
import os

SPRITE = "A_collection_of_40_square_digital_abstract_artwork.png"
ROWS, COLS = 5, 8
TRIM = 6
SIZE = 1024

img = Image.open(SPRITE).convert("RGB")
W, H = img.size
tile_w = W // COLS
tile_h = H // ROWS

os.makedirs(".", exist_ok=True)
count = 1
for r in range(ROWS):
    for c in range(COLS):
        x0 = c * tile_w + TRIM
        y0 = r * tile_h + TRIM
        x1 = (c + 1) * tile_w - TRIM
        y1 = (r + 1) * tile_h - TRIM
        tile = img.crop((x0, y0, x1, y1))
        tile = ImageOps.contain(tile, (SIZE, SIZE))
        bg = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
        bg.paste(tile, ((SIZE - tile.width)//2, (SIZE - tile.height)//2))
        bg.save(f"q{count}.jpg", quality=95)
        count += 1
print(f"✅ Разрезано {count-1} картинок ({ROWS}x{COLS}) с trim={TRIM}")
