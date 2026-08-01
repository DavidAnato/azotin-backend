"""Remplace les PNG seed 1×1 (≤80 octets) par un placeholder visible."""
from __future__ import annotations

import struct
import zlib
from pathlib import Path


def placeholder_png_bytes(width: int = 320, height: int = 320) -> bytes:
    r, g, b = 28, 37, 65
    accent = (91, 192, 190)
    rows: list[bytes] = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            if x > width * 0.72 and y < height * 0.28:
                row.extend(accent)
            else:
                row.extend((r, g, b))
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "media"
    blob = placeholder_png_bytes()
    n = 0
    for path in root.rglob("*"):
        if path.is_file() and path.stat().st_size <= 80:
            path.write_bytes(blob)
            n += 1
    print(f"replaced={n} bytes={len(blob)} root={root}")


if __name__ == "__main__":
    main()
