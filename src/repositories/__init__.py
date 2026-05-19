"""
Repositories package initialization.

This module provides the base repository class and exports all repository
implementations for data access layer operations.
"""

from typing import (
    Any,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
    overload,
)
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.sql import Select

from src.models.base import BaseModel
from src.core.exceptions import (
    RepositoryError,
    EntityNotFoundError,
    DuplicateEntityError,
    DatabaseConnectionError,
)
from src.core.logging import get_logger

logger = get_logger(__name__)

ModelType = TypeVar("ModelType", bound=BaseModel)
CreateSchemaType = TypeVar("CreateSchemaType")
UpdateSchemaType = TypeVar("UpdateSchemaType")


@dataclass
class PaginationParams:
    """Pagination parameters for repository queries."""

    page: int = 1
    page_size: int = 20
    sort_by: Optional[str] = None
    sort_order: str = "asc"

    def __post_init__(self) -> None:
        """Validate pagination parameters."""
        if self.page < 1:
            raise ValueError("Page must be greater than 0")
        if self.page_size < 1 or self.page_size > 100:
            raise ValueError("Page size must be between 1 and 100")
        if self.sort_order not in ("asc", "desc"):
            raise ValueError("Sort order must be 'asc' or 'desc'")


@dataclass
class PaginatedResult:
    """Generic paginated result container."""

    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int

    def __post_init__(self) -> None:
        """Calculate total pages after initialization."""
        if self.page_size > 0:
            self.total_pages = (self.total + self.page_size - 1) // self.page_size
        else:
            self.total_pages = 0


class BaseRepository(ABC, Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    Abstract base repository providing CRUD operations.

    This class implements the Repository pattern with async support,
    providing standard database operations with proper error handling
    and logging.

    Type Parameters:
        ModelType: SQLAlchemy model class
        CreateSchemaType: Pydantic schema for creation
        UpdateSchemaType: Pydantic schema for updates
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session

        Raises:
            DatabaseConnectionError: If session is invalid
        """
        if session is None:
            raise DatabaseConnectionError("Database session cannot be None")
        self._session = session
        self._model_class: Type[ModelType] = self._get_model_class()

    @abstractmethod
    def _get_model_class(self) -> Type[ModelType]:
        """
        Get the SQLAlchemy model class for this repository.

        Returns:
            Model class type

        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError("Subclasses must implement _get_model_class")

    async def create(self, schema: CreateSchemaType) -> ModelType:
        """
        Create a new entity in the database.

        Args:
            schema: Creation schema with entity data

        Returns:
            Created model instance

        Raises:
            DuplicateEntityError: If entity with same unique fields exists
            RepositoryError: If database operation fails
        """
        try:
            entity_data = schema.model_dump() if hasattr(schema, "model_dump") else schema.dict()
            entity = self._model_class(**entity_data)
            self._session.add(entity)
            await self._session.flush()
            await self._session.refresh(entity)
            logger.info(f"Created {self._model_class.__name__} with id: {entity.id}")
            return entity
        except IntegrityError as exc:
            await self._session.rollback()
            error_msg = f"Duplicate {self._model_class.__name__} detected"
            logger.error(f"{error_msg}: {exc}")
            raise DuplicateEntityError(error_msg) from exc
        except SQLAlchemyError as exc:
            await self._session.rollback()
            error_msg = f"Failed to create {self._model_class.__name__}"
            logger.error(f"{error_msg}: {exc}")
            raise RepositoryError(error_msg) from exc

    async def get(self, entity_id: Union[UUID, str, int]) -> Optional[ModelType]:
        """
        Retrieve an entity by its ID.

        Args:
            entity_id: Unique identifier of the entity

        Returns:
            Model instance if found, None otherwise

        Raises:
            RepositoryError: If database operation fails
        """
        try:
            stmt = select(self._model_class).where(
                self._model_class.id == entity_id
            )
            result = await self._session.execute(stmt)
            entity = result.scalar_one_or_none()
            if entity:
                logger.debug(f"Retrieved {self._model_class.__name__} with id: {entity_id}")
            return entity
        except SQLAlchemyError as exc:
            error_msg = f"Failed to retrieve {self._model_class.__name__} with id: {entity_id}"
            logger.error(f"{error_msg}: {exc}")
            raise RepositoryError(error_msg) from exc

    async def get_or_raise(self, entity_id: Union[UUID, str, int]) -> ModelType:
        """
        Retrieve an entity by its ID or raise an exception.

        Args:
            entity_id: Unique identifier of the entity

        Returns:
            Model instance

        Raises:
            EntityNotFoundError: If entity not found
            RepositoryError: If database operation fails
        """
        entity = await self.get(entity_id)
        if entity is None:
            error_msg = f"{self._model_class.__name__} with id {entity_id} not found"
            logger.warning(error_msg)
            raise EntityNotFoundError(error_msg)
        return entity

    async def get_multi(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
    ) -> List[ModelType]:
        """
        Retrieve multiple entities with pagination and filtering.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Dictionary of field-value pairs for filtering
            sort_by: Field name to sort by
            sort_order: Sort direction ('asc' or 'desc')

        Returns:
            List of model instances

        Raises:
            RepositoryError: If database operation fails
        """
        try:
            stmt = select(self._model_class)

            if filters:
                stmt = self._apply_filters(stmt, filters)

            if sort_by and hasattr(self._model_class, sort_by):
                sort_column = getattr(self._model_class, sort_by)
                if sort_order == "desc":
                    stmt = stmt.order_by(sort_column.desc())
                else:
                    stmt = stmt.order_by(sort_column.asc())

            stmt = stmt.offset(skip).limit(limit)
            result = await self._session.execute(stmt)
            entities = list(result.scalars().all())
            logger.debug(f"Retrieved {len(entities)} {self._model_class.__name__} records")
            return entities
        except SQLAlchemyError as exc:
            error_msg = f"Failed to retrieve {self._model_class.__name__} records"
            logger.error(f"{error_msg}: {exc}")
            raise RepositoryError(error_msg) from exc

    async def get_paginated(
        self,
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None,
    ) -> PaginatedResult:
        """
        Retrieve paginated results with filtering.

        Args:
            pagination: Pagination parameters
            filters: Dictionary of field-value pairs for filtering

        Returns:
            PaginatedResult containing items and metadata

        Raises:
            RepositoryError: If database operation fails
        """
        try:
            skip = (pagination.page - 1) * pagination.page_size
            items = await self.get_multi(
                skip=skip,
                limit=pagination.page_size,
                filters=filters,
                sort_by=pagination.sort_by,
                sort_order=pagination.sort_order,
            )
            total = await self.count(filters=filters)
            return PaginatedResult(
                items=items,
                total=total,
                page=pagination.page,
                page_size=pagination.page_size,
                total_pages=0,
            )
        except SQLAlchemyError as exc:
            error_msg = f"Failed to retrieve paginated {self._model_class.__name__} records"
            logger.error(f"{error_msg}: {exc}")
            raise RepositoryError(error_msg) from exc

    async def update(
        self,
        entity_id: Union[UUID, str, int],
        schema: UpdateSchemaType,
    ) -> ModelType:
        """
        Update an existing entity.

        Args:
            entity_id: Unique identifier of the entity to update
            schema: Update schema with new data

        Returns:
            Updated model instance

        Raises:
            EntityNotFoundError: If entity not found
            DuplicateEntityError: If update violates unique constraints
            RepositoryError: If database operation fails
        """
        try:
            entity = await self.get_or_raise(entity_id)
            update_data = schema.model_dump(exclude_unset=True) if hasattr(schema, "model_dump") else schema.dict(exclude_unset=True)
            
            for field, value in update_data.items():
                setattr(entity, field, value)
            
            entity.updated_at = datetime.utcnow()
            await self._session.flush()
            await self._session.refresh(entity)
            logger.info(f"Updated {self._model_class.__name__} with id: {entity_id}")
            return entity
        except EntityNotFoundError:
            raise
        except IntegrityError as exc:
            await self._session.rollback()
            error_msg = f"Duplicate {self._model_class.__name__} detected during update"
            logger.error(f"{error_msg}: {exc}")
            raise DuplicateEntityError(error_msg) from exc
        except SQLAlchemyError as exc:
            await self._session.rollback()
            error_msg = f"Failed to update {self._model_class.__name__} with id: {entity_id}"
            logger.error(f"{error_msg}: {exc}")
            raise RepositoryError(error_msg) from exc

    async def delete(self, entity_id: Union[UUID, str, int]) -> bool:
        """
        Delete an entity by its ID.

        Args:
            entity_id: Unique identifier of the entity to delete

        Returns:
            True if deleted, False if not found

        Raises:
            RepositoryError: If database operation fails
        """
        try:
            entity = await self.get(entity_id)
            if entity is None:
                logger.warning(f"{self._model_class.__name__} with id {entity_id} not found for deletion")
                return False
            
            await self._session.delete(entity)
            await self._session.flush()
            logger.info(f"Deleted {self._model_class.__name__} with id: {entity_id}")
            return True
        except SQLAlchemyError as exc:
            await self._session.rollback()
            error_msg = f"Failed to delete {self._model_class.__name__} with id: {entity_id}"
            logger.error(f"{error_msg}: {exc}")
            raise RepositoryError(error_msg) from exc

    async def soft_delete(self, entity_id: Union[UUID, str, int]) -> bool:
        """
        Soft delete an entity by setting its deleted_at timestamp.

        Args:
            entity_id: Unique identifier of the entity to soft delete

        Returns:
            True if soft deleted, False if not found

        Raises:
            RepositoryError: If database operation fails
            AttributeError: If model doesn't support soft delete
        """
        try:
            entity = await self.get(entity_id)
            if entity is None:
                logger.warning(f"{self._model_class.__name__} with id {entity_id} not found for soft deletion")
                return False
            
            if not hasattr(entity, "deleted_at"):
                raise AttributeError(f"{self._model_class.__name__} does not support soft delete")
            
            entity.deleted_at = datetime.utcnow()
            await self._session.flush()
            logger.info(f"Soft deleted {self._model_class.__name__} with id: {entity_id}")
            return True
        except SQLAlchemyError as exc:
            await self._session.rollback()
            error_msg = f"Failed to soft delete {self._model_class.__name__} with id: {entity_id}"
            logger.error(f"{error_msg}: {exc}")
            raise RepositoryError(error_msg) from exc

    async def count(
        self,
        filters: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Count entities matching optional filters.

        Args:
            filters: Dictionary of field-value pairs for filtering

        Returns:
            Count of matching entities

        Raises:
            RepositoryError: If database operation fails
        """
        try:
            stmt = select(func.count()).select_from(self._model_class)
            if filters:
                stmt = self._apply_filters(stmt, filters)
            result = await self._session.execute(stmt)
            count = result.scalar() or 0
            logger.debug(f"Counted {count} {self._model_class.__name__} records")
            return count
        except SQLAlchemyError as exc:
            error_msg = f"Failed to count {self._model_class.__name__} records"
            logger.error(f"{error_msg}: {exc}")
            raise RepositoryError(error_msg) from exc

    async def exists(
        self,
        filters: Dict[str, Any],
    ) -> bool:
        """
        Check if any entity matches the given filters.

        Args:
            filters: Dictionary of field-value pairs for filtering

        Returns:
            True if at least one entity matches, False otherwise

        Raises:
            RepositoryError: If database operation fails
        """
        try:
            count = await self.count(filters=filters)
            return count > 0
        except SQLAlchemyError as exc:
            error_msg = f"Failed to check existence of {self._model_class.__name__}"
            logger.error(f"{error_msg}: {exc}")
            raise RepositoryError(error_msg) from exc

    async def bulk_create(
        self,
        schemas: List[CreateSchemaType],
    ) -> List[ModelType]:
        """
        Create multiple entities in a single transaction.

        Args:
            schemas: List of creation schemas

        Returns:
            List of created model instances

        Raises:
            DuplicateEntityError: If any entity violates unique constraints
            RepositoryError: If database operation fails
        """
        try:
            entities = []
            for schema in schemas:
                entity_data = schema.model_dump() if hasattr(schema, "model_dump") else schema.dict()
                entity = self._model_class(**entity_data)
                self._session.add(entity)
                entities.append(entity)
            
            await self._session.flush()
            for entity in entities:
                await self._session.refresh(entity)
            
            logger.info(f"Bulk created {len(entities)} {self._model_class.__name__} records")
            return entities
        except IntegrityError as exc:
            await self._session.rollback()
            error_msg = f"Duplicate {self._model_class.__name__} detected during bulk create"
            logger.error(f"{error_msg}: {exc}")
            raise DuplicateEntityError(error_msg) from exc
        except SQLAlchemyError as exc:
            await self._session.rollback()
            error_msg = f"Failed to bulk create {self._model_class.__name__} records"
            logger.error(f"{error_msg}: {exc}")
            raise RepositoryError(error_msg) from exc

    async def bulk_update(
        self,
        updates: List[Dict[str, Any]],
    ) -> int:
        """
        Update multiple entities in a single transaction.

        Args:
            updates: List of dictionaries with 'id' and update fields

        Returns:
            Number of updated records

        Raises:
            RepositoryError: If database operation fails
        """
        try:
            updated_count = 0
            for update_data in updates:
                entity_id = update_data.pop("id", None)
                if entity_id is None:
                    continue
                
                stmt = (
                    update(self._model_class)
                    .where(self._model_class.id == entity_id)
                    .values(**update_data, updated_at=datetime.utcnow())
                )
                result = await self._session.execute(stmt)
                updated_count += result.rowcount
            
            await self._session.flush()
            logger.info(f"Bulk updated {updated_count} {self._model_class.__name__} records")
            return updated_count
        except SQLAlchemyError as exc:
            await self._session.rollback()
            error_msg = f"Failed to bulk update {self._model_class.__name__} records"
            logger.error(f"{error_msg}: {exc}")
            raise RepositoryError(error_msg) from exc

    async def bulk_delete(
        self,
        entity_ids: List[Union[UUID, str, int]],
    ) -> int:
        """
        Delete multiple entities by their IDs.

        Args:
            entity_ids: List of unique identifiers

        Returns:
            Number of deleted records

        Raises:
            RepositoryError: If database operation fails
        """
        try:
            stmt = delete(self._model_class).where(
                self._model_class.id.in_(entity_ids)
            )
            result = await self._session.execute(stmt)
            await self._session.flush()
            deleted_count = result.rowcount
            logger.info(f"Bulk deleted {deleted_count} {self._model_class.__name__} records")
            return deleted_count
        except SQLAlchemyError as exc:
            await self._session.rollback()
            error_msg = f"Failed to bulk delete {self._model_class.__name__} records"
            logger.error(f"{error_msg}: {exc}")
            raise RepositoryError(error_msg) from exc

    def _apply_filters(
        self,
        stmt: Select,
        filters: Dict[str, Any],
    ) -> Select:
        """
        Apply filters to a select statement.

        Args:
            stmt: SQLAlchemy Select statement
            filters: Dictionary of field-value pairs

        Returns:
            Modified Select statement with filters applied
        """
        for field, value in filters.items():
            if hasattr(self._model_class, field):
                column = getattr(self._model_class, field)
                if isinstance(value, (list, tuple)):
                    stmt = stmt.where(column.in_(value))
                elif value is None:
                    stmt = stmt.where(column.is_(None))
                else:
                    stmt = stmt.where(column == value)
        return stmt

    async def __aenter__(self) -> "BaseRepository":
        """Enter async context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> None:
        """Exit async context manager and close session."""
        if exc_type is not None:
            await self._session.rollback()
        await self._session.close()


# Export all repository classes and utilities
__all__ = [
    "BaseRepository",
    "PaginationParams",
    "PaginatedResult",
    "ModelType",
    "CreateSchemaType",
    "UpdateSchemaType",
]