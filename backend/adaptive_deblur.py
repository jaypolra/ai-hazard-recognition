import cv2
import numpy as np

def detect_blur_laplacian(image, threshold=100.0):
    """Measure blur level using Laplacian variance."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    return variance < threshold, variance

def apply_clahe(image):
    """Apply CLAHE (adaptive histogram equalization) for contrast."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    merged = cv2.merge((cl, a, b))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)

def apply_unsharp_mask(image, amount=1.0, kernel_size=(5, 5)):
    """Apply unsharp mask for sharpening."""
    blurred = cv2.GaussianBlur(image, kernel_size, 0)
    return cv2.addWeighted(image, 1 + amount, blurred, -amount, 0)

def enhance_adaptive(image, sharpness=1.0, gamma=1.0):
    is_blurry, score = detect_blur_laplacian(image)
    enhanced = image.copy()

    if is_blurry:
        print(f"Blurry (Var: {score:.2f}) → Strong Boost")
        enhanced = apply_clahe(enhanced)
        enhanced = apply_unsharp_mask(enhanced, amount=sharpness + 0.5)
        enhanced = cv2.bilateralFilter(enhanced, 9, 75, 75)

        # Laplacian boost
        lap = cv2.Laplacian(enhanced, cv2.CV_64F)
        enhanced = cv2.convertScaleAbs(enhanced + 0.3 * lap)
    else:
        print(f"Clear (Var: {score:.2f}) → Light Boost")
        enhanced = apply_unsharp_mask(enhanced, amount=sharpness)

    # Contrast stretching
    min_val = np.min(enhanced)
    max_val = np.max(enhanced)
    if max_val - min_val > 0:
        enhanced = ((enhanced - min_val) * (255.0 / (max_val - min_val))).astype(np.uint8)

    # Gamma correction
    table = np.array([(i / 255.0) ** (1.0 / gamma) * 255 for i in range(256)]).astype("uint8")
    enhanced = cv2.LUT(enhanced, table)

    return enhanced

