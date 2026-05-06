import React, { useRef, useEffect, useState } from 'react';

const Canvas = ({ onPolygonChange }) => {
    const canvasRef = useRef(null);
    const [points, setPoints] = useState([
        [150, 100], [450, 100], [500, 300], [200, 400], [100, 250]
    ]);
    const [draggingIndex, setDraggingIndex] = useState(null);

    const radius = 6;

    useEffect(() => {
        draw();
    }, [points]);

    const draw = () => {
        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        ctx.beginPath();
        if (points.length) {
            ctx.moveTo(points[0][0], points[0][1]);
            points.forEach(([x, y], index) => {
                if (index !== 0) ctx.lineTo(x, y);
            });
            ctx.closePath();
        }
        ctx.strokeStyle = 'red';
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.fillStyle = 'rgba(255, 0, 0, 0.2)';
        ctx.fill();

        points.forEach(([x, y]) => {
            ctx.beginPath();
            ctx.arc(x, y, radius, 0, 2 * Math.PI);
            ctx.fillStyle = 'blue';
            ctx.fill();
        });
    };

    const getMousePos = (e) => {
        const rect = canvasRef.current.getBoundingClientRect();
        return [e.clientX - rect.left, e.clientY - rect.top];
    };

    const onMouseDown = (e) => {
        const [x, y] = getMousePos(e);
        points.forEach(([px, py], index) => {
            if ((px - x) ** 2 + (py - y) ** 2 < radius ** 2) {
                setDraggingIndex(index);
            }
        });
    };

    const onMouseMove = (e) => {
        if (draggingIndex !== null) {
            const [x, y] = getMousePos(e);
            const newPoints = [...points];
            newPoints[draggingIndex] = [x, y];
            setPoints(newPoints);
            onPolygonChange(newPoints); // Send updates live
        }
    };

    const onMouseUp = () => {
        setDraggingIndex(null);
    };

    return (
        <canvas
            ref={canvasRef}
            width={640}
            height={480}
            style={{ border: '1px solid black' }}
            onMouseDown={onMouseDown}
            onMouseMove={onMouseMove}
            onMouseUp={onMouseUp}
        />
    );
};

export default Canvas;
