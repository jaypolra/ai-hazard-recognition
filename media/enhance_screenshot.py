"""
Quick image enhancement for dashboard screenshot.
Usage: python enhance_screenshot.py input.png output.png
"""
import sys
from PIL import Image, ImageFilter, ImageEnhance

def enhance(src, dst, scale=2.0):
    img = Image.open(src)

    # Upscale with high-quality Lanczos resampling
    w, h = img.size
    img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    # Sharpen
    img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=180, threshold=2))

    # Slight contrast boost to make text pop
    img = ImageEnhance.Contrast(img).enhance(1.15)

    img.save(dst, "PNG", optimize=True)
    print(f"Saved → {dst}  ({img.size[0]}×{img.size[1]}px)")

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "dashboard_raw.png"
    dst = sys.argv[2] if len(sys.argv) > 2 else "dashboard.png"
    enhance(src, dst)
