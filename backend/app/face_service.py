"""Face embedding service using InsightFace (ArcFace) for accurate face recognition.

Uses the buffalo_l model bundle which includes:
- RetinaFace: face detection + alignment
- ArcFace: 512-dim face embedding (identity-specific, not scene-level)
"""

import io
import numpy as np
import cv2
from insightface.app import FaceAnalysis

_face_app = None


def get_face_app() -> FaceAnalysis:
    """Load InsightFace model lazily — cached after first call (~300MB download on first run)."""
    global _face_app
    if _face_app is None:
        _face_app = FaceAnalysis(
            name="buffalo_l",
            providers=["CPUExecutionProvider"],
        )
        _face_app.prepare(ctx_id=0, det_size=(640, 640))
    return _face_app


def _bytes_to_cv2(image_bytes: bytes) -> np.ndarray:
    """Convert raw image bytes to a BGR cv2 image array."""
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image — unsupported format or corrupted data")
    return img


def generate_face_embedding(image_bytes: bytes) -> list[float]:
    """
    Detect the single/largest face in an image and return its 512-dim ArcFace embedding.

    Raises ValueError if no face is detected.
    Use detect_and_embed_all_faces() for group photos.
    """
    app = get_face_app()
    img = _bytes_to_cv2(image_bytes)
    faces = app.get(img)

    if not faces:
        raise ValueError("No face detected in the image")

    # Pick the largest face (by bounding-box area)
    face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    return face.embedding.tolist()


def detect_and_embed_all_faces(image_bytes: bytes) -> list[dict]:
    """
    Detect ALL faces in an image and return embeddings + metadata for each.

    Returns a list of dicts, each containing:
    - embedding: list[float] — 512-dim ArcFace vector
    - bbox: list[float] — [x1, y1, x2, y2] bounding box
    - det_score: float — face detection confidence (0.0-1.0)

    Returns empty list if no faces are detected.
    """
    app = get_face_app()
    img = _bytes_to_cv2(image_bytes)
    faces = app.get(img)

    results = []
    for face in faces:
        results.append({
            "embedding": face.embedding.tolist(),
            "bbox": [round(float(c), 1) for c in face.bbox],
            "det_score": round(float(face.det_score), 4),
        })

    # Sort by detection score descending (most confident first)
    results.sort(key=lambda r: r["det_score"], reverse=True)
    return results


def identify_faces_in_image(image_bytes: bytes, user_id: str) -> dict:
    """
    End-to-end face identification: detect all faces → search pgvector → enrich from Neo4j.

    Shared helper used by both the REST endpoint and MCP tool to avoid duplication.

    Returns dict with:
    - faces_detected: int
    - faces: list of per-face results with bbox, det_score, match_status, and matches
    """
    from . import vector_db, graph_db

    detected_faces = detect_and_embed_all_faces(image_bytes)

    if not detected_faces:
        return {"faces_detected": 0, "faces": [], "message": "No faces detected in the image"}

    faces_result = []
    for idx, face_data in enumerate(detected_faces):
        matches = vector_db.face_search(user_id, face_data["embedding"], limit=3)

        face_matches = []
        for match in matches:
            person = graph_db.get_person_node(match["person_id"])
            if person:
                face_matches.append({
                    **person,
                    "confidence_score": round(match["similarity_score"], 3),
                })

        faces_result.append({
            "face_index": idx,
            "bbox": face_data["bbox"],
            "det_score": face_data["det_score"],
            "match_status": "matched" if face_matches else "unknown",
            "matches": face_matches,
        })

    return {"faces_detected": len(detected_faces), "faces": faces_result}

