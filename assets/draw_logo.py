"""Draws the Recast icon: a page split on a 45-degree diagonal, white above, cyan below,
with the dog-ear corner as its own cyan piece. Run: python assets/draw_logo.py assets"""
import sys
from PIL import Image, ImageDraw

NAVY, WHITE, CYAN = "#0B1630", "#FFFFFF", "#08EEFF"
S = 4096
k = S / 1024  # drawn 4x bigger, then shrunk for smooth edges


def draw():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([40 * k, 40 * k, 984 * k, 984 * k], radius=230 * k, fill=NAVY)
    L, R, T, f, g = 270, 754, 262, 155, 32   # page left/right/top, dog-ear size, gap between pieces
    c = (R - f - g) + (T + f)                # white's diagonal is the line x + y = c
    c2 = c + round(g * 2 ** 0.5)             # cyan's diagonal: the same line, one gap further
    B = c2 - L - 15                          # bottom, so the cyan piece starts just right of the left edge
    P = lambda pts: [(x * k, y * k) for x, y in pts]
    d.polygon(P([(L, T), (R - f - g, T), (R - f - g, T + f), (L, c - L)]), fill=WHITE)
    d.polygon(P([(R - f, T), (R, T + f), (R - f, T + f)]), fill=CYAN)
    d.polygon(P([(c2 - (T + f + g), T + f + g), (R, T + f + g), (R, B), (c2 - B, B)]), fill=CYAN)
    return img.resize((1024, 1024), Image.LANCZOS)


if __name__ == "__main__":
    out = sys.argv[1]
    icon = draw()
    icon.save(f"{out}/icon.png")
    # Every size Windows asks for at 100-200% display scaling, so it never has to stretch one itself.
    sizes = [16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 128, 256]
    frames = [icon.resize((s, s), Image.LANCZOS) for s in sizes]
    frames[-1].save(f"{out}/icon.ico", sizes=[(s, s) for s in sizes], append_images=frames[:-1])
    for name, size in [("Square150x150Logo", 150), ("Square44x44Logo", 44), ("StoreLogo", 50)]:
        icon.resize((size, size), Image.LANCZOS).save(f"{out}/{name}.png")
