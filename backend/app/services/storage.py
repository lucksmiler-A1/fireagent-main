from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.config import settings


class StorageService:
    def __init__(self):
        self.upload_dir = settings.UPLOAD_DIR
        self.ensure_upload_dir()

    def ensure_upload_dir(self):
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def get_file_extension(filename: str) -> str:
        return Path(filename or "").suffix.lower()

    def is_allowed_file(self, filename: str) -> bool:
        return self.get_file_extension(filename) in settings.ALLOWED_EXTENSIONS

    async def save_upload_file(self, upload_file: UploadFile, record_id: str) -> tuple[str, str]:
        if not upload_file.filename or not self.is_allowed_file(upload_file.filename):
            allowed = ", ".join(sorted(settings.ALLOWED_EXTENSIONS))
            raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {allowed}")

        file_content = await upload_file.read()
        if len(file_content) > settings.MAX_UPLOAD_SIZE:
            mb = settings.MAX_UPLOAD_SIZE / 1024 / 1024
            raise HTTPException(status_code=400, detail=f"File too large. Max: {mb:.1f}MB")

        ext = self.get_file_extension(upload_file.filename)
        filename = f"{record_id}{ext}"
        full_path = self.upload_dir / filename

        with open(full_path, "wb") as f:
            f.write(file_content)

        relative_path = f"uploads/{filename}"
        image_url = f"/static/{filename}"
        return relative_path, image_url

    def delete_file(self, relative_path: str) -> bool:
        try:
            file_path = settings.BASE_DIR / relative_path
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception:
            return False


storage_service = StorageService()

