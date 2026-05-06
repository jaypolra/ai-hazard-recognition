import React, { useEffect, useRef, useState } from "react";

const LiveStream = ({ polygon }) => {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const wsRef = useRef(null);
  const [videoFile, setVideoFile] = useState(null);
  const [videoReady, setVideoReady] = useState(false);
  const [outputFrame, setOutputFrame] = useState(null);

  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8001/ws/stream");
    wsRef.current = ws;

    ws.onopen = () => console.log("✅ WebSocket connected");
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setOutputFrame(data.processed_frame);
    };

    return () => ws.close();
  }, []);

  useEffect(() => {
    const sendFrame = () => {
      if (!wsRef.current || wsRef.current.readyState !== 1) return;
      if (!videoRef.current || !canvasRef.current || !videoReady) return;

      const ctx = canvasRef.current.getContext("2d");
      ctx.drawImage(videoRef.current, 0, 0, 640, 480);
      const frame = canvasRef.current.toDataURL("image/png");

      wsRef.current.send(JSON.stringify({ frame, polygon }));
    };

    const interval = setInterval(sendFrame, 100); // 10 FPS
    return () => clearInterval(interval);
  }, [polygon, videoReady]);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      const videoURL = URL.createObjectURL(file);
      setVideoFile(videoURL);
      setVideoReady(false);
      setOutputFrame(null);
    }
  };

  return (
    <div style={{ textAlign: 'center' }}>
      <h3>🧠 Processed Output</h3>
      {outputFrame && (
        <img
          src={outputFrame}
          alt="Processed Frame"
          width={640}
          height={480}
          style={{ border: '1px solid #ccc', marginBottom: '10px' }}
        />
      )}

      {videoFile && (
        <video
          ref={videoRef}
          autoPlay
          muted
          controls
          width={640}
          height={480}
          onCanPlay={() => {
            videoRef.current.play();
            setVideoReady(true);
          }}
          style={{ marginBottom: '10px' }}
        >
          <source src={videoFile} type="video/mp4" />
        </video>
      )}

      <canvas ref={canvasRef} width={640} height={480} style={{ display: "none" }} />

      <div>
        <label>👥 Choose a video file: </label>
        <input type="file" accept="video/*" onChange={handleFileChange} />
      </div>
    </div>
  );
};

export default LiveStream;
