"""
hazard_reason.py — YOLO → VLM Reasoning Bridge
================================================
Takes a hazard event (snapshot + YOLO detection data) and calls the local
Gemma 3 27B model (vLLM, port 8000) twice:
  1. Without domain context  → shows what a generic VLM sees
  2. With domain context + CoT prompt → shows grounded, plant-specific reasoning

This is the Stage 2 of the two-stage pipeline:
  Stage 1: YOLO  — what is there, where, how confident
  Stage 2: VLM   — why dangerous, how severe, what action to take
"""

import base64
import time
from pathlib import Path
from typing import Optional

VLLM_URL    = "http://localhost:8000/v1"
MAX_TOKENS  = 500
TEMPERATURE = 0.2

# ── SDI plant domain context (mirrors ARIA demo context for consistency) ──────
SDI_DOMAIN_CONTEXT = """You are a safety analyst for the SDI Butler steel plant bay monitoring system.

PLANT CONTEXT:
- This is a steel plant bay where molten metal pot haulers operate.
- A pot hauler is a large, heavy vehicle that transports crucibles of liquid steel at ~1500°C.
- The bay uses a zone system: RED ZONES are active operation areas with restricted personnel entry.
- Physical blockers (swing-gate or pot_blocking) at BOTH north AND south bay ends define a safe corridor.
- If NO blockers are confirmed at both ends, the entire bay is a hazard zone when equipment is active.
- Workers on foot must NEVER be in the bay when pot haulers are active without confirmed blockers.

YOUR ROLE (Stage 2 — reasoning only):
The YOLO detection system (Stage 1) has already identified what objects are present and their locations.
Your job is NOT to re-detect — it is to REASON about the safety implications and recommend action.
Think step by step before concluding."""

# ── Prompt templates ───────────────────────────────────────────────────────────

def _build_prompt_no_context(detections: list, zone_status: str, zone_reason: str) -> str:
    """Generic prompt — no plant-specific context. Shows VLM baseline."""
    det_lines = "\n".join(
        f"  - {d['class']} (confidence {d['conf']:.0%}) detected in frame"
        for d in detections
    ) or "  - No objects detected"

    return f"""The automated detection system flagged this camera frame as a safety alert.

Detections:
{det_lines}

Zone status: {zone_status}
System reason: {zone_reason}

Describe the hazard in this scene and what action should be taken."""


def _build_prompt_with_context(detections: list, zone_status: str, zone_reason: str,
                                camera_id: int, source_camera: Optional[int] = None) -> str:
    """Domain-specific CoT prompt — plant context + chain-of-thought structure."""
    det_lines = "\n".join(
        f"  - {d['class']} (confidence {d['conf']:.0%})"
        for d in detections
    ) or "  - No objects detected in this camera's frame"

    cross_cam_note = ""
    if source_camera and source_camera != camera_id:
        cross_cam_note = (
            f"\nNOTE: The pot hauler was detected by Camera {source_camera}. "
            f"This camera (Camera {camera_id}) triggered a bay-wide alert because "
            f"all zones in the same bay become hazardous when equipment is active anywhere in it."
        )

    return f"""{SDI_DOMAIN_CONTEXT}

---
YOLO DETECTION REPORT — Camera {camera_id}
Detections this frame:
{det_lines}{cross_cam_note}

Zone {camera_id} status: {zone_status}
YOLO hazard reason: {zone_reason}
---

Think step by step:
1. What is the specific physical danger in this scene?
2. Who is at risk and how much time do they have to respond?
3. What is the severity level: CRITICAL / HIGH / MEDIUM / LOW?
4. What must the safety operator do RIGHT NOW?
5. What must any workers in the bay do RIGHT NOW?

Conclude with a one-line verdict starting with VERDICT:"""


# ── Image encoding ─────────────────────────────────────────────────────────────

def _encode_image(image_path: str) -> tuple[str, str]:
    """Base64-encode image for vLLM multimodal API."""
    path = Path(image_path)
    mime = "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode(), mime


# ── Core VLM call ──────────────────────────────────────────────────────────────

def _call_gemma(image_path: str, prompt: str) -> str:
    """
    Call local Gemma 3 27B via vLLM (OpenAI-compatible API).
    Returns the model response text, or an error string.
    """
    try:
        from openai import OpenAI
        client = OpenAI(base_url=VLLM_URL, api_key="EMPTY")

        models = client.models.list()
        if not models.data:
            return "⚠️ vLLM server is reachable but no models are loaded."
        model_id = models.data[0].id

        img_b64, mime = _encode_image(image_path)

        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
                {"type": "text", "text": prompt},
            ]
        }]

        response = client.chat.completions.create(
            model=model_id,
            messages=messages,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
        )
        return response.choices[0].message.content.strip()

    except ConnectionRefusedError:
        return "⚠️ vLLM server not reachable on port 8000. Start with: vllm serve google/gemma-3-27b-it --port 8000"
    except Exception as e:
        return f"⚠️ VLM call failed: {str(e)}"


# ── Public API ─────────────────────────────────────────────────────────────────

def analyze_hazard_event(
    snapshot_path: str,
    camera_id: int,
    detections: list,
    zone_status: str,
    zone_reason: str,
    source_camera: Optional[int] = None,
) -> dict:
    """
    Run both VLM analyses (with and without domain context) on a hazard snapshot.

    Args:
        snapshot_path:  Path to the YOLO-annotated snapshot image
        camera_id:      Camera that owns this zone (1-4)
        detections:     List of dicts: [{"class": "pot_hauler", "conf": 0.93}, ...]
        zone_status:    "HAZARD" or "SAFE"
        zone_reason:    Human-readable YOLO reason string
        source_camera:  Camera that originally detected the equipment (cross-cam propagation)

    Returns:
        {
            "snapshot_path":    str,
            "camera_id":        int,
            "zone_status":      str,
            "zone_reason":      str,
            "detections":       list,
            "source_camera":    int | None,
            "response_no_ctx":  str,   ← VLM without domain context
            "response_with_ctx": str,  ← VLM with SDI context + CoT
            "timestamp":        float,
        }
    """
    t0 = time.time()

    prompt_no_ctx   = _build_prompt_no_context(detections, zone_status, zone_reason)
    prompt_with_ctx = _build_prompt_with_context(
        detections, zone_status, zone_reason, camera_id, source_camera
    )

    print(f"[HazardReason] Analyzing snapshot for Camera {camera_id} — {zone_reason}")

    response_no_ctx   = _call_gemma(snapshot_path, prompt_no_ctx)
    response_with_ctx = _call_gemma(snapshot_path, prompt_with_ctx)

    elapsed = time.time() - t0
    print(f"[HazardReason] Done in {elapsed:.1f}s")

    return {
        "snapshot_path":     snapshot_path,
        "camera_id":         camera_id,
        "zone_status":       zone_status,
        "zone_reason":       zone_reason,
        "detections":        detections,
        "source_camera":     source_camera,
        "response_no_ctx":   response_no_ctx,
        "response_with_ctx": response_with_ctx,
        "timestamp":         t0,
    }
