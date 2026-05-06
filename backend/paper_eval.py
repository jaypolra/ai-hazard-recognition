# paper_eval.py
import argparse
import csv
import os
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

import cv2
from ultralytics import YOLO

from adaptive_deblur import enhance_adaptive
from deepsort_tracker import DeepSortTracker


@dataclass
class RunResult:
    run_name: str
    video_path: str
    total_frames: int
    frames_with_person_yolo: int
    frames_with_person_track: int  # confirmed tracks (only meaningful if tracking enabled)
    yolo_rate: float
    track_rate: float
    confidence: float
    iou: float
    quality: str
    sharpness: float
    gamma: float
    deepsort: bool


def _extract_person_boxes(results) -> List[Tuple[int, int, int, int]]:
    """
    Mirrors your backend logic: iterates results[0].boxes.data and class_id==0 means person.
    stream_generator.py uses: for box in results[0].boxes.data: ... score, cls = box.tolist()
    """
    person_boxes: List[Tuple[int, int, int, int]] = []
    if not results or results[0].boxes is None:
        return person_boxes

    for box in results[0].boxes.data:
        x1, y1, x2, y2, score, cls = box.tolist()
        class_id = int(cls)
        if class_id == 0:  # person
            person_boxes.append((int(x1), int(y1), int(x2), int(y2)))

    return person_boxes


def run_single_mode(
    video_path: str,
    yolo_weights: str,
    device: str,
    confidence: float,
    iou: float,
    quality: str,
    sharpness: float,
    gamma: float,
    deepsort: bool,
    run_name: str,
    per_frame_csv: Optional[str] = None,
) -> RunResult:
    # Load model once per run (simple + explicit for reproducibility)
    model = YOLO(yolo_weights).to(device)
    tracker = DeepSortTracker()  # mirrors backend behavior

    cap = cv2.VideoCapture(0 if video_path == "webcam" else video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open video source: {video_path}")

    pf_writer = None
    pf_fh = None
    if per_frame_csv:
        os.makedirs(os.path.dirname(per_frame_csv) or ".", exist_ok=True)
        pf_fh = open(per_frame_csv, "w", newline="")
        pf_writer = csv.DictWriter(
            pf_fh,
            fieldnames=[
                "run_name",
                "video_path",
                "frame_idx",
                "yolo_person",
                "num_person_boxes",
                "track_person",
                "num_tracks",
            ],
        )
        pf_writer.writeheader()

    total_frames = 0
    frames_with_person_yolo = 0
    frames_with_person_track = 0

    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Mirrors backend: resize to (640,480)
        frame = cv2.resize(frame, (640, 480))
        enhanced = frame.copy()

        # Mirrors backend: enhancement only when quality == "high"
        if quality == "high":
            enhanced = enhance_adaptive(enhanced, sharpness=sharpness, gamma=gamma)

        # Mirrors backend: model(enhanced, conf=..., iou=0.4)
        results = model(enhanced, conf=confidence, iou=iou)

        person_boxes = _extract_person_boxes(results)
        yolo_person = len(person_boxes) > 0

        total_frames += 1
        if yolo_person:
            frames_with_person_yolo += 1

        # Tracking: count frame positive if >=1 confirmed track exists
        track_person = False
        num_tracks = 0
        if deepsort:
            tracked_persons = tracker.update(results, enhanced)
            num_tracks = len(tracked_persons)
            track_person = num_tracks > 0
            if track_person:
                frames_with_person_track += 1

        if pf_writer:
            pf_writer.writerow(
                {
                    "run_name": run_name,
                    "video_path": video_path,
                    "frame_idx": frame_idx,
                    "yolo_person": int(yolo_person),
                    "num_person_boxes": len(person_boxes),
                    "track_person": int(track_person),
                    "num_tracks": num_tracks,
                }
            )

        frame_idx += 1

    cap.release()
    if pf_fh:
        pf_fh.close()

    yolo_rate = frames_with_person_yolo / total_frames if total_frames else 0.0
    track_rate = frames_with_person_track / total_frames if total_frames else 0.0

    return RunResult(
        run_name=run_name,
        video_path=video_path,
        total_frames=total_frames,
        frames_with_person_yolo=frames_with_person_yolo,
        frames_with_person_track=frames_with_person_track,
        yolo_rate=yolo_rate,
        track_rate=track_rate,
        confidence=confidence,
        iou=iou,
        quality=quality,
        sharpness=sharpness,
        gamma=gamma,
        deepsort=deepsort,
    )


def run_four_experiments(
    video_path: str,
    yolo_weights: str,
    device: str,
    confidence: float,
    iou: float,
    sharpness: float,
    gamma: float,
    out_summary_csv: str,
    out_per_frame_dir: Optional[str],
) -> List[RunResult]:
    os.makedirs(os.path.dirname(out_summary_csv) or ".", exist_ok=True)

    runs = [
        # 1) YOLO only
        dict(run_name="1_yolo", quality="low", deepsort=False, sharpness=1.0, gamma=1.0),
        # 2) YOLO + filters
        dict(run_name="2_yolo_filters", quality="high", deepsort=False, sharpness=sharpness, gamma=gamma),
        # 3) YOLO + tracking
        dict(run_name="3_yolo_deepsort", quality="low", deepsort=True, sharpness=1.0, gamma=1.0),
        # 4) YOLO + filters + tracking
        dict(run_name="4_yolo_filters_deepsort", quality="high", deepsort=True, sharpness=sharpness, gamma=gamma),
    ]

    results: List[RunResult] = []
    for r in runs:
        per_frame_csv = None
        if out_per_frame_dir:
            os.makedirs(out_per_frame_dir, exist_ok=True)
            per_frame_csv = os.path.join(out_per_frame_dir, f"{r['run_name']}_per_frame.csv")

        res = run_single_mode(
            video_path=video_path,
            yolo_weights=yolo_weights,
            device=device,
            confidence=confidence,
            iou=iou,
            quality=r["quality"],
            sharpness=r["sharpness"],
            gamma=r["gamma"],
            deepsort=r["deepsort"],
            run_name=r["run_name"],
            per_frame_csv=per_frame_csv,
        )
        results.append(res)

    # Save summary
    with open(out_summary_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(results[0]).keys()))
        writer.writeheader()
        for rr in results:
            writer.writerow(asdict(rr))

    return results


def print_results_table(results: List[RunResult]) -> None:
    print("\n===== PAPER RESULTS (Frame-level Coverage) =====")
    print(f"{'Run':28s} {'Total':>8s} {'YOLO_frames':>12s} {'YOLO_rate':>10s} {'Track_frames':>12s} {'Track_rate':>10s}")
    for r in results:
        print(
            f"{r.run_name:28s} "
            f"{r.total_frames:8d} "
            f"{r.frames_with_person_yolo:12d} "
            f"{r.yolo_rate:10.3f} "
            f"{r.frames_with_person_track:12d} "
            f"{r.track_rate:10.3f}"
        )
    print("Notes:")
    print("- YOLO_frames/YOLO_rate: frames with ≥1 person detection from YOLO.")
    print("- Track_frames/Track_rate: frames with ≥1 confirmed DeepSORT track (0 when tracking disabled).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, help="Path to video file (or 'webcam').")
    ap.add_argument("--weights", default="yolov8m.pt", help="YOLO weights path.")
    ap.add_argument("--device", default="cuda", help="cuda or cpu.")
    ap.add_argument("--conf", type=float, default=0.5, help="YOLO confidence threshold.")
    ap.add_argument("--iou", type=float, default=0.4, help="YOLO IoU (NMS) threshold (matches backend default 0.4).")
    ap.add_argument("--sharpness", type=float, default=1.2, help="Sharpness used for filter runs.")
    ap.add_argument("--gamma", type=float, default=1.2, help="Gamma used for filter runs.")
    ap.add_argument("--out_summary", default="eval_results/summary.csv", help="Summary CSV output path.")
    ap.add_argument("--out_per_frame_dir", default="", help="Optional: directory to write per-frame CSVs (empty disables).")
    args = ap.parse_args()

    out_per_frame_dir = args.out_per_frame_dir.strip() or None

    results = run_four_experiments(
        video_path=args.video,
        yolo_weights=args.weights,
        device=args.device,
        confidence=args.conf,
        iou=args.iou,
        sharpness=args.sharpness,
        gamma=args.gamma,
        out_summary_csv=args.out_summary,
        out_per_frame_dir=out_per_frame_dir,
    )
    print_results_table(results)
    print(f"\nSaved summary to: {args.out_summary}")
    if out_per_frame_dir:
        print(f"Saved per-frame CSVs to: {out_per_frame_dir}")


if __name__ == "__main__":
        main()
