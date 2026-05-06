"""
hazard_logic.py — Dynamic Hazard Evaluation Engine
====================================================
Evaluates safety state (HAZARD / SAFE) based on detected objects and zone config.

Active Class Mapping (4 classes — gate classes suppressed, see note below):
    0: gate_open        → SUPPRESSED — not present in current footage, causes
                          false detections. See FUTURE NOTE below.
    1: person           → Subject of safety evaluation
    2: pot_blocking     → Blocker ACTIVE (molten pot in blocking/parked position)
    3: pot_hauler       → Equipment HAZARD (always triggers RED if in zone)
    4: pot_not_blocking → Blocker INACTIVE (pot present but NOT protecting)

Safety Logic (per zone):
    1. pot_hauler in zone          → HAZARD (RED)   — highest priority
    2. person in zone:
       a. pot_blocking detected    → SAFE (GREEN)
       b. pot_not_blocking OR no blockers → HAZARD (RED)
    3. No person, no pot_hauler    → SAFE (GREEN)

── FUTURE NOTE — Gate-based safety system ────────────────────────────────────
    gate_open   = gate physically open  = NOT blocking = workers at risk (HAZARD)
    gate_closed = gate physically closed = IS blocking  = workers protected (SAFE)

    Full zone safety rule when gate data is available:
        gate_closed detected at BOTH north AND south ends → truly safe zone
        gate_open at either end → HAZARD regardless of other detections

    To activate:
        1. Label gate_open / gate_closed in new footage and retrain
        2. Add CLASS_GATE_CLOSED to BLOCKER_ACTIVE_CLASSES
        3. Add CLASS_GATE_OPEN to HAZARD_TRIGGER_CLASSES
        4. Add two-gate confirmation logic to evaluate_zone_hazard()
        5. Remove CLASS_GATE_OPEN from SUPPRESSED_CLASSES
──────────────────────────────────────────────────────────────────────────────
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional


# ──────────────────────────────────────────────────────────────────────────────
# Class ID constants (model trained with 5 classes; class 0 suppressed at
# inference — not present in current footage, causes false detections)
# ──────────────────────────────────────────────────────────────────────────────
CLASS_GATE_OPEN        = 0   # suppressed — see FUTURE NOTE in docstring
CLASS_PERSON           = 1
CLASS_POT_BLOCKING     = 2
CLASS_POT_HAULER       = 3
CLASS_POT_NOT_BLOCKING = 4

# Future class (not yet in model — add when gate footage available)
# CLASS_GATE_CLOSED    = 5

CLASS_NAMES = {
    CLASS_GATE_OPEN:        "gate_open",        # suppressed at inference
    CLASS_PERSON:           "person",
    CLASS_POT_BLOCKING:     "pot_blocking",
    CLASS_POT_HAULER:       "pot_hauler",
    CLASS_POT_NOT_BLOCKING: "pot_not_blocking",
}

# Classes suppressed at inference — model produces false positives for these
# on current footage because no gate instances exist in the 4 plant videos
SUPPRESSED_CLASSES = {CLASS_GATE_OPEN}

# Blocker classes that make a zone SAFE when a person is present
# NOTE: gate_open removed — see FUTURE NOTE. Only pot_blocking is active.
BLOCKER_ACTIVE_CLASSES   = {CLASS_POT_BLOCKING}

# Equipment classes that always trigger HAZARD regardless of blockers
HAZARD_TRIGGER_CLASSES   = {CLASS_POT_HAULER}


# ──────────────────────────────────────────────────────────────────────────────
# Data Structures
# ──────────────────────────────────────────────────────────────────────────────
class Detection:
    """Represents a single YOLO detection."""
    def __init__(self, class_id: int, conf: float, x1: int, y1: int, x2: int, y2: int):
        self.class_id = class_id
        self.conf     = conf
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        self.cx = (x1 + x2) // 2
        self.cy = (y1 + y2) // 2
        self.name = CLASS_NAMES.get(class_id, f"class_{class_id}")

    def center(self) -> Tuple[int, int]:
        return (self.cx, self.cy)

    def bbox(self) -> Tuple[int, int, int, int]:
        return (self.x1, self.y1, self.x2, self.y2)


class ZoneState:
    """Result of zone hazard evaluation.

    Two active states + one future state:

        HAZARD  (RED)   — pot_hauler detected anywhere in frame with no confirmed
                          blockers at both ends = entire bay is a hazard zone.
                          Also fires if pot_hauler is physically inside the zone,
                          or if a person is in the zone while bay is active.

        SAFE    (GREEN) — No pot_hauler detected (bay idle), OR both north AND
                          south blockers confirmed (section physically isolated).

        CAUTION (AMBER) — RESERVED FOR FUTURE use when gate detection is added.
                          Will fire when pot_hauler is active but ONE blocker end
                          is confirmed (partial protection, not fully safe).

    ── Current behaviour (no gate detection in footage) ─────────────────────
        pot_hauler anywhere in frame  →  entire bay RED  (no blockers = no safe section)
        no pot_hauler                 →  entire bay GREEN (bay idle)
    ──────────────────────────────────────────────────────────────────────────
    """
    HAZARD  = "HAZARD"
    CAUTION = "CAUTION"   # reserved — not triggered until gate detection is added
    SAFE    = "SAFE"

    def __init__(self, status: str, reason: str,
                 persons_in_zone: List[Detection],
                 equipment_in_zone: List[Detection],
                 blockers_active: bool,
                 blocker_detections: List[Detection]):
        self.status             = status
        self.reason             = reason
        self.persons_in_zone    = persons_in_zone
        self.equipment_in_zone  = equipment_in_zone
        self.blockers_active    = blockers_active
        self.blocker_detections = blocker_detections

    @property
    def is_hazard(self) -> bool:
        return self.status == self.HAZARD

    @property
    def is_caution(self) -> bool:
        return self.status == self.CAUTION

    @property
    def color_bgr(self) -> Tuple[int, int, int]:
        if self.status == self.HAZARD:
            return (0, 0, 255)      # Red
        if self.status == self.CAUTION:
            return (0, 165, 255)    # Amber
        return (0, 255, 0)          # Green

    @property
    def overlay_color_bgr(self) -> Tuple[int, int, int]:
        if self.status == self.HAZARD:
            return (0, 0, 200)
        if self.status == self.CAUTION:
            return (0, 130, 200)
        return (0, 200, 0)

    def log_dict(self, camera_id: int, zone_idx: int) -> Dict:
        return {
            "camera_id":        camera_id,
            "zone_idx":         zone_idx,
            "status":           self.status,
            "reason":           self.reason,
            "blocker_state":    "active" if self.blockers_active else "inactive",
            "persons_count":    len(self.persons_in_zone),
            "equipment_count":  len(self.equipment_in_zone),
        }


# ──────────────────────────────────────────────────────────────────────────────
# Core helpers
# ──────────────────────────────────────────────────────────────────────────────
def is_inside_zone(cx: int, cy: int, points: List) -> bool:
    """Check if point (cx, cy) is inside polygon defined by points."""
    if len(points) < 3:
        return False
    pts = np.array(points, dtype=np.int32).reshape((-1, 1, 2))
    return cv2.pointPolygonTest(pts, (float(cx), float(cy)), False) >= 0


def parse_yolo_detections(results) -> List[Detection]:
    """
    Parse raw YOLO results into a list of Detection objects.
    Handles both YOLOv8 and YOLO26 output formats.
    Suppresses classes in SUPPRESSED_CLASSES (e.g. gate_open) that cause
    false positives on current footage.
    """
    detections = []
    if results is None or len(results) == 0:
        return detections

    for result in results:
        if result.boxes is None:
            continue
        for box in result.boxes.data:
            try:
                x1, y1, x2, y2, conf, cls = box.tolist()
                class_id = int(cls)
                if class_id in SUPPRESSED_CLASSES:
                    continue   # filter out — false positives on current footage
                detections.append(Detection(
                    class_id=class_id,
                    conf=float(conf),
                    x1=int(x1), y1=int(y1),
                    x2=int(x2), y2=int(y2),
                ))
            except Exception as e:
                print(f"[HazardLogic] Box parse error: {e}")
    return detections


def evaluate_zone_hazard(
    zone_points: List,
    all_detections: List[Detection],
    frame_width: int = 640,
    frame_height: int = 480,
    external_equipment_active: bool = False,
    external_source_camera: int = None,
    zone_blockers_confirmed: bool = False,
    vehicle_memory_active: bool = False,
) -> ZoneState:
    """
    Core hazard evaluation for a single zone — three-state traffic light logic.

    Core safety logic — blocker-based zone isolation:

        A "blocker" (gate_closed or pot_blocking) at BOTH the north AND south
        ends of the bay defines a protected corridor between them. The zone
        polygon drawn in the UI represents that corridor.

        Priority (highest → lowest):
        1. pot_hauler inside the zone polygon
               → HAZARD — equipment has breached the protected corridor
        2. pot_hauler anywhere in frame + both ends NOT blocked
               → HAZARD — entire bay is live, no safe section exists
        3. pot_hauler anywhere in frame + both ends blocked
               → SAFE   — pot_hauler is OUTSIDE the protected corridor
                           (blockers are doing their job)
        4. No pot_hauler in frame
               → SAFE   — bay is idle

        Person in zone is always HAZARD regardless of blocker state
        (a person should never be in the zone during active operations).

    CAUTION (AMBER) reserved for future:
        pot_hauler active + only ONE end blocked → partial protection → AMBER

    Args:
        zone_points:              List of [x, y] polygon vertices (the protected corridor)
        all_detections:           All YOLO detections in current frame (full frame scope)
        external_equipment_active: True if another camera in the same bay has seen pot_hauler
                                   recently — triggers bay-wide RED even if not visible in
                                   this camera's frame.
        external_source_camera:   Camera ID that detected the equipment (for reason string).

    Returns:
        ZoneState with full evaluation result
    """
    if not zone_points or len(zone_points) < 3:
        return ZoneState(
            ZoneState.SAFE, "Zone has no valid polygon",
            [], [], False, []
        )

    # ── Classify detections
    persons_in_zone:    List[Detection] = []
    equipment_in_zone:  List[Detection] = []   # pot_hauler INSIDE zone polygon
    equipment_in_frame: List[Detection] = []   # pot_hauler anywhere in frame
    blocker_detections: List[Detection] = []

    for det in all_detections:
        in_zone = is_inside_zone(det.cx, det.cy, zone_points)

        if det.class_id == CLASS_PERSON:
            if in_zone:
                persons_in_zone.append(det)

        elif det.class_id in HAZARD_TRIGGER_CLASSES:
            equipment_in_frame.append(det)
            if in_zone:
                equipment_in_zone.append(det)

        elif det.class_id in BLOCKER_ACTIVE_CLASSES:
            blocker_detections.append(det)

    # equipment_active is True if THIS camera sees pot_hauler OR any other camera
    # in the bay does (cross-camera propagation — the bay is one physical space).
    equipment_active  = len(equipment_in_frame) > 0 or external_equipment_active

    # ── Blocker state: operator confirmed both blockers bounding THIS zone
    both_ends_blocked = zone_blockers_confirmed

    # ── Rule 1: Person in zone
    #   Blockers confirmed + no equipment + no vehicle memory → SAFE
    #   Blockers confirmed + no equipment + vehicle memory    → HAZARD (blind spot risk)
    #   Blockers confirmed + equipment active                 → HAZARD (equipment override)
    #   No blockers → HAZARD regardless
    if persons_in_zone:
        if both_ends_blocked and not equipment_active and not vehicle_memory_active:
            return ZoneState(
                ZoneState.SAFE,
                f"{len(persons_in_zone)} person(s) in corridor - blockers confirmed, zone isolated",
                persons_in_zone, [],
                True, blocker_detections
            )
        if both_ends_blocked and not equipment_active and vehicle_memory_active:
            return ZoneState(
                ZoneState.HAZARD,
                f"Vehicle in blind spot - {len(persons_in_zone)} person(s) at risk",
                persons_in_zone, [],
                False, []
            )
        person_note = f"{len(persons_in_zone)} person(s) in zone"
        ops_note    = " - equipment active" if equipment_active else " - blockers not set"
        return ZoneState(
            ZoneState.HAZARD,
            f"{person_note}{ops_note}",
            persons_in_zone, equipment_in_frame,
            len(blocker_detections) > 0, blocker_detections
        )

    # ── Rule 2: pot_hauler physically inside zone polygon — blocker breach
    if equipment_in_zone:
        eq_names = ", ".join(set(d.name for d in equipment_in_zone))
        return ZoneState(
            ZoneState.HAZARD,
            f"{eq_names} inside zone - blocker breach",
            [], equipment_in_zone,
            len(blocker_detections) > 0, blocker_detections
        )

    # ── Rule 3: pot_hauler active in bay + this zone NOT isolated → RED
    if equipment_active and not both_ends_blocked:
        if equipment_in_frame:
            eq_names = ", ".join(set(d.name for d in equipment_in_frame))
            reason = f"{eq_names} active - zone not isolated"
        else:
            cam_note = f"Cam {external_source_camera}" if external_source_camera else "another camera"
            reason = f"pot_hauler on {cam_note} - zone not isolated"
        return ZoneState(
            ZoneState.HAZARD,
            reason,
            [], equipment_in_frame,
            False, []
        )

    # ── Rule 4: pot_hauler active + this zone IS isolated
    #   If equipment is visible on THIS camera (outside zone polygon) → cameras confirm
    #   it is not inside the zone → SAFE.
    #   If equipment is NOT visible on this camera but is active in the bay (seen on
    #   another camera or recently) → the vehicle may have entered this zone's blind
    #   spot before blockers were placed → HAZARD.
    if equipment_active and both_ends_blocked:
        if len(equipment_in_frame) > 0:
            # Vehicle visible on this camera and NOT inside zone (Rule 2 caught that)
            return ZoneState(
                ZoneState.SAFE,
                "Equipment active - zone boundary confirmed by camera",
                [], equipment_in_frame,
                True, blocker_detections
            )
        else:
            # Vehicle somewhere in bay but not visible on this camera
            # → could be in this zone's blind spot
            return ZoneState(
                ZoneState.HAZARD,
                "Equipment in bay - verify no vehicle in blind spot",
                [], [],
                False, []
            )

    # ── Rule 4b: Vehicle memory — entered zone, not confirmed to have exited
    #   Bay now appears clear (equipment_active timed out) BUT the zone is isolated
    #   and this camera previously saw a vehicle that never confirmed to have left.
    #   The vehicle may be parked in the camera's blind spot between the blockers.
    #   Only fires when blockers are confirmed — if zone is open, vehicle could
    #   have freely exited and memory is irrelevant.
    if vehicle_memory_active and both_ends_blocked and not equipment_active:
        return ZoneState(
            ZoneState.HAZARD,
            "Vehicle entered zone - not confirmed to have exited",
            [], [], False, []
        )

    # ── Rule 5: Bay idle
    #   Blockers confirmed → full GREEN (zone secured even if equipment enters)
    #   No blockers → CAUTION (clear right now but physically unguarded)
    if both_ends_blocked:
        return ZoneState(
            ZoneState.SAFE, "Bay idle - zone secured by confirmed blockers",
            [], [], True, []
        )
    return ZoneState(
        ZoneState.CAUTION, "Bay idle - no blockers set",
        [], [], False, []
    )


# ──────────────────────────────────────────────────────────────────────────────
# Drawing Utilities
# ──────────────────────────────────────────────────────────────────────────────
def draw_detections(frame: np.ndarray, detections: List[Detection]) -> np.ndarray:
    """Draw all YOLO detections with class-specific colors.
    Suppressed classes are not drawn."""
    CLASS_COLORS = {
        CLASS_PERSON:           (255, 100, 0),   # Blue-ish
        CLASS_POT_BLOCKING:     (0, 220, 120),   # Green
        CLASS_POT_HAULER:       (0, 0, 255),     # Red
        CLASS_POT_NOT_BLOCKING: (0, 165, 255),   # Orange
    }

    for det in detections:
        if det.class_id in SUPPRESSED_CLASSES:
            continue
        color = CLASS_COLORS.get(det.class_id, (200, 200, 200))
        cv2.rectangle(frame, (det.x1, det.y1), (det.x2, det.y2), color, 2)
        label = f"{det.name} {det.conf:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
        cv2.rectangle(frame, (det.x1, det.y1 - th - 6), (det.x1 + tw + 4, det.y1), color, -1)
        cv2.putText(frame, label, (det.x1 + 2, det.y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)   # white, bold
    return frame


def draw_zone(frame: np.ndarray, zone_points: List, zone_state: ZoneState,
              zone_label: str = "Zone", alpha: float = 0.30) -> np.ndarray:
    """Draw zone polygon with hazard/safe coloring and overlay."""
    if not zone_points or len(zone_points) < 3:
        return frame

    pts = np.array(zone_points, dtype=np.int32).reshape((-1, 1, 2))
    color = zone_state.color_bgr
    overlay_color = zone_state.overlay_color_bgr

    # Fill overlay
    overlay = frame.copy()
    cv2.fillPoly(overlay, [pts], overlay_color)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

    # Border
    cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=2)

    # Label with status
    label_pt = tuple(pts[0][0])
    status_text = f"{zone_label}: {zone_state.status}"
    cv2.putText(frame, status_text,
                (label_pt[0], label_pt[1] - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
    return frame


def draw_alert_banner(frame: np.ndarray, zone_states: List[ZoneState],
                      camera_id: int) -> np.ndarray:
    """Draw a top alert banner. Auto-scales font to fit text within frame width."""
    any_hazard = any(z.is_hazard for z in zone_states)

    if any_hazard:
        hazard_zone  = next(z for z in zone_states if z.is_hazard)
        banner_color = (0, 0, 200)      # Red
        text = f"CAM {camera_id}  HAZARD: {hazard_zone.reason}"
    else:
        banner_color = (0, 140, 0)      # Green
        text = f"CAM {camera_id}  OK - BAY IDLE - ALL ZONES SAFE"

    # Auto-fit font scale so text always fits within the frame width
    max_width = frame.shape[1] - 16   # 8px padding each side
    font      = cv2.FONT_HERSHEY_SIMPLEX
    scale     = 0.65
    thickness = 2
    for scale in [0.65, 0.58, 0.52, 0.46, 0.40]:
        (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
        if tw <= max_width:
            break

    banner_h = th + 16
    cv2.rectangle(frame, (0, 0), (frame.shape[1], banner_h), banner_color, -1)
    cv2.putText(frame, text, (8, th + 6), font, scale, (255, 255, 255), thickness)
    return frame
