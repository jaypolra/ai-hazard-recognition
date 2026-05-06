import React, { useState } from "react";
import Sidebar from "./Sidebar";
import StreamCard from "./StreamCard";
import LogsDashboard from "./LogsDashboard";

const MonitoringPage = () => {
  const [selectedCamera, setSelectedCamera] = useState(1);
  const [videoUploaded1, setVideoUploaded1] = useState(false);
  const [videoUploaded2, setVideoUploaded2] = useState(false);
  const [videoSource, setVideoSource] = useState("video_1.mp4"); // webcam or file

  return (
    <div className="monitoring-page">
      <Sidebar
        selectedCamera={selectedCamera}
        setSelectedCamera={setSelectedCamera}
        setVideoSource={setVideoSource}
      />

      <div className="streams">
        {selectedCamera === 1 && (
          <StreamCard
            streamId={1}
            videoUploaded={videoUploaded1}
            setVideoUploaded={setVideoUploaded1}
            videoSource={videoSource}
          />
        )}
        {selectedCamera === 2 && (
          <StreamCard
            streamId={2}
            videoUploaded={videoUploaded2}
            setVideoUploaded={setVideoUploaded2}
            videoSource={videoSource}
          />
        )}
      </div>

      <LogsDashboard />
    </div>
  );
};

export default MonitoringPage;
