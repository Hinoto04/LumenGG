"""Build smaller runtime WebP assets; retain the original artwork for rebuilds.

Requires Pillow. Run from any directory with a Python interpreter that has it.
Resolution and alpha are preserved; RGB artwork uses WebP quality 90. When
lossless WebP is smaller it is preferred. Existing background WebP files stay
unchanged. Re-running always encodes from the originals, never from lossy output.
"""
import io
import json
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    ROOT / "src" / name
    for name in [
        "calculator-art.ts",
        "calculator-symbol-images.ts",
        "calculator-clean-images.ts",
        "calculator-passive-images.ts",
    ]
]
PATTERN = re.compile(r'\.\./assets/calculator-(?:character|release)/([^"\']+)')


def build():
    results = {}

    def encode(match):
        relative = Path(match[1])
        original = ROOT / "assets/calculator-character" / relative
        if not original.exists():
            original = original.with_suffix(".png")
        relative = original.relative_to(ROOT / "assets/calculator-character")
        if relative.name == "background.webp":
            return f"../assets/calculator-character/{relative.as_posix()}"
        if relative.as_posix() not in results:
            image = Image.open(original).convert("RGBA")
            options = []
            for lossless in [False, True]:
                buffer = io.BytesIO()
                image.save(buffer, "WEBP", quality=90, method=6,
                           lossless=lossless, exact=True)
                options.append(buffer.getvalue())
            data = min(options, key=len)
            decoded = Image.open(io.BytesIO(data)).convert("RGBA")
            if decoded.size != image.size or decoded.getchannel("A").tobytes() != image.getchannel("A").tobytes():
                raise ValueError(f"Resolution/alpha changed: {original}")
            destination = ROOT / "assets/calculator-release" / relative.with_suffix(".webp")
            if len(data) < original.stat().st_size:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
                ref = "../" + destination.relative_to(ROOT).as_posix()
                size = len(data)
            else:
                ref = f"../assets/calculator-character/{relative.as_posix()}"
                size = original.stat().st_size
            results[relative.as_posix()] = {
                "reference": ref, "original_bytes": original.stat().st_size,
                "runtime_bytes": size,
            }
        return results[relative.as_posix()]["reference"]

    for source in SOURCES:
        contents = PATTERN.sub(encode, source.read_text(encoding="utf-8"))
        source.write_text(contents, encoding="utf-8")
    original = sum(r["original_bytes"] for r in results.values())
    runtime = sum(r["runtime_bytes"] for r in results.values())
    print(json.dumps({"images": len(results), "original_bytes": original,
                      "runtime_bytes": runtime, "saved_bytes": original - runtime}))


if __name__ == "__main__":
    build()
