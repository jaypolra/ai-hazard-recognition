import base64
import cv2
import numpy as np
from fastapi import WebSocket
import torch
from ultralytics import YOLO


# ✅ Load using safe torch.load
model = YOLO("yolov8m.pt").to("cuda")


def decode_base64_image(base64_str: str):
    header, encoded = base64_str.split(",", 1)
    img_data = base64.b64decode(encoded)
    nparr = np.frombuffer(img_data, np.uint8)
    return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

def encode_image_to_base64(image):
    _, buffer = cv2.imencode('.jpg', image)
    b64 = base64.b64encode(buffer).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"

async def process_stream(websocket: WebSocket):
    await websocket.accept()
    print("✅ WebSocket connected")

    while True:
        try:
            data = await websocket.receive_json()
            frame_b64 = data["frame"]
            polygon = data["polygon"]

            frame = decode_base64_image(frame_b64)
            frame = cv2.resize(frame, (416, 416))  # 🧠 speed boost

            polygon_np = np.array(polygon, np.int32).reshape((-1, 1, 2))

            results = model.track(frame, classes=[0], persist=True)

            annotated = frame.copy()
            overlay = annotated.copy()
            cv2.fillPoly(overlay, [polygon_np], (0, 0, 255))
            cv2.addWeighted(overlay, 0.3, annotated, 0.7, 0, annotated)
            cv2.polylines(annotated, [polygon_np], True, (0, 0, 255), 2)

            cv2.putText(annotated, "NO-GO ZONE", (polygon_np[0][0][0], polygon_np[0][0][1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            for box in results[0].boxes.xyxy:
                x1, y1, x2, y2 = map(int, box[:4])
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (255, 0, 0), 2)
                cv2.putText(annotated, "Person", (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
                if cv2.pointPolygonTest(polygon_np, (cx, cy), False) >= 0:
                    cv2.putText(annotated, "Person IN NO-GO ZONE", (20, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

            frame_out = encode_image_to_base64(annotated)
            await websocket.send_json({"processed_frame": frame_out})

        except Exception as e:
            print("❌ WebSocket error:", e)
            break
