from app.core.config import Settings
from app.rag.embeddings.providers import OpenAIEmbeddingsAdapter


def test_openai_compatible_embeddings_send_text_without_client_tokenization():
    settings = Settings(ai_mock_mode=False, openai_api_key="test-key")

    adapter = OpenAIEmbeddingsAdapter(settings, dimension=1024)

    assert adapter.client.check_embedding_ctx_length is False
    assert adapter.client._invocation_params["encoding_format"] == "float"
