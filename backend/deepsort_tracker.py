"""
deepsort_tracker.py — Multi-Class DeepSORT Tracker (YOLO26m compatible)
=========================================================================
Tracks:
    - person      (class 1) — primary safety subject
    - pot_hauler  (class 3) — equipment hazard trigger

Class IDs match YOLO26m dataset:
    0: gate_open        → not tracked (static detector, evaluated in hazard_logic)
    1: person           → TRACKED
    2: pot_blocking     → not tracked (static state)
    3: pot_hauler       → TRACKED (equipment movement)
    4: pot_not_blocking → not tracked (static state)
"""

import numpy as np
from deep_sort_realtime.deepsort_tracker import DeepSort
from typing import List, Dict, Tuple, Optional

# Classes to track via DeepSORT
TRACK_CLASSES = {1: "person", 3: "pot_hauler"}


class DeepSortTracker:
    """
    Multi-class DeepSORT tracker for industrial safety monitoring.

    Tracks persons and pot haulers independently to:
    - Maintain consistent IDs across frames
    - Enable cross-camera trajectory reasoning
    - Prevent duplicate alerts for same object
    """

    def __init__(self, max_age: int = 60, n_init: int = 1,
                 max_iou_distance: float = 0.85):
        """
        Args:
            max_age:           Frames to keep a lost track alive (60 @ 8fps = 7.5s)
            n_init:            Frames before a track is confirmed (1 = instant)
            max_iou_distance:  Max IOU distance for association (higher = more tolerant
                               to position shift between skipped frames)
        """
        self.tracker = DeepSort(
            max_age=max_age,
            n_init=n_init,
            max_iou_distance=max_iou_distance,
            # Use MobileNet embedder (included with deep-sort-realtime) for
            # appearance-based re-identification — critical for re-associating
            # tracks that were lost during DVR frame-skip bursts.
            embedder="mobilenet",
            half=True,           # fp16 embedder on GPU — faster, no quality loss
            bgr=True,            # OpenCV frames are BGR
        )
        self._class_cache: Dict[int, int] = {}   # track_id → class_id

    def update(self, yolo_results, frame: np.ndarray) -> List[Dict]:
        """
        Update tracker with new YOLO detections.

        Args:
            yolo_results: Raw YOLO result object (list of Results)
            frame:        Current BGR frame (needed for appearance embeddings)

        Returns:
            List of tracked objects:
            [
                {
                    "track_id":  int,
                    "class_id":  int,   (1=person, 3=pot_hauler)
                    "class_name": str,
                    "bbox":      (x1, y1, x2, y2),
                    "conf":      float,
                },
                ...
            ]
        """
        detections = []

        # ── Parse YOLO results into DeepSORT input format
        if yolo_results is not None:
            for result in yolo_results:
                if result.boxes is None:
                    continue
                for box in result.boxes.data:
                    try:
                        x1, y1, x2, y2, conf, cls = box.tolist()
                        class_id = int(cls)

                        if class_id not in TRACK_CLASSES:
                            continue

                        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                        w = x2 - x1
                        h = y2 - y1

                        # DeepSORT input: ([left, top, w, h], confidence, class_name)
                        detections.append((
                            [x1, y1, w, h],
                            float(conf),
                            TRACK_CLASSES[class_id],
                        ))

                        # Stash class_id by bbox key for later lookup
                        # (DeepSORT doesn't expose class_id in track outputs)
                        self._class_cache[f"{x1}_{y1}_{x2}_{y2}"] = class_id

                    except Exception as e:
                        print(f"[DeepSort] Detection parse error: {e}")

        # ── Update tracker
        try:
            tracks = self.tracker.update_tracks(detections, frame=frame)
        except Exception as e:
            print(f"[DeepSort] Tracker update error: {e}")
            return []

        # ── Build output
        # Include BOTH confirmed AND tentative tracks so objects are drawn
        # from their very first detection (n_init=1 makes all tentative → confirmed
        # immediately, but we keep the is_deleted() guard to skip dead tracks).
        tracked = []
        for track in tracks:
            if track.is_deleted():
                continue

            try:
                ltrb = track.to_ltrb()
                x1, y1, x2, y2 = int(ltrb[0]), int(ltrb[1]), int(ltrb[2]), int(ltrb[3])
                track_id = track.track_id

                # Resolve class from DeepSORT det_class attribute if available
                class_name = "person"  # default
                class_id   = 1
                if hasattr(track, 'det_class') and track.det_class is not None:
                    class_name = track.det_class
                    class_id = next(
                        (cid for cid, name in TRACK_CLASSES.items() if name == class_name),
                        1
                    )

                conf = track.det_conf if hasattr(track, 'det_conf') and track.det_conf else 0.0

                tracked.append({
                    "track_id":   track_id,
                    "class_id":   class_id,
                    "class_name": class_name,
                    "bbox":       (x1, y1, x2, y2),
                    "conf":       float(conf) if conf else 0.0,
                })

            except Exception as e:
                print(f"[DeepSort] Track output error: {e}")

        return tracked

    def get_person_tracks(self, tracked: List[Dict]) -> List[Dict]:
        """Filter to only person tracks."""
        return [t for t in tracked if t["class_id"] == 1]

    def get_hauler_tracks(self, tracked: List[Dict]) -> List[Dict]:
        """Filter to only pot_hauler tracks."""
        return [t for t in tracked if t["class_id"] == 3]


def draw_tracked_objects(frame: np.ndarray, tracked: List[Dict]) -> np.ndarray:
    """
    Draw tracked bounding boxes with ID labels onto frame.

    Colors:
        person     → Blue  (255, 100, 0)
        pot_hauler → Red   (0, 0, 255)
    """
    import cv2

    TRACK_COLORS = {
        1: (255, 100, 0),   # person: blue
        3: (0, 0, 255),     # pot_hauler: red
    }

    for obj in tracked:
        x1, y1, x2, y2 = obj["bbox"]
        class_id   = obj["class_id"]
        track_id   = obj["track_id"]
        class_name = obj["class_name"]
        color      = TRACK_COLORS.get(class_id, (200, 200, 200))

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        label = f"ID:{track_id} {class_name}"
        cv2.putText(frame, label, (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

    return frame
