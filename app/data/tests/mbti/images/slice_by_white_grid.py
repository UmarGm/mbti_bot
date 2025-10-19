from PIL import Image, ImageOps
import numpy as np, os

SPRITE = "A_collection_of_40_square_digital_abstract_artwork.png"
ROWS, COLS = 5, 8
SIZE = 1024
WHITE_THR = 245        # порог «белизны»: min(R,G,B) >= WHITE_THR
RATIO_THR = 0.80       # доля белых пикселей в колонке/строке, чтобы считать её «полосой»

def find_white_segments(mask_1d, ratio_thr=0.8):
    """Находит непрерывные сегменты (start, end) там, где True-плотность высокая."""
    segs = []
    n = len(mask_1d)
    i = 0
    while i < n:
        if mask_1d[i]:
            j = i
            while j < n and mask_1d[j]:
                j += 1
            # сегмент i..j-1
            segs.append((i, j-1))
            i = j
        else:
            i += 1
    return segs

def detect_white_bands(rgb):
    """Возвращает списки вертикальных и горизонтальных белых полос (сегментов)."""
    h, w, _ = rgb.shape
    # белый пиксель: min(R,G,B) >= WHITE_THR
    white = (rgb.min(axis=2) >= WHITE_THR)

    # по вертикали: считаем долю белых по каждой колонке
    v_ratio = white.mean(axis=0)  # shape: (w,)
    v_mask = v_ratio >= RATIO_THR
    v_segs = find_white_segments(v_mask)

    # по горизонтали: доля белых по каждой строке
    h_ratio = white.mean(axis=1)  # shape: (h,)
    h_mask = h_ratio >= RATIO_THR
    h_segs = find_white_segments(h_mask)

    return v_segs, h_segs

def ensure_count(segs, expected):
    """Иногда детектор может слить двойные линии или разбить одну на две.
       Приводим к нужному количеству через слияние близких/тонких сегментов."""
    if len(segs) == expected:
        return segs
    if not segs:
        return segs
    # Сначала сольём очень близкие (зазор <= 2px)
    merged = []
    cur_s, cur_e = segs[0]
    for s, e in segs[1:]:
        if s - cur_e <= 2:
            cur_e = max(cur_e, e)
        else:
            merged.append((cur_s, cur_e))
            cur_s, cur_e = s, e
    merged.append((cur_s, cur_e))
    segs = merged
    # Если всё ещё не совпало — лучший эвристический отбор равномерно
    if len(segs) > expected:
        # выбросим самые узкие/избыточные
        segs = sorted(segs, key=lambda se: -(se[1]-se[0]+1))[:expected]
        segs = sorted(segs, key=lambda se: se[0])
    elif len(segs) < expected:
        # попробуем искусственно вставить края, если их нет
        # (иногда крайняя полоса чуть не дотягивает до порога)
        if segs[0][0] > 3:
            segs = [(0,2)] + segs
        if segs[-1][1] < (segs[-1][1] + 3):  # не знаем ширину, просто оставим как есть
            pass
        # Если всё равно маловато — вернём как есть (скрипт всё равно порежет по имеющимся)
    return segs

def main():
    img = Image.open(SPRITE).convert("RGB")
    rgb = np.array(img)
    H, W, _ = rgb.shape

    v_segs, h_segs = detect_white_bands(rgb)

    # Ожидаем COLS+1 вертикальных и ROWS+1 горизонтальных полос (включая внешние)
    v_segs = ensure_count(v_segs, COLS+1)
    h_segs = ensure_count(h_segs, ROWS+1)

    if len(v_segs) < COLS+1 or len(h_segs) < ROWS+1:
        print(f"⚠️ Найдено мало белых полос (v={len(v_segs)}, h={len(h_segs)}). Буду резать по имеющимся.")
    v_segs = sorted(v_segs, key=lambda se: se[0])[:COLS+1]
    h_segs = sorted(h_segs, key=lambda se: se[0])[:ROWS+1]

    # Границы тайлов: между белыми полосами — [prev.end+1, next.start-1]
    xs = [max(0, v_segs[i][1]+1) for i in range(min(COLS, len(v_segs)-1))]
    xs += [min(W-1, v_segs[min(COLS, len(v_segs)-1)][0]-1)]
    # Не все детекции идеальны — надёжнее собрать x-границы как пары соседних сегментов:
    x_pairs = []
    for i in range(len(v_segs)-1):
        left = v_segs[i][1] + 1
        right = v_segs[i+1][0] - 1
        left = max(0, left); right = min(W-1, right)
        if right <= left: right = left + 1
        x_pairs.append((left, right))
    # Оставляем первые COLS интервалов
    x_pairs = x_pairs[:COLS]

    y_pairs = []
    for i in range(len(h_segs)-1):
        top = h_segs[i][1] + 1
        bot = h_segs[i+1][0] - 1
        top = max(0, top); bot = min(H-1, bot)
        if bot <= top: bot = top + 1
        y_pairs.append((top, bot))
    y_pairs = y_pairs[:ROWS]

    # Режем и сохраняем
    os.makedirs(".", exist_ok=True)
    n = 1
    for r in range(len(y_pairs)):
        for c in range(len(x_pairs)):
            x0, x1 = x_pairs[c]
            y0, y1 = y_pairs[r]
            tile = img.crop((x0, y0, x1+1, y1+1))  # +1 потому что правая/нижняя не включительно
            tile = ImageOps.contain(tile, (SIZE, SIZE))
            bg = Image.new("RGB", (SIZE, SIZE), (0,0,0))
            bg.paste(tile, ((SIZE - tile.width)//2, (SIZE - tile.height)//2))
            bg.save(f"q{n}.jpg", quality=95)
            n += 1

    print(f"✅ Сохранено {n-1} изображений. Вертикальные полосы: {len(v_segs)}, горизонтальные: {len(h_segs)}")

if __name__ == "__main__":
    main()
