export async function uploadVideo(streamId, file) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`http://localhost:8001/upload_video_${streamId}`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(`Failed to upload video ${streamId}: ${response.statusText}`);
  }
  return await response.json();
}

export async function setPolygon(streamId, polygons) {
  // Each polygon must have: { label, color, points }
  await fetch(`http://localhost:8001/set_polygon_${streamId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ polygons }),  // Pass full zone structure
  });
}

export async function setConfidence(streamId, confidence) {
  await fetch(`http://localhost:8001/set_confidence_${streamId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confidence }),
  });
}
