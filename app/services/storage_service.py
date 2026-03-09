import asyncio
from pathlib import Path
from uuid import uuid4

from supabase import Client, create_client

from app.core.config import settings


class StorageService:
    def __init__(self) -> None:
        self._client: Client | None = None
        self._bucket_ready = False

    def _get_client(self) -> Client:
        if self._client is None:
            self._client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_ROLE_KEY,
            )
        return self._client

    def _ensure_bucket_sync(self) -> None:
        if self._bucket_ready:
            return
        client = self._get_client()
        try:
            client.storage.create_bucket(settings.SUPABASE_CV_BUCKET)
        except Exception:
            pass
        self._bucket_ready = True

    def _build_candidate_cv_path(self, user_id: int, candidate_id: int, filename: str | None) -> str:
        suffix = Path(filename or "cv.txt").suffix or ".txt"
        return f"user_{user_id}/candidate_{candidate_id}/{uuid4().hex}{suffix.lower()}"

    async def upload_candidate_cv(
        self,
        user_id: int,
        candidate_id: int,
        filename: str | None,
        content: bytes,
        content_type: str | None,
    ) -> str:
        return await asyncio.to_thread(
            self._upload_candidate_cv_sync,
            user_id,
            candidate_id,
            filename,
            content,
            content_type,
        )

    def _upload_candidate_cv_sync(
        self,
        user_id: int,
        candidate_id: int,
        filename: str | None,
        content: bytes,
        content_type: str | None,
    ) -> str:
        self._ensure_bucket_sync()
        path = self._build_candidate_cv_path(user_id, candidate_id, filename)
        self._get_client().storage.from_(settings.SUPABASE_CV_BUCKET).upload(
            path,
            content,
            {"content-type": content_type or "application/octet-stream"},
        )
        return path

    async def download_cv(self, path: str) -> bytes:
        return await asyncio.to_thread(self._download_cv_sync, path)

    def _download_cv_sync(self, path: str) -> bytes:
        return self._get_client().storage.from_(settings.SUPABASE_CV_BUCKET).download(path)

    async def delete_cv(self, path: str) -> None:
        await asyncio.to_thread(self._delete_cv_sync, path)

    def _delete_cv_sync(self, path: str) -> None:
        self._get_client().storage.from_(settings.SUPABASE_CV_BUCKET).remove([path])

    async def create_signed_cv_url(self, path: str) -> str:
        return await asyncio.to_thread(self._create_signed_cv_url_sync, path)

    def _create_signed_cv_url_sync(self, path: str) -> str:
        data = self._get_client().storage.from_(settings.SUPABASE_CV_BUCKET).create_signed_url(
            path,
            settings.CV_SIGNED_URL_EXPIRE_SECONDS,
        )
        return data["signedURL"]


storage_service = StorageService()
