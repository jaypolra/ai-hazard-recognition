from fastapi import FastAPI, UploadFile, Request
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from ultralytics import YOLO
import os
import threading
import time

from polygon_utils import save_polygon, load_polygon
from video_utils import save_uploaded_video, capture_first_frame
from stream_generator import gen_stream
from logs_api import router as logs_router
from zone_sync_manager import get_zone_sync_manager
from hazard_reason import analyze_hazard_event

app = FastAPI()
app.mount("/snapshots", StaticFiles(directory="snapshots"), name="snapshots")
app.include_router(logs_router)

@app.get("/")
def health_check():
    return {"status": "ok"}

@app.post("/set_blocker")
async def set_blocker(request: Request):
    """Toggle one physical blocker on/off.
    Body: { "blocker": "far_north" | "inner_north" | "inner_south" | "far_south", "confirmed": true/false }
    """
    from stream_generator import _BLOCKERS, _BLOCKERS_LOCK, CAMERA_ZONE_BLOCKERS, ZONE_NAMES
    body    = await request.json()
    name    = body.get("blocker")
    confirmed = bool(body.get("confirmed", False))
    with _BLOCKERS_LOCK:
        if name not in _BLOCKERS:
            return JSONResponse({"error": f"Unknown blocker: {name}"}, status_code=400)
        _BLOCKERS[name] = confirmed
        snapshot = dict(_BLOCKERS)
    return {"blocker": name, "confirmed": confirmed, "all": snapshot}

@app.post("/confirm_zone_clear/{zone_key}")
def confirm_zone_clear(zone_key: str):
    """Operator confirms a zone is physically clear — resets vehicle entry memory.
    zone_key: 'A', 'B', or 'C'
    """
    from stream_generator import clear_zone_memory
    ZONE_TO_CAMERAS = {"A": [1], "B": [2, 3], "C": [4]}
    cameras = ZONE_TO_CAMERAS.get(zone_key.upper(), [])
    if not cameras:
        return JSONResponse({"error": f"Unknown zone: {zone_key}"}, status_code=400)
    clear_zone_memory(cameras)
    return {"zone": zone_key.upper(), "cleared": True, "cameras": cameras}

@app.get("/blockers_status")
def blockers_status():
    """Return all blocker states + derived zone isolation summary."""
    from stream_generator import _BLOCKERS, _BLOCKERS_LOCK, ZONE_NAMES
    ZONE_PAIRS = [
        ("far_north",   "inner_north",  "A", "North Zone"),
        ("inner_north", "inner_south",  "B", "Middle Zone"),
        ("inner_south", "far_south",    "C", "South Zone"),
    ]
    with _BLOCKERS_LOCK:
        blockers = dict(_BLOCKERS)
    zones = {}
    for b1, b2, key, label in ZONE_PAIRS:
        zones[key] = {
            "label":    label,
            "isolated": blockers[b1] and blockers[b2],
            "blockers": [b1, b2],
            "b1_set":   blockers[b1],
            "b2_set":   blockers[b2],
        }
    return {"blockers": blockers, "zones": zones}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────────────────────────────────────
# Load YOLO26m model (trained on 5-class industrial safety dataset)
# Classes: gate_open(0), person(1), pot_blocking(2), pot_hauler(3), pot_not_blocking(4)
# ──────────────────────────────────────────────────────────────────────────────
import torch

_WEIGHTS_PRIORITY = [
    "weights/person_industry_best.pt",   # trained YOLO26m (after training)
    "weights/model_no_aug.pt",           # trained model (no augmentation)
    "weights/yolo26m_industry_hazard.pt",
    "../yolo26n.pt",                      # project root nano (fallback)
    "../yolov8m.pt",                      # project root yolov8m (fallback)
]

_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[Main] Using device: {_DEVICE}")

import os as _os
for _wpath in _WEIGHTS_PRIORITY:
    if _os.path.exists(_wpath):
        print(f"[Main] Loading model: {_wpath}")
        model = YOLO(_wpath).to(_DEVICE)
        print(f"[Main] Model loaded — classes: {model.names}")
        break
else:
    print("[Main] WARNING: no local weights found, loading yolo26m (auto-download)")
    model = YOLO("yolo26m.pt").to(_DEVICE)

# State dictionaries
video_paths = {1: "video_1.mp4", 2: "video_2.mp4", 3: "video_3.mp4", 4: "video_4.mp4"}
polygon_paths = {1: "polygon_1.npy", 2: "polygon_2.npy", 3: "polygon_3.npy", 4: "polygon_4.npy"}
screenshot_paths = {1: "screenshot_1.jpg", 2: "screenshot_2.jpg", 3: "screenshot_3.jpg", 4: "screenshot_4.jpg"}
confidences = {1: 0.5, 2: 0.5, 3: 0.5, 4: 0.5}
lock = threading.Lock()
sync_lock = threading.Lock()
sync_sessions = {} # {sync_time_str: start_timestamp}

@app.post("/upload_video_{index}")
async def upload_video(index: int, file: UploadFile):
    save_uploaded_video(file, video_paths[index])
    capture_first_frame(video_paths[index], screenshot_paths[index])
    return {"status": "uploaded", "stream": index}

@app.post("/capture_screenshot_{index}")
async def capture_screenshot(index: int):
    capture_first_frame(video_paths[index], screenshot_paths[index])
    return {"status": "screenshot captured"}

@app.get("/get_screenshot_{index}")
def get_screenshot(index: int):
    path = screenshot_paths.get(index)
    if path and os.path.exists(path):
        return FileResponse(path, media_type="image/jpeg")
    return {"status": "screenshot not found"}

@app.post("/set_polygon_{index}")
async def set_polygon(index: int, request: Request):
    data = await request.json()
    polygons = data.get("polygons", [])
    with lock:
        save_polygon(polygon_paths[index], polygons)
    return {"status": "polygon updated", "stream": index}

@app.post("/set_confidence_{index}")
async def set_confidence(index: int, request: Request):
    data = await request.json()
    val = data.get("confidence", 0.5)
    confidences[index] = float(val)
    return {"status": "confidence updated", "value": confidences[index]}

@app.get("/stream_{index}")
def stream(index: int, request: Request):
    quality = request.query_params.get("quality", "low")
    sharpness = float(request.query_params.get("sharpness", 1.0))
    gamma = float(request.query_params.get("gamma", 1.0))
    deepsort = request.query_params.get("deepsort", "true").lower() != "false"   # default ON
    sync_time = request.query_params.get("sync_time", "default")
    
    # Establish a stable backend-side start time for this sync session
    with sync_lock:
        if sync_time not in sync_sessions:
            sync_sessions[sync_time] = time.time()
        backend_start_time = sync_sessions[sync_time]

    return StreamingResponse(
        gen_stream(
            index=index,
            video_path=video_paths[index],
            polygon_path=polygon_paths[index],
            model=model,
            confidence=confidences[index],
            quality=quality,
            sharpness=sharpness,
            gamma=gamma,
            deepsort=deepsort,
            sync_start_time=backend_start_time,
        ),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

# ✅ NEW: Switch between webcam and video dynamically
@app.post("/switch_stream_{index}")
async def switch_stream(index: int, request: Request):
    data = await request.json()
    new_source = data.get("video_path", "webcam")
    confidence = float(data.get("confidence", confidences.get(index, 0.5)))

    with lock:
        video_paths[index] = new_source
        confidences[index] = confidence
        capture_first_frame(new_source, screenshot_paths[index])

    return JSONResponse(content={"status": "stream switched", "stream": index, "source": new_source})

@app.get("/video_feed_{index}")
def video_feed(index: int,
               quality: str = "low",
               sharpness: float = 1.0,
               gamma: float = 1.0,
               deepsort: bool = True):
    webcam_path = 0  # Default webcam index
    polygon_path = polygon_paths[index]
    
    return StreamingResponse(
        gen_stream(
            index=index,
            video_path=webcam_path,
            polygon_path=polygon_path,
            model=model,
            confidence=confidences.get(index, 0.5),
            quality=quality,
            sharpness=sharpness,
            gamma=gamma,
            deepsort=deepsort
        ),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.get("/get_zones_{index}")
def get_zones(index: int):
    """Retrieve saved zones for a specific camera"""
    polygon_path = polygon_paths.get(index)
    if not polygon_path or not os.path.exists(polygon_path):
        return {"zones": [], "exists": False}
    
    try:
        polygons = load_polygon(polygon_path)
        # Convert numpy arrays to lists for JSON serialization
        zones = []
        if polygons:
            for poly in polygons:
                zones.append({
                    "id": len(zones),
                    "type": poly.get("type", "Red Zone"),
                    "color": poly.get("color", "red"),
                    "points": poly.get("points", []),
                    "confidence": poly.get("confidence", 0.5)
                })
        return {"zones": zones, "exists": True}
    except Exception as e:
        return {"zones": [], "exists": False, "error": str(e)}

@app.get("/check_zones")
def check_zones():
    """Check which cameras have saved zones"""
    zones_status = {}
    for camera_id in range(1, 5):
        polygon_path = polygon_paths.get(camera_id)
        zones_status[camera_id] = os.path.exists(polygon_path) if polygon_path else False
    return zones_status


# ============================================================================
# Model Info Endpoints (YOLO26m class schema)
# ============================================================================

@app.get("/model_info")
def model_info():
    """Return loaded model information and class schema."""
    from hazard_logic import CLASS_NAMES, BLOCKER_ACTIVE_CLASSES, HAZARD_TRIGGER_CLASSES
    return {
        "model_classes":      model.names if hasattr(model, "names") else {},
        "num_classes":        len(model.names) if hasattr(model, "names") else 0,
        "class_schema": {
            "gate_open":        {"id": 0, "role": "blocker_active"},
            "person":           {"id": 1, "role": "safety_subject"},
            "pot_blocking":     {"id": 2, "role": "blocker_active"},
            "pot_hauler":       {"id": 3, "role": "hazard_trigger"},
            "pot_not_blocking": {"id": 4, "role": "blocker_inactive"},
        },
        "hazard_logic": {
            "equipment_in_zone":  "HAZARD (highest priority)",
            "person_no_blocker":  "HAZARD",
            "person_with_blocker": "SAFE",
            "zone_clear":         "SAFE",
        },
        "device": _DEVICE,
    }


@app.get("/hazard_status")
async def hazard_status():
    """Live per-camera zone states — populated by running streams."""
    from stream_generator import _LIVE_STATES, _LIVE_STATES_LOCK
    with _LIVE_STATES_LOCK:
        return dict(_LIVE_STATES)


# ============================================================================
# PHASE 1: Multi-Camera Zone Management Endpoints
# ============================================================================

@app.post("/zones/define-multi-camera")
async def define_multi_camera_zones(request: Request):
    """
    Define and validate zones across all 4 cameras.
    
    Request Body:
    {
        "name": "Zone Name",
        "zones": [
            {
                "camera_id": 1,
                "polygon": [[x,y], [x,y], ...],
                "blocker_left": [x, y],
                "blocker_right": [x, y],
                "name": "Camera 1 Zone (optional)"
            },
            ... (cameras 2, 3, 4)
        ]
    }
    
    Response:
    {
        "success": bool,
        "zone_group_id": str,
        "message": str,
        "validation": {
            "is_continuous": bool,
            "continuity_type": str,
            "overlaps": [...]
        }
    }
    """
    try:
        data = await request.json()
        zone_configs = data.get("zones", [])
        name = data.get("name", "Multi-Camera Zone")
        
        # Add zone name to each config if not present
        for config in zone_configs:
            if "name" not in config:
                config["name"] = name
        
        zone_manager = get_zone_sync_manager()
        is_valid, reason, zone_group = zone_manager.link_zones(zone_configs)
        
        if is_valid:
            return {
                "success": True,
                "zone_group_id": zone_group["zone_group_id"],
                "message": reason,
                "validation": zone_group["validation"]
            }
        else:
            return {
                "success": False,
                "zone_group_id": None,
                "message": reason,
                "validation": None
            }
    
    except Exception as e:
        return {
            "success": False,
            "zone_group_id": None,
            "message": f"Error: {str(e)}",
            "validation": None
        }


@app.get("/zones/group/{zone_group_id}")
async def get_zone_group(zone_group_id: str):
    """
    Retrieve complete zone group with all 4 cameras.
    
    Response:
    {
        "zone_group_id": str,
        "name": str,
        "created_at": str,
        "last_updated": str,
        "cameras": [
            {
                "camera_id": int,
                "polygon": [[x,y], ...],
                "blocker_left": [x, y],
                "blocker_right": [x, y],
                "name": str
            },
            ... (cameras 2, 3, 4)
        ],
        "validation": {
            "is_continuous": bool,
            "continuity_type": str,
            "overlaps": [...]
        }
    }
    """
    try:
        zone_manager = get_zone_sync_manager()
        zone_group = zone_manager.load_zone_group(zone_group_id)
        
        if zone_group:
            return zone_group
        else:
            return {
                "error": f"Zone group '{zone_group_id}' not found"
            }
    
    except Exception as e:
        return {"error": str(e)}


@app.get("/zones/group/{zone_group_id}/camera/{camera_id}")
async def get_zone_for_camera(zone_group_id: str, camera_id: int):
    """
    Retrieve camera-specific zone from a zone group.
    
    Response:
    {
        "camera_id": int,
        "polygon": [[x,y], ...],
        "blocker_left": [x, y],
        "blocker_right": [x, y],
        "name": str
    }
    """
    try:
        zone_manager = get_zone_sync_manager()
        camera_zone = zone_manager.get_zone_for_camera(zone_group_id, camera_id)
        
        if camera_zone:
            return camera_zone
        else:
            return {
                "error": f"Zone for camera {camera_id} in group '{zone_group_id}' not found"
            }
    
    except Exception as e:
        return {"error": str(e)}


@app.get("/zones/list")
async def list_zone_groups():
    """
    List all available zone groups.
    
    Response:
    {
        "zone_groups": [
            {
                "zone_group_id": str,
                "name": str,
                "created_at": str,
                "last_updated": str
            },
            ...
        ]
    }
    """
    try:
        zone_manager = get_zone_sync_manager()
        all_groups = zone_manager.get_all_zone_groups()
        
        # Return simplified info for list
        zone_list = []
        for group in all_groups:
            zone_list.append({
                "zone_group_id": group["zone_group_id"],
                "name": group["name"],
                "created_at": group["created_at"],
                "last_updated": group["last_updated"]
            })
        
        return {
            "count": len(zone_list),
            "zone_groups": zone_list
        }
    
    except Exception as e:
        return {"error": str(e)}


@app.delete("/zones/group/{zone_group_id}")
async def delete_zone_group(zone_group_id: str):
    """
    Delete a zone group.
    
    Response:
    {
        "success": bool,
        "message": str
    }
    """
    try:
        zone_manager = get_zone_sync_manager()
        success, reason = zone_manager.delete_zone_group(zone_group_id)
        
        return {
            "success": success,
            "message": reason
        }
    
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }


# ============================================================================
# VLM REASONING ENDPOINTS
# Two-stage pipeline: YOLO (Stage 1) → Gemma 3 27B (Stage 2)
# ============================================================================

# In-memory store of the last N hazard analyses (shown in the VLM Reasoning page)
_vlm_analysis_history: list = []
_VLM_HISTORY_MAX = 20
_vlm_history_lock = threading.Lock()


@app.post("/analyze_hazard")
async def analyze_hazard(request: Request):
    """
    Trigger VLM analysis on a hazard event.

    Request body:
    {
        "snapshot_path":  "snapshots/2_2026-04-21_12-30-00.jpg",
        "camera_id":      2,
        "detections":     [{"class": "pot_hauler", "conf": 0.93}, ...],
        "zone_status":    "HAZARD",
        "zone_reason":    "pot_hauler active in bay — blockers not confirmed",
        "source_camera":  2   (optional — for cross-camera propagation)
    }

    Returns full analysis dict from hazard_reason.analyze_hazard_event()
    plus an "id" field for history lookup.
    """
    try:
        data = await request.json()
        snapshot_path = data.get("snapshot_path", "")

        if not snapshot_path or not os.path.exists(snapshot_path):
            return JSONResponse(
                status_code=404,
                content={"error": f"Snapshot not found: {snapshot_path}"}
            )

        result = analyze_hazard_event(
            snapshot_path  = snapshot_path,
            camera_id      = data.get("camera_id", 0),
            detections     = data.get("detections", []),
            zone_status    = data.get("zone_status", "HAZARD"),
            zone_reason    = data.get("zone_reason", ""),
            source_camera  = data.get("source_camera"),
        )

        # Store in history
        with _vlm_history_lock:
            result["id"] = len(_vlm_analysis_history)
            _vlm_analysis_history.append(result)
            if len(_vlm_analysis_history) > _VLM_HISTORY_MAX:
                _vlm_analysis_history.pop(0)

        return JSONResponse(content=result)

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/vlm_history")
def vlm_history():
    """Return the list of past VLM hazard analyses (most recent first)."""
    with _vlm_history_lock:
        return list(reversed(_vlm_analysis_history))


@app.get("/latest_snapshots")
def latest_snapshots():
    """
    Return the 10 most recent hazard snapshots from the snapshots/ directory,
    with metadata parsed from filenames (camera_id, timestamp).
    Format: camera_{id}_{datetime}.jpg
    """
    snap_dir = "snapshots"
    if not os.path.exists(snap_dir):
        return {"snapshots": []}

    files = sorted(
        [f for f in os.listdir(snap_dir) if f.endswith(".jpg")],
        reverse=True
    )[:10]

    result = []
    for fname in files:
        parts = fname.replace(".jpg", "").split("_")
        camera_id = int(parts[0]) if parts and parts[0].isdigit() else 0
        result.append({
            "filename": fname,
            "path":     f"snapshots/{fname}",
            "url":      f"http://localhost:8001/snapshots/{fname}",
            "camera_id": camera_id,
        })
    return {"snapshots": result}