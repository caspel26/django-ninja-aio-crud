"""Build the header marks for the Studio theme from docs/images/logo.png.

light: the artwork without its soft drop shadow, trimmed to its bounds.
dark:  the same artwork with a light outline, so the black line work stays
       legible on dark surfaces.

Run from the repository root: python design/step15/logo/build_logo.py
"""

from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

SOURCE = Path("docs/images/logo.png")
OUT = Path(__file__).parent
SHADOW_ALPHA = 160  # the drop shadow fades below this; the artwork is opaque
OUTLINE_PX = 14
OUTLINE_COLOR = (240, 235, 248)
SIZES = (64, 128, 256)


def without_shadow(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A").point(
        lambda a: 0 if a <= SHADOW_ALPHA else min(255, (a - SHADOW_ALPHA) * 255 // (255 - SHADOW_ALPHA))
    )
    cleaned = image.copy()
    cleaned.putalpha(alpha)
    return cleaned.crop(alpha.getbbox())


def with_outline(image: Image.Image) -> Image.Image:
    pad = OUTLINE_PX * 2
    canvas = Image.new("RGBA", (image.width + pad * 2, image.height + pad * 2))
    canvas.alpha_composite(image, (pad, pad))
    mask = canvas.getchannel("A").point(lambda a: 255 if a > 160 else 0)
    grown = mask.filter(ImageFilter.MaxFilter(OUTLINE_PX * 2 + 1)).filter(ImageFilter.GaussianBlur(1.2))
    outline = Image.new("RGBA", canvas.size, OUTLINE_COLOR + (0,))
    outline.putalpha(grown)
    outline.alpha_composite(canvas)
    return outline.crop(ImageChops.lighter(grown, mask).getbbox())


def square(image: Image.Image, size: int) -> Image.Image:
    scale = size / max(image.size)
    resized = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    tile = Image.new("RGBA", (size, size))
    tile.alpha_composite(resized, ((size - resized.width) // 2, (size - resized.height) // 2))
    return tile


def main() -> None:
    light = without_shadow(Image.open(SOURCE).convert("RGBA"))
    dark = with_outline(light)
    for name, image in (("light", light), ("dark", dark)):
        for size in SIZES:
            square(image, size).save(OUT / f"mark-{name}-{size}.png", optimize=True)


if __name__ == "__main__":
    main()
