import csv
import os
from datetime import datetime
import cv2

LOG_FILE = "event_log.csv"

def log_event(camera_id, event_type, confidence, frame, polygon_active):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    screenshot_path = f"snapshots/{camera_id}_{timestamp.replace(' ', '_').replace(':', '-')}.jpg"

    # Ensure snapshot folder exists
    os.makedirs("snapshots", exist_ok=True)
    cv2.imwrite(screenshot_path, frame)

    row = {
        "timestamp": timestamp,
        "camera_id": camera_id,
        "event_type": event_type,
        "confidence": round(confidence, 2),
        "polygon_applied": polygon_active,
        "screenshot_path": screenshot_path
    }

    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, "a", newline="") as csvfile:
        fieldnames = ["timestamp", "camera_id", "event_type", "confidence", "polygon_applied", "screenshot_path"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
