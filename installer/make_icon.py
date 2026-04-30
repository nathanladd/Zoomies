"""Generate installer/rudi.ico — stdlib-only placeholder.

Writes a single 32x32 solid-color .ico directly using the raw ICO + BITMAPINFOHEADER
format, with no external dependencies. It's ugly but valid; swap in a designed
icon at installer/rudi.ico whenever you have one (the spec and .iss both
pick up whatever file is there).

Run from the project root:

    .venv\\Scripts\\python.exe installer\\make_icon.py
"""
from __future__ import annotations

import struct
from pathlib import Path

OUT = Path(__file__).resolve().parent / "rudi.ico"

SIZE = 32
# Flat slate-navy background with a yellow diagonal lightning-ish stripe so the
# icon is at least distinguishable from a blank square on the taskbar.
BG = (15, 23, 42, 255)         # slate-900 (B, G, R, A — ICO is BGRA)
STRIPE = (250, 204, 21, 255)   # yellow-400

# ---- Pixel buffer: 32bpp BGRA, bottom-up row order (DIB convention). -------
pixels: list[bytes] = []
for y_top in range(SIZE):
    # DIB is bottom-up, so the row we write first is actually the bottom row.
    y = SIZE - 1 - y_top
    row = bytearray()
    for x in range(SIZE):
        # Thick diagonal stripe through the middle.
        on_stripe = abs((x + y) - SIZE) < 6
        b, g, r, a = STRIPE if on_stripe else BG
        row += bytes((b, g, r, a))
    pixels.append(bytes(row))
xor_mask = b"".join(pixels)

# ---- AND mask: 1 bit per pixel, padded to 32-bit rows, all zeros (fully opaque
# where the 32bpp alpha channel says so). 32 px / 8 = 4 bytes per row already
# aligned to 4 bytes.
and_mask = b"\x00" * (4 * SIZE)

# ---- BITMAPINFOHEADER (40 bytes). In ICO, the biHeight is 2 * image height
# because it accounts for both the XOR and AND masks stacked.
bmp_header = struct.pack(
    "<IiiHHIIiiII",
    40,            # biSize
    SIZE,          # biWidth
    SIZE * 2,      # biHeight (XOR + AND)
    1,             # biPlanes
    32,            # biBitCount
    0,             # biCompression = BI_RGB
    len(xor_mask) + len(and_mask),  # biSizeImage
    0, 0, 0, 0,    # biXPelsPerMeter, biYPelsPerMeter, biClrUsed, biClrImportant
)
image_blob = bmp_header + xor_mask + and_mask

# ---- ICONDIR (6 bytes) + one ICONDIRENTRY (16 bytes).
icondir = struct.pack("<HHH", 0, 1, 1)  # reserved=0, type=1 (icon), count=1
offset = 6 + 16
icondirentry = struct.pack(
    "<BBBBHHII",
    SIZE if SIZE < 256 else 0,  # width (0 means 256)
    SIZE if SIZE < 256 else 0,  # height
    0,                          # color count (0 = >=8bpp)
    0,                          # reserved
    1,                          # color planes
    32,                         # bits per pixel
    len(image_blob),            # size of image data
    offset,                     # offset into file
)

OUT.write_bytes(icondir + icondirentry + image_blob)
print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {SIZE}x{SIZE}, 32bpp)")
