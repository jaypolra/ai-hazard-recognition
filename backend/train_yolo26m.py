"""
YOLO26m Training Script — Multi-Camera Industrial Safety Dataset
================================================================
Active Classes (4 — gate class removed from training):
    0: person           → subject of safety evaluation
    1: pot_blocking     → molten pot in blocking/parked position (SAFE signal)
    2: pot_hauler       → pot hauler vehicle → HAZARD trigger
    3: pot_not_blocking → pot present but NOT in blocking position

NOTE — gate_open removed:
    gate_open was class 0 in the previous model but is not present in the
    4 plant videos used for training/testing. The model produced false
    positives (hallucinating gates on walls/shadows). Removed until plant
    footage with labeled gate instances is available.

FUTURE — Gate classes to add when footage available:
    gate_open   → HAZARD   (gate physically open = not blocking = unsafe)
    gate_closed → SAFE     (gate physically closed = blocking = safe)
    Safety rule: gate_closed at BOTH north AND south ends = safe zone

Dataset: D:/reactapp/datasets/YOLO26
  Train : 168 images  (re-label: remove gate_open annotations)
  Valid :  28 images
  Test  :  84 images
  Size  : 512x512

Usage:
    cd D:/reactapp/backend
    python train_yolo26m.py
"""

import os
import sys
from pathlib import Path
from ultralytics import YOLO

# ──────────────────────────────────────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────────────────────────────────────
DATASET_YAML   = "D:/reactapp/datasets/YOLO26/data_abs.yaml"
WEIGHTS_DIR    = Path("weights")
WEIGHTS_DIR.mkdir(exist_ok=True)

# Base pretrained model: yolo26m (medium variant)
# Ultralytics will download automatically if not present locally.
# Falls back to yolov8m.pt if yolo26m is unavailable.
BASE_MODEL     = "yolo26m.pt"
FALLBACK_MODEL = "yolov8m.pt"          # already present in project root

# Output run name
RUN_NAME       = "yolo26m_industry_hazard"
PROJECT        = "D:/reactapp/backend/runs/train"

# ──────────────────────────────────────────────────────────────────────────────
# Hyper-parameters — tuned for small dataset (~280 images)
# ──────────────────────────────────────────────────────────────────────────────
EPOCHS      = 100
IMG_SIZE    = 512      # matches dataset preprocessing
BATCH_SIZE  = 16       # reduce to 8 if GPU OOM
WORKERS     = 4
LR0         = 0.01
LRF         = 0.01
MOMENTUM    = 0.937
WEIGHT_DECAY = 0.0005
WARMUP_EPOCHS = 5
PATIENCE    = 30       # early stopping patience
CONF_THRES  = 0.25
IOU_THRES   = 0.45

# Augmentation — aggressive to compensate for small dataset
AUGMENT_CFG = dict(
    hsv_h=0.015,
    hsv_s=0.7,
    hsv_v=0.4,
    degrees=10.0,
    translate=0.1,
    scale=0.5,
    shear=2.0,
    perspective=0.0005,
    flipud=0.0,
    fliplr=0.5,
    mosaic=1.0,
    mixup=0.15,
    copy_paste=0.1,
)


def load_base_model() -> YOLO:
    """Load yolo26m, falling back to yolov8m if unavailable."""
    # Check for locally cached model first
    local_path = Path("../") / BASE_MODEL   # project root has yolo26n.pt
    if local_path.exists():
        print(f"[Train] Loading local model: {local_path}")
        return YOLO(str(local_path))

    try:
        print(f"[Train] Attempting to load {BASE_MODEL} (will auto-download)…")
        model = YOLO(BASE_MODEL)
        return model
    except Exception as e:
        print(f"[Train] yolo26m unavailable ({e}), falling back to {FALLBACK_MODEL}")
        # yolov8m.pt is in project root
        fb_path = Path("../") / FALLBACK_MODEL
        if fb_path.exists():
            return YOLO(str(fb_path))
        return YOLO(FALLBACK_MODEL)


def main():
    print("=" * 60)
    print("  YOLO26m — Industrial Hazard Detection Training")
    print("=" * 60)
    print(f"  Dataset : {DATASET_YAML}")
    print(f"  Epochs  : {EPOCHS}")
    print(f"  ImgSize : {IMG_SIZE}")
    print(f"  Batch   : {BATCH_SIZE}")
    print(f"  Project : {PROJECT}")
    print("=" * 60)

    # ── Verify dataset YAML exists
    if not Path(DATASET_YAML).exists():
        print(f"[ERROR] Dataset YAML not found: {DATASET_YAML}")
        sys.exit(1)

    # ── Load pretrained backbone
    model = load_base_model()
    print(f"[Train] Model loaded: {model.info()}")

    # ── Train
    results = model.train(
        data       = DATASET_YAML,
        epochs     = EPOCHS,
        imgsz      = IMG_SIZE,
        batch      = BATCH_SIZE,
        workers    = WORKERS,
        lr0        = LR0,
        lrf        = LRF,
        momentum   = MOMENTUM,
        weight_decay = WEIGHT_DECAY,
        warmup_epochs = WARMUP_EPOCHS,
        patience   = PATIENCE,
        conf       = CONF_THRES,
        iou        = IOU_THRES,
        name       = RUN_NAME,
        project    = PROJECT,
        device     = 0,          # GPU 0; use 'cpu' if no CUDA
        exist_ok   = True,
        verbose    = True,
        save       = True,
        save_period = 10,        # save checkpoint every 10 epochs
        plots      = True,
        val        = True,
        **AUGMENT_CFG,
    )

    # ── Copy best weights to backend/weights/
    best_weights_src = Path(PROJECT) / RUN_NAME / "weights" / "best.pt"
    dest             = WEIGHTS_DIR / "person_industry_best.pt"

    if best_weights_src.exists():
        import shutil
        shutil.copy2(best_weights_src, dest)
        print(f"\n[Train] ✅ Best weights copied → {dest}")
    else:
        print(f"\n[Train] ⚠️  Best weights not found at {best_weights_src}")
        print(f"           Manually copy from: {PROJECT}/{RUN_NAME}/weights/best.pt")

    print("\n[Train] 🏁 Training complete.")
    print(f"         Results saved to: {PROJECT}/{RUN_NAME}/")
    return results


if __name__ == "__main__":
    main()
