from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


OUTPUT_DIR = Path(__file__).resolve().parents[1] / "public" / "icons"


def font(size: int):
    candidates = (
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def make_icon(size: int, destination: Path, *, maskable: bool = False):
    image = Image.new("RGB", (size, size))
    pixels = image.load()
    start = (37, 99, 235)
    end = (124, 58, 237)
    for y in range(size):
        for x in range(size):
            ratio = (x + y) / (2 * max(size - 1, 1))
            pixels[x, y] = tuple(round(a + (b - a) * ratio) for a, b in zip(start, end))

    draw = ImageDraw.Draw(image)
    safe = 0.20 if maskable else 0.14
    left = int(size * safe)
    right = size - left
    top = int(size * 0.28)
    bottom = int(size * (1 - safe))
    middle = size // 2
    fold = int(size * 0.57)
    stroke = max(3, size // 42)

    draw.rounded_rectangle(
        (left, top, right, bottom),
        radius=int(size * 0.07),
        fill=(255, 255, 255),
    )
    draw.line((left, top, middle, fold, right, top), fill=(67, 56, 202), width=stroke, joint="curve")
    draw.line((left, bottom, int(size * 0.40), int(size * 0.55)), fill=(99, 102, 241), width=stroke)
    draw.line((right, bottom, int(size * 0.60), int(size * 0.55)), fill=(99, 102, 241), width=stroke)

    label_font = font(int(size * 0.22))
    label = "AI"
    box = draw.textbbox((0, 0), label, font=label_font)
    label_width = box[2] - box[0]
    draw.text(
        ((size - label_width) / 2, int(size * 0.08)),
        label,
        font=label_font,
        fill=(255, 255, 255),
    )
    image.save(destination, "PNG", optimize=True)


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    make_icon(192, OUTPUT_DIR / "pwa-192x192.png")
    make_icon(512, OUTPUT_DIR / "pwa-512x512.png")
    make_icon(512, OUTPUT_DIR / "pwa-maskable-512x512.png", maskable=True)
    make_icon(180, OUTPUT_DIR / "apple-touch-icon.png")
