"""
stream_generator.py — Multi-Camera MJPEG Stream with Dynamic Hazard Logic
==========================================================================
Integrates:
  - YOLO26m detection (5 classes)
  - Dynamic hazard evaluation via hazard_logic.py
  - DeepSORT tracking (person + pot_hauler)
  - Zone overlay with real-time RED/GREEN state
  - Event logging with blocker state
  - Wall-clock FPS pacing: plays at native video FPS regardless of YOLO speed
  - DVR-style frame skipping: drops frames to stay on-time, never slows down
  - Multi-camera sync: all streams share a sync_start_time clock anchor

Thread Safety:
  All 4 camera streams run in separate threads and share the same GPU model.
  _MODEL_LOCK serializes inference so CUDA doesn't get torn between threads.
"""

import cv2
import time
import threading
import numpy as np

from adaptive_deblur import enhance_adaptive
from polygon_utils import load_polygon
from event_logger import log_event
from deepsort_tracker import DeepSortTracker, draw_tracked_objects
from hazard_logic import (
    parse_yolo_detections,
    evaluate_zone_hazard,
    draw_detections,
    draw_zone,
    draw_alert_banner,
    ZoneState,
    CLASS_PERSON,
    CLASS_POT_HAULER,
    HAZARD_TRIGGER_CLASSES,
    is_inside_zone,
)

# ── Global lock: serializes GPU model inference across all concurrent streams
# All 4 camera streams share one CUDA device; this prevents race conditions.
_MODEL_LOCK = threading.Lock()

# ── Cross-camera bay hazard propagation
# The physical plant bay is ONE space. If any camera detects pot_hauler, ALL
# cameras in the same bay must show RED — even if the hauler is out of that
# camera's field of view at that moment.
#
# Design:
#   - Any stream that detects pot_hauler sets _BAY_HAZARD["equipment_active"] = True
#     and records its camera ID + timestamp.
#   - All streams read this shared state when evaluating zones.
#   - After EQUIPMENT_CLEAR_TIMEOUT seconds with no detection on any camera, resets to SAFE.
_BAY_HAZARD_LOCK = threading.Lock()
_BAY_HAZARD = {
    "equipment_active": False,
    "last_seen_time": 0.0,
    "last_seen_camera": None,
}
EQUIPMENT_CLEAR_TIMEOUT = 3.0   # seconds — how long RED persists after last detection

# ── Manual blocker confirmation (operator toggles) ────────────────────────────
# Four physical blockers define three bay zones:
#   Zone A (North) : bounded by far_north  + inner_north   → Camera 1
#   Zone B (Middle): bounded by inner_north + inner_south  → Camera 2 & 3
#   Zone C (South) : bounded by inner_south + far_south    → Camera 4
#
# A zone is isolated only when BOTH its bounding blockers are confirmed.
_BLOCKERS_LOCK = threading.Lock()
_BLOCKERS = {
    "far_north":   False,
    "inner_north": False,
    "inner_south": False,
    "far_south":   False,
}

# Which two blockers must be confirmed to isolate each camera's zone
CAMERA_ZONE_BLOCKERS = {
    1: ("far_north",   "inner_north"),   # Zone A
    2: ("inner_north", "inner_south"),   # Zone B
    3: ("inner_north", "inner_south"),   # Zone B (same physical zone, different angle)
    4: ("inner_south", "far_south"),     # Zone C
}

ZONE_NAMES = {
    ("far_north",   "inner_north"):  "Zone A (North)",
    ("inner_north", "inner_south"):  "Zone B (Middle)",
    ("inner_south", "far_south"):    "Zone C (South)",
}

# ── Per-camera vehicle entry memory ──────────────────────────────────────────
# Tracks whether a vehicle (pot_hauler) has been seen on each camera and has
# NOT been manually confirmed as cleared.  Persists beyond the short
# _BAY_HAZARD timeout so the system can warn about blind-spot occupancy even
# after the vehicle disappears from all camera views.
#
# Only relevant when the zone's two blockers are both confirmed — if the zone
# is open the vehicle may have simply driven out.
_ZONE_MEMORY_LOCK = threading.Lock()
_ZONE_VEHICLE_MEMORY: dict = {
    1: {"vehicle_entered": False, "entered_at": None},
    2: {"vehicle_entered": False, "entered_at": None},
    3: {"vehicle_entered": False, "entered_at": None},
    4: {"vehicle_entered": False, "entered_at": None},
}

def clear_zone_memory(camera_ids: list):
    """Operator-confirmed zone clear: reset vehicle memory for given cameras."""
    with _ZONE_MEMORY_LOCK:
        for cam in camera_ids:
            if cam in _ZONE_VEHICLE_MEMORY:
                _ZONE_VEHICLE_MEMORY[cam]["vehicle_entered"] = False
                _ZONE_VEHICLE_MEMORY[cam]["entered_at"]     = None

# ── Per-camera live zone state (for frontend side panel polling) ──────────────
_LIVE_STATES_LOCK = threading.Lock()
_LIVE_STATES: dict = {}   # camera_id → {"is_hazard": bool, "status": str, "reason": str, "ts": float}


def gen_stream(
    index: int,
    video_path,
    polygon_path: str,
    model,
    confidence: float,
    quality: str,
    sharpness: float,
    gamma: float,
    deepsort: bool = True,
    sync_start_time: float = None,
):
    """
    Generator yielding MJPEG frames for a single camera stream.

    FPS Pacing (CCTV/DVR style):
      - Each frame is yielded at the exact wall-clock time it should appear
        based on the video's native FPS.
      - If YOLO inference is slow, frames are SKIPPED (not slowed down) to
        maintain wall-clock accuracy — identical to how a DVR behaves.
      - If YOLO is fast, we sleep the remainder of the frame period.

    Synchronization:
      - All cameras share sync_start_time as their common clock anchor.
      - Since all videos are the same length/FPS, sharing the same start time
        keeps all 4 cameras at the same position throughout playback.

    Playback: one-time (no loop). Stream ends when video ends.
    """
    # ── Open video source
    if video_path == "webcam" or video_path == 0:
        cap = cv2.VideoCapture(0)
    else:
        cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"[Stream {index}] ERROR: Unable to open source: {video_path}")
        return

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    native_fps = cap.get(cv2.CAP_PROP_FPS)

    # Hardcode target CCTV playback rate to 8.0 FPS to match Camera 1
    # This massively reduces GPU load and syncs all streams perfectly
    TARGET_FPS = 8.0
    frame_period = 1.0 / TARGET_FPS  # seconds per frame at target speed

    # ── Wall-clock anchor: shared across all streams for synchronization
    # All cameras use the same start time so they stay at the same video position.
    stream_start = sync_start_time if sync_start_time else time.time()

    # virtual_frame: absolute frame counter aligned to wall clock
    # This is how we know which frame "should" be showing right now.
    virtual_frame = 0

    # ── Initialize tracker
    tracker = DeepSortTracker(max_age=60, n_init=1) if deepsort else None

    # ── FPS tracking for overlay (shows actual output rate)
    frame_count = 0
    measured_fps = 0.0
    fps_calc_start = time.time()

    # ── Alert de-duplication
    alerted_ids: set = set()

    # ── Hazard state tracking (suppress repeated prints — only log on transition)
    _prev_hazard: bool = False

    # ── Last successfully encoded frame (used as fallback if encoding fails)
    last_buffer = None

    print(
        f"[Stream {index}] Started — source: {video_path} | "
        f"native_fps: {native_fps:.1f} | frame_period: {frame_period*1000:.1f}ms | "
        f"deepsort: {deepsort}"
    )

    while cap.isOpened():
        # ────────────────────────────────────────────────────────────────────
        # STEP 1: Wall-clock sync — figure out which frame we should be on
        # ────────────────────────────────────────────────────────────────────
        now = time.time()
        elapsed = now - stream_start

        # Which frame should currently be displayed based on the wall clock?
        target_frame = int(elapsed * TARGET_FPS)

        # DVR-style catch-up: if YOLO was slow and we fell behind the clock,
        # skip forward by reading (and discarding) the missed frames.
        # This keeps us on-time without slowing video down.
        if target_frame > virtual_frame:
            frames_to_skip = target_frame - virtual_frame
            skipped = 0
            for _ in range(frames_to_skip):
                ret_skip, skipped_frame = cap.read()
                if not ret_skip:
                    break
                skipped += 1
                # ── Feed tracker with empty detections during skipped frames
                # Without this, DeepSORT ages all tracks by 1 for every skipped
                # frame but never gets a Kalman prediction update, causing tracks
                # to drift and die during slow-inference bursts.
                if tracker is not None and skipped_frame is not None:
                    tracker.update(None, cv2.resize(skipped_frame, (640, 480)))
            virtual_frame += skipped
            if skipped > 10:   # only log significant catch-up bursts
                print(f"[Stream {index}] Skipped {skipped} frame(s) to stay on clock")

        # ────────────────────────────────────────────────────────────────────
        # STEP 2: Read the current frame
        # ────────────────────────────────────────────────────────────────────
        ret, frame = cap.read()
        virtual_frame += 1

        if not ret:
            # End of video — one-time playback, stop stream
            print(f"[Stream {index}] Video ended at frame {virtual_frame}/{total_frames}")
            # Send a "stream ended" placeholder frame
            blank = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(
                blank,
                f"Camera {index}: Playback Complete",
                (80, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 200, 255), 2,
            )
            ret_enc, buf = cv2.imencode(".jpg", blank)
            if ret_enc:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")
            break

        # ────────────────────────────────────────────────────────────────────
        # STEP 3: Pre-process frame
        # ────────────────────────────────────────────────────────────────────
        frame = cv2.resize(frame, (640, 480))
        enhanced = frame.copy()

        if quality == "high":
            enhanced = enhance_adaptive(enhanced, sharpness=sharpness, gamma=gamma)

        # ────────────────────────────────────────────────────────────────────
        # STEP 4: YOLO inference (thread-safe GPU call)
        # Two-tier confidence:
        #   - tracker_conf (0.35): lower gate for DeepSORT — catches partial/occluded
        #     detections that should still feed the Kalman filter.
        #   - confidence: the user-set threshold for hazard logic decisions.
        # ────────────────────────────────────────────────────────────────────
        TRACKER_CONF = max(0.35, confidence - 0.15)   # always ≥ 0.35
        with _MODEL_LOCK:
            # Run inference once at the lower tracker confidence
            results = model(enhanced, conf=TRACKER_CONF, iou=0.45, verbose=False)

        # ────────────────────────────────────────────────────────────────────
        # STEP 5: Hazard Logic + Zone Overlay
        # ────────────────────────────────────────────────────────────────────
        detections = parse_yolo_detections(results)
        zones = load_polygon(polygon_path)
        zone_states: list[ZoneState] = []
        alert_triggered = False

        # ── Cross-camera bay hazard propagation ──
        # Check if THIS camera sees equipment; update shared bay state.
        now_ts = time.time()
        this_cam_equipment = any(d.class_id in HAZARD_TRIGGER_CLASSES for d in detections)

        with _BAY_HAZARD_LOCK:
            if this_cam_equipment:
                _BAY_HAZARD["equipment_active"] = True
                _BAY_HAZARD["last_seen_time"]   = now_ts
                _BAY_HAZARD["last_seen_camera"] = index
            elif now_ts - _BAY_HAZARD["last_seen_time"] > EQUIPMENT_CLEAR_TIMEOUT:
                # No camera has seen equipment for N seconds — reset to safe
                _BAY_HAZARD["equipment_active"] = False

            external_equipment_active = _BAY_HAZARD["equipment_active"] and not this_cam_equipment
            source_camera = _BAY_HAZARD["last_seen_camera"] if external_equipment_active else None
        # ─────────────────────────────────────────

        # ── Update vehicle entry memory for this camera ───────────────────────
        # Set memory the moment a vehicle is detected on this camera's frame.
        # Never auto-clear — only an operator "Confirm Zone Clear" resets it.
        if this_cam_equipment:
            with _ZONE_MEMORY_LOCK:
                if not _ZONE_VEHICLE_MEMORY[index]["vehicle_entered"]:
                    _ZONE_VEHICLE_MEMORY[index]["vehicle_entered"] = True
                    _ZONE_VEHICLE_MEMORY[index]["entered_at"]      = now_ts

        with _ZONE_MEMORY_LOCK:
            vehicle_memory_active = _ZONE_VEHICLE_MEMORY[index]["vehicle_entered"]
        # ─────────────────────────────────────────

        for zone_idx, zone in enumerate(zones):
            zone_points = zone.get("points", [])
            if len(zone_points) < 3:
                continue
            with _BLOCKERS_LOCK:
                b1, b2 = CAMERA_ZONE_BLOCKERS.get(index, ("far_north", "far_south"))
                zone_isolated = _BLOCKERS[b1] and _BLOCKERS[b2]
            state = evaluate_zone_hazard(
                zone_points=zone_points,
                all_detections=detections,
                external_equipment_active=external_equipment_active,
                external_source_camera=source_camera,
                zone_blockers_confirmed=zone_isolated,
                vehicle_memory_active=vehicle_memory_active,
            )
            zone_states.append(state)
            enhanced = draw_zone(enhanced, zone_points, state, zone.get("label", f"Zone {zone_idx + 1}"))
            if state.is_hazard and not alert_triggered:
                log_event(index, "hazard", confidence, enhanced, state.reason)
                alert_triggered = True
                if not _prev_hazard:           # only print on transition → HAZARD
                    print(f"[Stream {index}] HAZARD: {state.reason}")

        # ────────────────────────────────────────────────────────────────────
        # STEP 6: Visuals & Tracking
        # ────────────────────────────────────────────────────────────────────
        enhanced = draw_detections(enhanced, detections)
        if tracker is not None:
            tracked = tracker.update(results, enhanced)
            enhanced = draw_tracked_objects(enhanced, tracked)
            for obj in tracked:
                track_id, bx1, by1, bx2, by2 = obj["track_id"], *obj["bbox"]
                bcx, bcy = (bx1 + bx2) // 2, (by1 + by2) // 2
                for z_idx, z in enumerate(zones):
                    z_pts = z.get("points", [])
                    if len(z_pts) >= 3 and is_inside_zone(bcx, bcy, z_pts):
                        state = zone_states[z_idx] if z_idx < len(zone_states) else None
                        if state and state.is_hazard:
                            if (track_id, z_idx) not in alerted_ids:
                                alerted_ids.add((track_id, z_idx))
                                print(f"[Stream {index}] Track {track_id} → HAZARD zone {z_idx}")
                        elif state:
                            alerted_ids.discard((track_id, z_idx))

        if zone_states:
            enhanced = draw_alert_banner(enhanced, zone_states, index)

        # ── Update hazard transition tracker ─────────────────────────────────
        _prev_hazard = alert_triggered

        # ── Publish live state for frontend side panel ────────────────────────
        if zone_states:
            # Priority: HAZARD > CAUTION > SAFE
            top = (next((z for z in zone_states if z.is_hazard), None)
                   or next((z for z in zone_states if z.is_caution), None)
                   or zone_states[0])
            with _BLOCKERS_LOCK:
                b1, b2 = CAMERA_ZONE_BLOCKERS.get(index, ("far_north", "far_south"))
                isolated = _BLOCKERS[b1] and _BLOCKERS[b2]
            with _LIVE_STATES_LOCK:
                _LIVE_STATES[index] = {
                    "is_hazard":      top.is_hazard,
                    "is_caution":     top.is_caution,
                    "status":         top.status,
                    "reason":         top.reason,
                    "zone_name":      ZONE_NAMES.get((b1, b2), "Zone"),
                    "isolated":       isolated,
                    "memory_active":  vehicle_memory_active,
                    "ts":             time.time(),
                }

        # ────────────────────────────────────────────────────────────────────
        # STEP 7: FPS overlay (shows real output fps + sync position)
        # ────────────────────────────────────────────────────────────────────
        frame_count += 1
        el_fps = time.time() - fps_calc_start
        if el_fps >= 1.0:
            measured_fps = frame_count / el_fps
            frame_count = 0
            fps_calc_start = time.time()

        cv2.putText(
            enhanced,
            f"Cam {index} | FPS: {measured_fps:.1f} | Frame: {virtual_frame}/{total_frames}",
            (8, 470), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2,
        )

        # ────────────────────────────────────────────────────────────────────
        # STEP 8: MJPEG Encoding & Yield
        # ────────────────────────────────────────────────────────────────────
        ret_enc, buffer = cv2.imencode(
            ".jpg", enhanced,
            [cv2.IMWRITE_JPEG_QUALITY, 85 if quality == "high" else 70]
        )
        if not ret_enc:
            if last_buffer is not None:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + last_buffer + b"\r\n")
            continue

        last_buffer = buffer.tobytes()
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + last_buffer + b"\r\n")

        # ────────────────────────────────────────────────────────────────────
        # STEP 9: Wall-clock sleep — pace output to native FPS
        # Sleep only the remaining time until the next frame is due.
        # If YOLO was slow and we're already behind, sleep_time will be ≤0
        # and we skip the sleep entirely (DVR catch-up mode).
        # ────────────────────────────────────────────────────────────────────
        next_frame_due = stream_start + (virtual_frame / TARGET_FPS)
        sleep_time = next_frame_due - time.time()
        if sleep_time > 0:
            time.sleep(sleep_time)

    cap.release()
    print(f"[Stream {index}] Stream ended.")
