import cv2
import shutil

def save_uploaded_video(file, save_path):
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

def capture_first_frame(video_path, screenshot_path):
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    if ret:
        resized = cv2.resize(frame, (640, 480))  # Ensure match with stream resolution
        cv2.imwrite(screenshot_path, resized)
    cap.release()

