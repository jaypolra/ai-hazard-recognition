import React, { useRef, useState } from "react";
import { uploadVideo } from "../api";

const SERVER_URL = "http://localhost:8001";

const VideoUpload = ({ onUpload }) => {
  const fileInputRefs = {
    1: useRef(null),
    2: useRef(null),
    3: useRef(null),
    4: useRef(null),
  };
  const [uploadedVideos, setUploadedVideos] = useState({
    1: null,
    2: null,
    3: null,
    4: null,
  });
  const [videoNames, setVideoNames] = useState({
    1: "",
    2: "",
    3: "",
    4: "",
  });
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState({
    1: 0,
    2: 0,
    3: 0,
    4: 0,
  });

  const handleFileChange = (cameraId, e) => {
    const file = e.target.files[0];
    if (file && file.type.startsWith("video/")) {
      // Store the actual file object, not blob URL
      setUploadedVideos((prev) => ({ ...prev, [cameraId]: file }));
      setVideoNames((prev) => ({ ...prev, [cameraId]: file.name }));
    } else {
      alert("Please select a valid video file");
    }
  };

  const handleClick = (cameraId) => {
    fileInputRefs[cameraId].current?.click();
  };

  const handleStartMonitoring = async () => {
    const allReady = Object.values(uploadedVideos).every((v) => v !== null);
    if (!allReady) {
      alert("Please upload videos for all 4 cameras");
      return;
    }

    setUploading(true);

    try {
      // Upload all 4 videos to the backend
      const uploadPromises = Object.entries(uploadedVideos).map(([cameraId, file]) =>
        uploadVideo(parseInt(cameraId), file)
          .then(() => {
            setUploadProgress((prev) => ({ ...prev, [cameraId]: 100 }));
          })
          .catch((err) => {
            console.error(`Failed to upload camera ${cameraId}:`, err);
            throw err;
          })
      );

      await Promise.all(uploadPromises);

      // All uploads successful - create blob URLs for frontend display
      const videoUrls = {};
      Object.entries(uploadedVideos).forEach(([cameraId, file]) => {
        videoUrls[cameraId] = URL.createObjectURL(file);
      });

      // Notify parent component and start monitoring
      onUpload(videoUrls);
    } catch (error) {
      alert("Failed to upload videos. Please try again.");
      setUploading(false);
      setUploadProgress({ 1: 0, 2: 0, 3: 0, 4: 0 });
    }
  };

  const allUploaded = Object.values(uploadedVideos).every((v) => v !== null);

  return (
    <div>
      <h2 style={{ marginBottom: "1.5rem", color: "#1a202c" }}>📹 Upload Camera Feeds</h2>
      <p style={{ color: "#64748b", marginBottom: "2rem" }}>
        Upload a video file for each camera. Each video will be displayed independently as a separate live feed.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "1.5rem", marginBottom: "2rem" }}>
        {[1, 2, 3, 4].map((cameraId) => (
          <div
            key={cameraId}
            onClick={() => handleClick(cameraId)}
            style={{
              border: "2px dashed #cbd5e1",
              borderRadius: "10px",
              padding: "1.5rem",
              textAlign: "center",
              cursor: "pointer",
              transition: "all 0.2s ease",
              backgroundColor: uploadedVideos[cameraId] ? "#f0fdf4" : "#ffffff",
              borderColor: uploadedVideos[cameraId] ? "#22c55e" : "#cbd5e1",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = "#3b82f6";
              e.currentTarget.style.backgroundColor = "rgba(59, 130, 246, 0.02)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = uploadedVideos[cameraId] ? "#22c55e" : "#cbd5e1";
              e.currentTarget.style.backgroundColor = uploadedVideos[cameraId] ? "#f0fdf4" : "#ffffff";
            }}
          >
            <div style={{ fontSize: "2rem", marginBottom: "0.75rem" }}>
              {uploadedVideos[cameraId] ? "✓" : "📹"}
            </div>
            <p style={{ fontSize: "1rem", color: "#1a202c", marginBottom: "0.5rem", fontWeight: "600" }}>
              Camera {cameraId}
            </p>
            {uploadedVideos[cameraId] ? (
              <p style={{ fontSize: "0.85rem", color: "#22c55e", fontWeight: "500" }}>
                ✓ {videoNames[cameraId]}
              </p>
            ) : (
              <p style={{ fontSize: "0.9rem", color: "#64748b" }}>
                Click to upload video
              </p>
            )}
            <input
              ref={fileInputRefs[cameraId]}
              type="file"
              accept="video/*"
              onChange={(e) => handleFileChange(cameraId, e)}
              style={{ display: "none" }}
            />
          </div>
        ))}
      </div>

      <button
        onClick={handleStartMonitoring}
        disabled={!allUploaded || uploading}
        style={{
          width: "100%",
          padding: "1rem",
          backgroundColor: !allUploaded || uploading ? "#cbd5e1" : "#22c55e",
          color: "white",
          border: "none",
          borderRadius: "8px",
          fontSize: "1rem",
          fontWeight: "600",
          cursor: !allUploaded || uploading ? "not-allowed" : "pointer",
          transition: "all 0.2s ease",
        }}
        onMouseEnter={(e) => {
          if (allUploaded && !uploading) {
            e.target.style.backgroundColor = "#16a34a";
          }
        }}
        onMouseLeave={(e) => {
          if (allUploaded && !uploading) {
            e.target.style.backgroundColor = "#22c55e";
          }
        }}
      >
        {uploading ? "⏳ Uploading to Backend..." : "🚀 Start Multi-Camera Monitoring"}
      </button>

      {uploading && (
        <div style={{ marginTop: "1.5rem", padding: "1rem", backgroundColor: "#f0f4f8", borderRadius: "8px" }}>
          <p style={{ color: "#1a202c", fontWeight: "600", marginBottom: "0.75rem" }}>Upload Progress:</p>
          {[1, 2, 3, 4].map((cameraId) => (
            <div key={cameraId} style={{ marginBottom: "0.75rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.25rem" }}>
                <span style={{ color: "#64748b", fontSize: "0.9rem" }}>Camera {cameraId}</span>
                <span style={{ color: "#3b82f6", fontSize: "0.9rem", fontWeight: "600" }}>
                  {uploadProgress[cameraId]}%
                </span>
              </div>
              <div style={{
                width: "100%",
                height: "6px",
                backgroundColor: "#e4e8f0",
                borderRadius: "3px",
                overflow: "hidden"
              }}>
                <div style={{
                  width: `${uploadProgress[cameraId]}%`,
                  height: "100%",
                  backgroundColor: "#3b82f6",
                  transition: "width 0.3s ease"
                }} />
              </div>
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: "2rem", padding: "1.5rem", background: "#f0f4f8", borderRadius: "10px" }}>
        <h3 style={{ color: "#1a202c", marginBottom: "0.75rem" }}>ℹ️ How it works:</h3>
        <ul style={{ color: "#64748b", lineHeight: "1.8", marginLeft: "1.5rem" }}>
          <li>Select a video file for each of the 4 cameras</li>
          <li>Click "Start Multi-Camera Monitoring" to upload videos to backend</li>
          <li>Each camera will stream its video with YOLO detection and zone overlays</li>
          <li>Draft and configure polygon detection zones in Zone Configuration</li>
          <li>Zones will appear on the live monitoring streams with dynamic color feedback</li>
          <li>Click any camera to view in full screen</li>
          <li>Switch between cameras without returning to grid</li>
        </ul>
      </div>
    </div>
  );
};

export default VideoUpload;
