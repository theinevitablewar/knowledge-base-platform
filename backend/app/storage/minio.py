import asyncio
import io
from datetime import timedelta

from minio import Minio

from app.core.config import Settings
from app.core.exceptions import StorageError


class MinioStorage:
    def __init__(self, settings: Settings) -> None:
        self.bucket = settings.minio_bucket
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    async def ensure_bucket(self) -> None:
        def ensure() -> None:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)

        try:
            await asyncio.to_thread(ensure)
        except Exception as exc:
            raise StorageError("MinIO bucket 初始化失败") from exc

    async def put_bytes(self, key: str, content: bytes, content_type: str) -> None:
        await self.ensure_bucket()
        try:
            await asyncio.to_thread(
                self.client.put_object,
                self.bucket,
                key,
                io.BytesIO(content),
                len(content),
                content_type=content_type,
            )
        except Exception as exc:
            raise StorageError("文件保存失败") from exc

    async def get_bytes(self, key: str) -> bytes:
        try:
            response = await asyncio.to_thread(self.client.get_object, self.bucket, key)
            try:
                return await asyncio.to_thread(response.read)
            finally:
                response.close()
                response.release_conn()
        except Exception as exc:
            raise StorageError("文件读取失败") from exc

    async def delete(self, key: str) -> None:
        try:
            await asyncio.to_thread(self.client.remove_object, self.bucket, key)
        except Exception as exc:
            raise StorageError("文件删除失败") from exc

    async def presigned_download(self, key: str) -> str:
        return await asyncio.to_thread(
            self.client.presigned_get_object, self.bucket, key, expires=timedelta(minutes=10)
        )
