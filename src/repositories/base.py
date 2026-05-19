from typing import (
    Any,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
)
from uuid import UUID

from sqlalchemy import (
    delete,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from src.models.base import BaseModel

ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseRepository(Generic[ModelType]):
    """
    Generic base repository providing CRUD operations for SQLAlchemy models.

    This repository implements the Repository pattern, abstracting database
    operations and providing a consistent interface for data access.

    Attributes:
        model_class: The SQLAlchemy model class this repository manages.
        session: The async database session.
    """

    def __init__(
        self,
        model_class: Type[ModelType],
        session: AsyncSession,
    ) -> None:
        """
        Initialize the repository with a model class and database session.

        Args:
            model_class: The SQLAlchemy model class.
            session: The async database session.

        Raises:
            TypeError: If model_class is not a subclass of BaseModel.
        """
        if not issubclass(model_class, BaseModel):
            raise TypeError(
                f"model_class must be a subclass of BaseModel, "
                f"got {model_class.__name__}"
            )
        self.model_class = model_class
        self.session = session

    async def create(self, **kwargs: Any) -> ModelType:
        """
        Create a new record in the database.

        Args:
            **kwargs: Field values for the new record.

        Returns:
            The newly created model instance.

        Raises:
            ValueError: If required fields are missing.
            Exception: If database operation fails.
        """
        try:
            instance = self.model_class(**kwargs)
            self.session.add(instance)
            await self.session.flush()
            await self.session.refresh(instance)
            return instance
        except Exception as e:
            await self.session.rollback()
            raise Exception(f"Failed to create {self.model_class.__name__}: {e}") from e

    async def get(
        self,
        id: Union[UUID, str, int],
    ) -> Optional[ModelType]:
        """
        Retrieve a single record by its primary key.

        Args:
            id: The primary key value of the record.

        Returns:
            The model instance if found, None otherwise.

        Raises:
            ValueError: If id is invalid.
            Exception: If database operation fails.
        """
        if not id:
            raise ValueError("id must be provided")

        try:
            stmt = select(self.model_class).where(
                self.model_class.id == id
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            raise Exception(
                f"Failed to get {self.model_class.__name__} with id {id}: {e}"
            ) from e

    async def get_multi(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        descending: bool = False,
    ) -> List[ModelType]:
        """
        Retrieve multiple records with pagination and optional filtering.

        Args:
            skip: Number of records to skip (offset).
            limit: Maximum number of records to return.
            filters: Dictionary of field-value pairs to filter by.
            order_by: Field name to order results by.
            descending: Whether to order in descending order.

        Returns:
            List of model instances.

        Raises:
            ValueError: If skip or limit are negative.
            Exception: If database operation fails.
        """
        if skip < 0:
            raise ValueError("skip must be non-negative")
        if limit < 1:
            raise ValueError("limit must be positive")

        try:
            stmt: Select = select(self.model_class)

            if filters:
                for field, value in filters.items():
                    if hasattr(self.model_class, field):
                        stmt = stmt.where(
                            getattr(self.model_class, field) == value
                        )

            if order_by and hasattr(self.model_class, order_by):
                order_column = getattr(self.model_class, order_by)
                stmt = stmt.order_by(
                    order_column.desc() if descending else order_column.asc()
                )

            stmt = stmt.offset(skip).limit(limit)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            raise Exception(
                f"Failed to get multiple {self.model_class.__name__}: {e}"
            ) from e

    async def update(
        self,
        id: Union[UUID, str, int],
        **kwargs: Any,
    ) -> Optional[ModelType]:
        """
        Update a record by its primary key.

        Args:
            id: The primary key value of the record to update.
            **kwargs: Field values to update.

        Returns:
            The updated model instance if found, None otherwise.

        Raises:
            ValueError: If id is invalid or no fields to update.
            Exception: If database operation fails.
        """
        if not id:
            raise ValueError("id must be provided")
        if not kwargs:
            raise ValueError("At least one field must be provided for update")

        try:
            stmt = (
                update(self.model_class)
                .where(self.model_class.id == id)
                .values(**kwargs)
                .returning(self.model_class)
            )
            result = await self.session.execute(stmt)
            await self.session.flush()
            updated_instance = result.scalar_one_or_none()
            if updated_instance:
                await self.session.refresh(updated_instance)
            return updated_instance
        except Exception as e:
            await self.session.rollback()
            raise Exception(
                f"Failed to update {self.model_class.__name__} with id {id}: {e}"
            ) from e

    async def delete(
        self,
        id: Union[UUID, str, int],
    ) -> bool:
        """
        Delete a record by its primary key.

        Args:
            id: The primary key value of the record to delete.

        Returns:
            True if the record was deleted, False if not found.

        Raises:
            ValueError: If id is invalid.
            Exception: If database operation fails.
        """
        if not id:
            raise ValueError("id must be provided")

        try:
            stmt = (
                delete(self.model_class)
                .where(self.model_class.id == id)
                .returning(self.model_class.id)
            )
            result = await self.session.execute(stmt)
            await self.session.flush()
            deleted_id = result.scalar_one_or_none()
            return deleted_id is not None
        except Exception as e:
            await self.session.rollback()
            raise Exception(
                f"Failed to delete {self.model_class.__name__} with id {id}: {e}"
            ) from e

    async def count(
        self,
        filters: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Count records with optional filtering.

        Args:
            filters: Dictionary of field-value pairs to filter by.

        Returns:
            The count of matching records.

        Raises:
            Exception: If database operation fails.
        """
        try:
            stmt = select(self.model_class)

            if filters:
                for field, value in filters.items():
                    if hasattr(self.model_class, field):
                        stmt = stmt.where(
                            getattr(self.model_class, field) == value
                        )

            result = await self.session.execute(stmt)
            return len(result.scalars().all())
        except Exception as e:
            raise Exception(
                f"Failed to count {self.model_class.__name__}: {e}"
            ) from e

    async def exists(
        self,
        id: Union[UUID, str, int],
    ) -> bool:
        """
        Check if a record exists by its primary key.

        Args:
            id: The primary key value to check.

        Returns:
            True if the record exists, False otherwise.

        Raises:
            ValueError: If id is invalid.
            Exception: If database operation fails.
        """
        if not id:
            raise ValueError("id must be provided")

        try:
            stmt = select(self.model_class.id).where(
                self.model_class.id == id
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none() is not None
        except Exception as e:
            raise Exception(
                f"Failed to check existence of {self.model_class.__name__} "
                f"with id {id}: {e}"
            ) from e

    async def bulk_create(
        self,
        records: List[Dict[str, Any]],
    ) -> List[ModelType]:
        """
        Create multiple records in a single operation.

        Args:
            records: List of dictionaries containing field values for each record.

        Returns:
            List of created model instances.

        Raises:
            ValueError: If records list is empty.
            Exception: If database operation fails.
        """
        if not records:
            raise ValueError("records list must not be empty")

        try:
            instances = [self.model_class(**record) for record in records]
            self.session.add_all(instances)
            await self.session.flush()
            for instance in instances:
                await self.session.refresh(instance)
            return instances
        except Exception as e:
            await self.session.rollback()
            raise Exception(
                f"Failed to bulk create {self.model_class.__name__}: {e}"
            ) from e

    async def bulk_delete(
        self,
        ids: List[Union[UUID, str, int]],
    ) -> int:
        """
        Delete multiple records by their primary keys.

        Args:
            ids: List of primary key values to delete.

        Returns:
            Number of records deleted.

        Raises:
            ValueError: If ids list is empty.
            Exception: If database operation fails.
        """
        if not ids:
            raise ValueError("ids list must not be empty")

        try:
            stmt = (
                delete(self.model_class)
                .where(self.model_class.id.in_(ids))
                .returning(self.model_class.id)
            )
            result = await self.session.execute(stmt)
            await self.session.flush()
            deleted_ids = result.scalars().all()
            return len(deleted_ids)
        except Exception as e:
            await self.session.rollback()
            raise Exception(
                f"Failed to bulk delete {self.model_class.__name__}: {e}"
            ) from e