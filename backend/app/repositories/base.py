from typing import Generic, TypeVar, Type, Optional, List, Any
from sqlalchemy import select, insert, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

T = TypeVar("T")

class BaseRepository(Generic[T]):
    def __init__(self, session: AsyncSession, model: Type[T]):
        self.session = session
        self.model = model

    async def get_all(self) -> List[T]:
        stmt = select(self.model)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, id: Any) -> Optional[T]:
        result = await self.session.get(self.model, id)
        return result

    async def create(self, **kwargs) -> T:
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, id: Any, **kwargs) -> Optional[T]:
        pk_filter = self._build_pk_filter(id)
        stmt = (
            update(self.model)
            .where(*pk_filter)
            .values(**kwargs)
            .returning(self.model)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def delete(self, id: Any) -> bool:
        pk_filter = self._build_pk_filter(id)
        stmt = delete(self.model).where(*pk_filter)
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    def _build_pk_filter(self, id_value: Any):
        pk_cols = self.model.__mapper__.primary_key
        if len(pk_cols) == 1:
            return (pk_cols[0] == id_value,)
        if isinstance(id_value, dict):
            return tuple(getattr(self.model, key) == value for key, value in id_value.items())
        if isinstance(id_value, (tuple, list)) and len(id_value) == len(pk_cols):
            return tuple(col == value for col, value in zip(pk_cols, id_value))
        raise ValueError("Composite primary key requires tuple/list or dict identifier.")
