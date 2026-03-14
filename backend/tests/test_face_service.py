"""Tests for face_service.py — face detection and embedding via InsightFace."""

import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

import numpy as np
import pytest

from app import face_service


# ===================================================================
# _bytes_to_cv2
# ===================================================================
class TestBytesToCv2:
    @patch("app.face_service.cv2")
    def test_valid_image(self, mock_cv2):
        fake_img = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_cv2.imdecode.return_value = fake_img
        mock_cv2.IMREAD_COLOR = 1

        result = face_service._bytes_to_cv2(b"\x89PNG_fake_data")

        mock_cv2.imdecode.assert_called_once()
        assert np.array_equal(result, fake_img)

    @patch("app.face_service.cv2")
    def test_invalid_image_raises(self, mock_cv2):
        mock_cv2.imdecode.return_value = None
        mock_cv2.IMREAD_COLOR = 1

        with pytest.raises(ValueError, match="Could not decode image"):
            face_service._bytes_to_cv2(b"not_an_image")

    @patch("app.face_service.cv2")
    def test_empty_bytes(self, mock_cv2):
        mock_cv2.imdecode.return_value = None
        mock_cv2.IMREAD_COLOR = 1

        with pytest.raises(ValueError, match="Could not decode image"):
            face_service._bytes_to_cv2(b"")


# ===================================================================
# generate_face_embedding
# ===================================================================
class TestGenerateFaceEmbedding:
    def _make_face(self, bbox=(10, 10, 100, 100), embedding=None):
        face = MagicMock()
        face.bbox = list(bbox)
        face.embedding = np.array(embedding or [0.1] * 512)
        face.det_score = 0.95
        return face

    @patch("app.face_service._bytes_to_cv2")
    @patch("app.face_service.get_face_app")
    def test_single_face(self, mock_app, mock_cv2):
        mock_cv2.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        face = self._make_face()
        mock_app.return_value.get.return_value = [face]

        result = face_service.generate_face_embedding(b"fake_image")

        assert len(result) == 512
        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)

    @patch("app.face_service._bytes_to_cv2")
    @patch("app.face_service.get_face_app")
    def test_multiple_faces_picks_largest(self, mock_app, mock_cv2):
        mock_cv2.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        small_face = self._make_face(bbox=(10, 10, 50, 50), embedding=[0.2] * 512)
        large_face = self._make_face(bbox=(0, 0, 200, 200), embedding=[0.5] * 512)
        mock_app.return_value.get.return_value = [small_face, large_face]

        result = face_service.generate_face_embedding(b"fake_image")

        # Should pick the larger face (200x200 area)
        assert result == large_face.embedding.tolist()

    @patch("app.face_service._bytes_to_cv2")
    @patch("app.face_service.get_face_app")
    def test_no_face_raises(self, mock_app, mock_cv2):
        mock_cv2.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_app.return_value.get.return_value = []

        with pytest.raises(ValueError, match="No face detected"):
            face_service.generate_face_embedding(b"fake_image")

    @patch("app.face_service._bytes_to_cv2")
    @patch("app.face_service.get_face_app")
    def test_returns_512_dim_vector(self, mock_app, mock_cv2):
        mock_cv2.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        emb = [float(i) / 512 for i in range(512)]
        face = self._make_face(embedding=emb)
        mock_app.return_value.get.return_value = [face]

        result = face_service.generate_face_embedding(b"fake")
        assert len(result) == 512
        assert result == emb


# ===================================================================
# detect_and_embed_all_faces
# ===================================================================
class TestDetectAndEmbedAllFaces:
    def _make_face(self, bbox=(10, 10, 100, 100), det_score=0.95, embedding=None):
        face = MagicMock()
        face.bbox = np.array(bbox, dtype=np.float64)
        face.embedding = np.array(embedding or [0.1] * 512)
        face.det_score = np.float64(det_score)
        return face

    @patch("app.face_service._bytes_to_cv2")
    @patch("app.face_service.get_face_app")
    def test_multi_face_image(self, mock_app, mock_cv2):
        mock_cv2.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        faces = [
            self._make_face(bbox=(0, 0, 50, 50), det_score=0.85),
            self._make_face(bbox=(60, 60, 120, 120), det_score=0.99),
        ]
        mock_app.return_value.get.return_value = faces

        result = face_service.detect_and_embed_all_faces(b"fake")

        assert len(result) == 2
        # Sorted by det_score descending
        assert result[0]["det_score"] >= result[1]["det_score"]

    @patch("app.face_service._bytes_to_cv2")
    @patch("app.face_service.get_face_app")
    def test_result_structure(self, mock_app, mock_cv2):
        mock_cv2.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        face = self._make_face(bbox=(10.1, 20.2, 30.3, 40.4), det_score=0.9567)
        mock_app.return_value.get.return_value = [face]

        result = face_service.detect_and_embed_all_faces(b"fake")

        assert len(result) == 1
        r = result[0]
        assert "embedding" in r
        assert "bbox" in r
        assert "det_score" in r
        assert len(r["embedding"]) == 512
        assert len(r["bbox"]) == 4
        # bbox values are rounded to 1 decimal
        for val in r["bbox"]:
            assert isinstance(val, float)
        assert r["det_score"] == 0.9567

    @patch("app.face_service._bytes_to_cv2")
    @patch("app.face_service.get_face_app")
    def test_no_faces_returns_empty_list(self, mock_app, mock_cv2):
        mock_cv2.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_app.return_value.get.return_value = []

        result = face_service.detect_and_embed_all_faces(b"fake")
        assert result == []

    @patch("app.face_service._bytes_to_cv2")
    @patch("app.face_service.get_face_app")
    def test_sorted_by_det_score_descending(self, mock_app, mock_cv2):
        mock_cv2.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        faces = [
            self._make_face(det_score=0.70),
            self._make_face(det_score=0.99),
            self._make_face(det_score=0.85),
        ]
        mock_app.return_value.get.return_value = faces

        result = face_service.detect_and_embed_all_faces(b"fake")
        scores = [r["det_score"] for r in result]
        assert scores == sorted(scores, reverse=True)


# ===================================================================
# identify_faces_in_image
# ===================================================================
class TestIdentifyFacesInImage:
    @pytest.fixture
    def mock_deps(self):
        """Patch detect_and_embed_all_faces, vector_db, and graph_db.

        vector_db and graph_db are lazily imported inside identify_faces_in_image
        via `from . import vector_db, graph_db`, so we patch the actual module functions.
        """
        with (
            patch("app.face_service.detect_and_embed_all_faces") as mock_detect,
            patch("app.vector_db.face_search_batch") as mock_batch,
            patch("app.graph_db.get_person_nodes_batch", new_callable=AsyncMock) as mock_persons,
        ):
            yield mock_detect, mock_batch, mock_persons

    def test_no_faces_detected(self, mock_deps):
        mock_detect, _, _ = mock_deps
        mock_detect.return_value = []

        result = asyncio.get_event_loop().run_until_complete(
            face_service.identify_faces_in_image(b"fake", "user-1")
        )

        assert result["faces_detected"] == 0
        assert result["faces"] == []
        assert "No faces" in result["message"]

    def test_matched_face(self, mock_deps):
        mock_detect, mock_batch, mock_persons = mock_deps

        emb = [0.1] * 512
        mock_detect.return_value = [
            {"embedding": emb, "bbox": [10, 20, 30, 40], "det_score": 0.95}
        ]
        mock_batch.return_value = [
            [{"person_id": "p-1", "similarity_score": 0.92}]
        ]
        mock_persons.return_value = {
            "p-1": {"id": "p-1", "name": "Alice", "short_bio": "Engineer"}
        }

        result = asyncio.get_event_loop().run_until_complete(
            face_service.identify_faces_in_image(b"fake", "user-1")
        )

        assert result["faces_detected"] == 1
        face = result["faces"][0]
        assert face["match_status"] == "matched"
        assert len(face["matches"]) == 1
        assert face["matches"][0]["name"] == "Alice"
        assert face["matches"][0]["confidence_score"] == 0.92

    def test_unmatched_face(self, mock_deps):
        mock_detect, mock_batch, mock_persons = mock_deps

        mock_detect.return_value = [
            {"embedding": [0.1] * 512, "bbox": [0, 0, 50, 50], "det_score": 0.88}
        ]
        mock_batch.return_value = [[]]  # no matches
        mock_persons.return_value = {}

        result = asyncio.get_event_loop().run_until_complete(
            face_service.identify_faces_in_image(b"fake", "user-1")
        )

        assert result["faces_detected"] == 1
        face = result["faces"][0]
        assert face["match_status"] == "unknown"
        assert face["matches"] == []

    def test_multiple_faces_mixed(self, mock_deps):
        mock_detect, mock_batch, mock_persons = mock_deps

        mock_detect.return_value = [
            {"embedding": [0.1] * 512, "bbox": [0, 0, 50, 50], "det_score": 0.95},
            {"embedding": [0.2] * 512, "bbox": [60, 60, 120, 120], "det_score": 0.87},
        ]
        mock_batch.return_value = [
            [{"person_id": "p-1", "similarity_score": 0.91}],
            [],  # second face not matched
        ]
        mock_persons.return_value = {
            "p-1": {"id": "p-1", "name": "Bob"}
        }

        result = asyncio.get_event_loop().run_until_complete(
            face_service.identify_faces_in_image(b"fake", "user-1")
        )

        assert result["faces_detected"] == 2
        assert result["faces"][0]["match_status"] == "matched"
        assert result["faces"][1]["match_status"] == "unknown"

    def test_face_index_assigned(self, mock_deps):
        mock_detect, mock_batch, mock_persons = mock_deps

        mock_detect.return_value = [
            {"embedding": [0.1] * 512, "bbox": [0, 0, 50, 50], "det_score": 0.9},
            {"embedding": [0.2] * 512, "bbox": [60, 60, 120, 120], "det_score": 0.8},
        ]
        mock_batch.return_value = [[], []]
        mock_persons.return_value = {}

        result = asyncio.get_event_loop().run_until_complete(
            face_service.identify_faces_in_image(b"fake", "user-1")
        )

        assert result["faces"][0]["face_index"] == 0
        assert result["faces"][1]["face_index"] == 1

    def test_person_not_in_graph_filtered_out(self, mock_deps):
        """If vector_db returns a person_id that graph_db doesn't have, skip it."""
        mock_detect, mock_batch, mock_persons = mock_deps

        mock_detect.return_value = [
            {"embedding": [0.1] * 512, "bbox": [0, 0, 50, 50], "det_score": 0.9}
        ]
        mock_batch.return_value = [
            [{"person_id": "deleted-person", "similarity_score": 0.88}]
        ]
        mock_persons.return_value = {}  # person gone

        result = asyncio.get_event_loop().run_until_complete(
            face_service.identify_faces_in_image(b"fake", "user-1")
        )

        face = result["faces"][0]
        assert face["match_status"] == "unknown"
        assert face["matches"] == []


# ===================================================================
# get_face_app / init_face_model / is_model_ready
# ===================================================================
class TestModelLifecycle:
    @patch("app.face_service.FaceAnalysis")
    def test_get_face_app_creates_once(self, mock_fa):
        # Reset global state
        face_service._face_app = None
        mock_instance = MagicMock()
        mock_fa.return_value = mock_instance

        app1 = face_service.get_face_app()
        app2 = face_service.get_face_app()

        assert app1 is app2
        mock_fa.assert_called_once_with(name="buffalo_l", providers=["CPUExecutionProvider"])
        mock_instance.prepare.assert_called_once_with(ctx_id=0, det_size=(640, 640))

        # Cleanup
        face_service._face_app = None

    @patch("app.face_service.get_face_app")
    def test_init_face_model_sets_ready(self, mock_get):
        face_service._model_ready = False

        face_service.init_face_model()

        assert face_service.is_model_ready() is True
        mock_get.assert_called_once()

        # Cleanup
        face_service._model_ready = False

    def test_is_model_ready_default_false(self):
        face_service._model_ready = False
        assert face_service.is_model_ready() is False
