from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.base import BaseRepository
from app.models import Upload

class UploadRepository(BaseRepository[Upload]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Upload)
