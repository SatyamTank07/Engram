'use client';

import { useRef, useEffect, useState } from 'react';
import { FaceDetection } from '@/lib/api';

interface FaceOverlayProps {
    imageSrc: string;
    faces: FaceDetection[];
    highlightedFace: number | null;
    onFaceHover: (index: number | null) => void;
}

const MATCHED_COLOR = '#22c55e';
const UNKNOWN_COLOR = '#f59e0b';
const HIGHLIGHT_COLOR = '#3b82f6';

export default function FaceOverlay({ imageSrc, faces, highlightedFace, onFaceHover }: FaceOverlayProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const imgRef = useRef<HTMLImageElement>(null);
    const [scale, setScale] = useState({ x: 1, y: 1, offsetX: 0, offsetY: 0 });

    useEffect(() => {
        const img = imgRef.current;
        if (!img) return;

        const updateScale = () => {
            const displayW = img.clientWidth;
            const displayH = img.clientHeight;
            const naturalW = img.naturalWidth;
            const naturalH = img.naturalHeight;

            if (!naturalW || !naturalH) return;

            // The image uses object-contain, so compute the actual rendered area
            const imgAspect = naturalW / naturalH;
            const containerAspect = displayW / displayH;

            let renderedW: number, renderedH: number, offsetX: number, offsetY: number;

            if (imgAspect > containerAspect) {
                // Image is wider — full width, letterboxed vertically
                renderedW = displayW;
                renderedH = displayW / imgAspect;
                offsetX = 0;
                offsetY = (displayH - renderedH) / 2;
            } else {
                // Image is taller — full height, pillarboxed horizontally
                renderedH = displayH;
                renderedW = displayH * imgAspect;
                offsetX = (displayW - renderedW) / 2;
                offsetY = 0;
            }

            setScale({
                x: renderedW / naturalW,
                y: renderedH / naturalH,
                offsetX,
                offsetY,
            });
        };

        img.addEventListener('load', updateScale);
        window.addEventListener('resize', updateScale);
        // If already loaded
        if (img.complete) updateScale();

        return () => {
            img.removeEventListener('load', updateScale);
            window.removeEventListener('resize', updateScale);
        };
    }, [imageSrc]);

    return (
        <div ref={containerRef} className="relative inline-block w-full max-w-lg mx-auto">
            <img
                ref={imgRef}
                src={imageSrc}
                alt="Uploaded photo"
                className="w-full max-h-[400px] object-contain rounded-lg"
            />
            {faces.map((face) => {
                const [x1, y1, x2, y2] = face.bbox;
                const isHighlighted = highlightedFace === face.face_index;
                const color = isHighlighted
                    ? HIGHLIGHT_COLOR
                    : face.match_status === 'matched'
                        ? MATCHED_COLOR
                        : UNKNOWN_COLOR;

                return (
                    <div
                        key={face.face_index}
                        onMouseEnter={() => onFaceHover(face.face_index)}
                        onMouseLeave={() => onFaceHover(null)}
                        className="absolute cursor-pointer transition-all duration-150"
                        style={{
                            left: `${scale.offsetX + x1 * scale.x}px`,
                            top: `${scale.offsetY + y1 * scale.y}px`,
                            width: `${(x2 - x1) * scale.x}px`,
                            height: `${(y2 - y1) * scale.y}px`,
                            border: `2px solid ${color}`,
                            borderRadius: '4px',
                            boxShadow: isHighlighted ? `0 0 8px ${color}` : 'none',
                        }}
                    >
                        {/* Face number label */}
                        <span
                            className="absolute -top-5 left-0 text-[10px] font-bold px-1.5 py-0.5 rounded-t-sm text-white"
                            style={{ backgroundColor: color }}
                        >
                            {face.face_index + 1}
                        </span>
                    </div>
                );
            })}
        </div>
    );
}
