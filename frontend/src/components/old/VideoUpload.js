import React, { useState } from 'react';
import axios from 'axios';

const VideoUpload = ({ polygon }) => {
    const [file, setFile] = useState(null);

    const handleUpload = async () => {
        if (!file) return;
        
        const formData = new FormData();
        formData.append('file', file);
        formData.append('polygon', JSON.stringify(polygon));

        await axios.post('http://localhost:8001/upload', formData);
        alert('Video uploaded!');
    };

    return (
        <div>
            <input type="file" onChange={(e) => setFile(e.target.files[0])} />
            <button onClick={handleUpload}>Upload Video</button>
        </div>
    );
};

export default VideoUpload;
