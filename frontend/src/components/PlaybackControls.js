import React from "react";

const PlaybackControls = ({ 
  isLive, 
  isPaused, 
  currentTime, 
  onPause, 
  onPlaybackRewind, 
  onPlaybackForward, 
  onGoLive,
  canRewind,
  canForward
}) => {
  const formatTime = (seconds) => {
    if (!seconds && seconds !== 0) return "00:00";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div className="playback-controls-bar">
      <div className="time-display">
        {isLive ? "🔴 LIVE" : `${formatTime(currentTime)}`}
      </div>

      <button
        className={`playback-button ${isPaused ? "active" : ""}`}
        onClick={onPause}
        title={isPaused ? "Resume" : "Pause"}
      >
        {isPaused ? "▶ Resume" : "⏸ Pause"}
      </button>

      <button
        className="playback-button"
        onClick={onPlaybackRewind}
        disabled={!canRewind}
        title="Rewind 5 seconds"
      >
        ⏪ -5s
      </button>

      <button
        className="playback-button"
        onClick={onPlaybackForward}
        disabled={!canForward}
        title="Forward 5 seconds"
      >
        ⏩ +5s
      </button>

      <button
        className={`playback-button go-live-btn ${isLive ? "active" : ""}`}
        onClick={onGoLive}
        title="Return to live feed"
      >
        Go Live
      </button>
    </div>
  );
};

export default PlaybackControls;
