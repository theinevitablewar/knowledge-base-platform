from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.rag.embeddings import embedding_provider
from app.rag.embeddings.providers import EmbeddingsAdapter
from app.rag.vectorstores import QdrantVectorStoreProvider, VectorStoreProvider
from app.storage import MinioStorage


def settings_provider() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(settings_provider)]


def storage_provider(settings: SettingsDep) -> MinioStorage:
    return MinioStorage(settings)


def embeddings_provider(settings: SettingsDep) -> EmbeddingsAdapter:
    return embedding_provider(settings)


def vector_provider(settings: SettingsDep) -> VectorStoreProvider:
    return QdrantVectorStoreProvider(settings)


StorageDep = Annotated[MinioStorage, Depends(storage_provider)]
EmbeddingsDep = Annotated[EmbeddingsAdapter, Depends(embeddings_provider)]
VectorDep = Annotated[VectorStoreProvider, Depends(vector_provider)]
