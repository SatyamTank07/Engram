"""Tests for embedding_service.py — text embedding generation via OpenAI."""

from unittest.mock import MagicMock, patch

import pytest

from app import embedding_service


# ===================================================================
# build_person_text
# ===================================================================
class TestBuildPersonText:
    def test_name_only(self):
        result = embedding_service.build_person_text("Alice")
        assert result == "Alice"

    def test_name_with_aliases(self):
        result = embedding_service.build_person_text("Alice", aliases=["Ali", "A"])
        assert result == "Alice | Aliases: Ali, A"

    def test_name_with_bio(self):
        result = embedding_service.build_person_text("Alice", short_bio="Engineer at Google")
        assert result == "Alice | Bio: Engineer at Google"

    def test_name_with_contacts(self):
        result = embedding_service.build_person_text(
            "Alice", contacts={"email": "alice@test.com", "phone": "123"}
        )
        assert "Contacts:" in result
        assert "email: alice@test.com" in result
        assert "phone: 123" in result

    def test_all_fields(self):
        result = embedding_service.build_person_text(
            "Alice",
            aliases=["Ali"],
            short_bio="Engineer",
            contacts={"email": "alice@test.com"},
        )
        parts = result.split(" | ")
        assert parts[0] == "Alice"
        assert parts[1] == "Aliases: Ali"
        assert parts[2] == "Bio: Engineer"
        assert "email: alice@test.com" in parts[3]

    def test_empty_aliases_ignored(self):
        result = embedding_service.build_person_text("Alice", aliases=[])
        assert "Aliases" not in result

    def test_none_aliases_ignored(self):
        result = embedding_service.build_person_text("Alice", aliases=None)
        assert "Aliases" not in result

    def test_empty_bio_ignored(self):
        result = embedding_service.build_person_text("Alice", short_bio="")
        assert "Bio" not in result

    def test_none_bio_ignored(self):
        result = embedding_service.build_person_text("Alice", short_bio=None)
        assert "Bio" not in result

    def test_empty_contacts_ignored(self):
        result = embedding_service.build_person_text("Alice", contacts={})
        assert "Contacts" not in result

    def test_nested_contacts(self):
        result = embedding_service.build_person_text(
            "Alice",
            contacts={"social": {"twitter": "@alice", "github": "alice123"}},
        )
        assert "twitter: @alice" in result
        assert "github: alice123" in result


# ===================================================================
# generate_text_embedding
# ===================================================================
class TestGenerateTextEmbedding:
    def test_calls_openai_with_correct_params(self):
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1] * 1536

        mock_response = MagicMock()
        mock_response.data = [mock_embedding]

        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response

        with patch.object(embedding_service, "get_openai_client", return_value=mock_client):
            result = embedding_service.generate_text_embedding("test text")

        mock_client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-small",
            input="test text",
        )
        assert result == [0.1] * 1536

    def test_returns_correct_dimensions(self):
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.01] * 1536

        mock_response = MagicMock()
        mock_response.data = [mock_embedding]

        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response

        with patch.object(embedding_service, "get_openai_client", return_value=mock_client):
            result = embedding_service.generate_text_embedding("anything")

        assert len(result) == 1536

    def test_raises_on_api_error(self):
        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = RuntimeError("API error")

        with patch.object(embedding_service, "get_openai_client", return_value=mock_client):
            with pytest.raises(RuntimeError, match="API error"):
                embedding_service.generate_text_embedding("text")


# ===================================================================
# generate_person_embedding
# ===================================================================
class TestGeneratePersonEmbedding:
    def test_returns_text_and_embedding(self):
        fake_vec = [0.02] * 1536

        with patch.object(
            embedding_service, "generate_text_embedding", return_value=fake_vec
        ):
            text, embedding = embedding_service.generate_person_embedding(
                "Alice", aliases=["Ali"], short_bio="Engineer"
            )

        assert "Alice" in text
        assert "Ali" in text
        assert "Engineer" in text
        assert embedding == fake_vec

    def test_passes_all_fields_to_build(self):
        contacts = {"email": "a@b.com"}
        fake_vec = [0.0] * 1536

        with (
            patch.object(embedding_service, "build_person_text", return_value="built") as mock_build,
            patch.object(embedding_service, "generate_text_embedding", return_value=fake_vec),
        ):
            embedding_service.generate_person_embedding(
                "Alice", aliases=["A"], short_bio="Bio", contacts=contacts
            )

        mock_build.assert_called_once_with("Alice", ["A"], "Bio", contacts)


# ===================================================================
# get_openai_client
# ===================================================================
class TestGetOpenaiClient:
    def test_raises_when_no_api_key(self):
        # Reset singleton
        embedding_service._client = None
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            # Need to also clear the env var
            import os
            old = os.environ.pop("OPENAI_API_KEY", None)
            try:
                with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                    embedding_service.get_openai_client()
            finally:
                if old:
                    os.environ["OPENAI_API_KEY"] = old
                embedding_service._client = None
