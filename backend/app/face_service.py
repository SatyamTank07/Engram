"""Face embedding service using CLIP (clip-ViT-B-32) via sentence-transformers."""

from sentence_transformers import SentenceTransformer
from PIL import Image
import io

CLIP_MODEL_NAME = "clip-ViT-B-32"  # 512-dim output, matches vector_db.FACE_EMBEDDING_DIM
_clip_model = None


def get_clip_model() -> SentenceTransformer:
    """Load CLIP model lazily — cached after first call (~350MB download on first run)."""
    global _clip_model
    if _clip_model is None:
        _clip_model = SentenceTransformer(CLIP_MODEL_NAME)
    return _clip_model


def generate_face_embedding(image_bytes: bytes) -> list[float]:
    """
    Encode an image to a 512-dim CLIP embedding.
    Accepts any PIL-readable format (JPEG, PNG, WebP, etc.)
    """
    model = get_clip_model()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    embedding = model.encode(image)
    return embedding.tolist()
