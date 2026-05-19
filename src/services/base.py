from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from uuid import UUID

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from src.models.base import Base
from src.schemas.base import BaseCreateSchema, BaseUpdateSchema
from src.core.exceptions import (
    NotFoundException,
    DuplicateException,
    ServiceException,
)
from src.core.logging import get_logger

logger = get_logger(__name__)

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseCreateSchema)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseUpdateSchema)


class BaseService(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    Base service class providing CRUD operations for all models.
    
    This service implements the repository pattern with async SQLAlchemy sessions,
    providing a consistent interface for data access operations across the application.
    
    Attributes:
        model: The SQLAlchemy model class
        db_session: Async database session
    """

    def __init__(
        self,
        model: Type[ModelType],
        db_session: AsyncSession,
    ) -> None:
        """
        Initialize the base service.
        
        Args:
            model: SQLAlchemy model class
            db_session: Async database session
        """
        self.model = model
        self.db_session = db_session

    async def create(
        self,
        schema: CreateSchemaType,
        commit: bool = True,
        refresh: bool = True,
    ) -> ModelType:
        """
        Create a new record in the database.
        
        Args:
            schema: Pydantic schema with creation data
            commit: Whether to commit the transaction
            refresh: Whether to refresh the instance after creation
            
        Returns:
            Created model instance
            
        Raises:
            DuplicateException: If a record with unique constraints already exists
            ServiceException: If creation fails for other reasons
        """
        try:
            instance = self.model(**schema.model_dump(exclude_unset=True))
            self.db_session.add(instance)
            
            if commit:
                await self.db_session.commit()
                if refresh:
                    await self.db_session.refresh(instance)
            
            logger.info(
                "Created %s with id: %s",
                self.model.__name__,
                getattr(instance, "id", None),
            )
            return instance
            
        except Exception as exc:
            await self.db_session.rollback()
            error_msg = f"Failed to create {self.model.__name__}: {str(exc)}"
            logger.error(error_msg, exc_info=True)
            
            if "duplicate key" in str(exc).lower() or "unique constraint" in str(exc).lower():
                raise DuplicateException(
                    detail=f"{self.model.__name__} with given data already exists"
                ) from exc
            
            raise ServiceException(detail=error_msg) from exc

    async def get(
        self,
        id: Union[UUID, str, int],
        raise_exception: bool = True,
    ) -> Optional[ModelType]:
        """
        Retrieve a record by its primary key.
        
        Args:
            id: Primary key value
            raise_exception: Whether to raise NotFoundException if not found
            
        Returns:
            Model instance if found, None otherwise
            
        Raises:
            NotFoundException: If record not found and raise_exception is True
        """
        try:
            query = select(self.model).where(self.model.id == id)
            result = await self.db_session.execute(query)
            instance = result.scalar_one_or_none()
            
            if instance is None and raise_exception:
                raise NotFoundException(
                    detail=f"{self.model.__name__} with id {id} not found"
                )
            
            return instance
            
        except NotFoundException:
            raise
        except Exception as exc:
            error_msg = f"Failed to retrieve {self.model.__name__} with id {id}: {str(exc)}"
            logger.error(error_msg, exc_info=True)
            raise ServiceException(detail=error_msg) from exc

    async def get_multi(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        ascending: bool = True,
    ) -> List[ModelType]:
        """
        Retrieve multiple records with pagination and filtering.
        
        Args:
            skip: Number of records to skip (offset)
            limit: Maximum number of records to return
            filters: Dictionary of field-value pairs to filter by
            order_by: Field name to order results by
            ascending: Whether to sort in ascending order
            
        Returns:
            List of model instances
        """
        try:
            query = select(self.model)
            
            # Apply filters
            if filters:
                for field, value in filters.items():
                    if hasattr(self.model, field):
                        query = query.where(getattr(self.model, field) == value)
            
            # Apply ordering
            if order_by and hasattr(self.model, order_by):
                order_column = getattr(self.model, order_by)
                query = query.order_by(
                    order_column.asc() if ascending else order_column.desc()
                )
            
            # Apply pagination
            query = query.offset(skip).limit(limit)
            
            result = await self.db_session.execute(query)
            instances = list(result.scalars().all())
            
            logger.debug(
                "Retrieved %d %s records (skip=%d, limit=%d)",
                len(instances),
                self.model.__name__,
                skip,
                limit,
            )
            
            return instances
            
        except Exception as exc:
            error_msg = f"Failed to retrieve {self.model.__name__} records: {str(exc)}"
            logger.error(error_msg, exc_info=True)
            raise ServiceException(detail=error_msg) from exc

    async def update(
        self,
        id: Union[UUID, str, int],
        schema: UpdateSchemaType,
        commit: bool = True,
        refresh: bool = True,
    ) -> ModelType:
        """
        Update a record by its primary key.
        
        Args:
            id: Primary key value
            schema: Pydantic schema with update data
            commit: Whether to commit the transaction
            refresh: Whether to refresh the instance after update
            
        Returns:
            Updated model instance
            
        Raises:
            NotFoundException: If record not found
            ServiceException: If update fails
        """
        try:
            # Get existing instance
            instance = await self.get(id=id, raise_exception=True)
            
            # Update only provided fields
            update_data = schema.model_dump(exclude_unset=True)
            if not update_data:
                logger.warning("No fields to update for %s with id %s", self.model.__name__, id)
                return instance
            
            # Apply updates
            for field, value in update_data.items():
                setattr(instance, field, value)
            
            if commit:
                await self.db_session.commit()
                if refresh:
                    await self.db_session.refresh(instance)
            
            logger.info(
                "Updated %s with id: %s",
                self.model.__name__,
                id,
            )
            return instance
            
        except NotFoundException:
            raise
        except Exception as exc:
            await self.db_session.rollback()
            error_msg = f"Failed to update {self.model.__name__} with id {id}: {str(exc)}"
            logger.error(error_msg, exc_info=True)
            raise ServiceException(detail=error_msg) from exc

    async def delete(
        self,
        id: Union[UUID, str, int],
        soft_delete: bool = False,
        commit: bool = True,
    ) -> bool:
        """
        Delete a record by its primary key.
        
        Args:
            id: Primary key value
            soft_delete: Whether to perform a soft delete (set is_active=False)
            commit: Whether to commit the transaction
            
        Returns:
            True if deletion was successful
            
        Raises:
            NotFoundException: If record not found
            ServiceException: If deletion fails
        """
        try:
            instance = await self.get(id=id, raise_exception=True)
            
            if soft_delete and hasattr(instance, "is_active"):
                instance.is_active = False
                if commit:
                    await self.db_session.commit()
                logger.info(
                    "Soft deleted %s with id: %s",
                    self.model.__name__,
                    id,
                )
            else:
                await self.db_session.delete(instance)
                if commit:
                    await self.db_session.commit()
                logger.info(
                    "Hard deleted %s with id: %s",
                    self.model.__name__,
                    id,
                )
            
            return True
            
        except NotFoundException:
            raise
        except Exception as exc:
            await self.db_session.rollback()
            error_msg = f"Failed to delete {self.model.__name__} with id {id}: {str(exc)}"
            logger.error(error_msg, exc_info=True)
            raise ServiceException(detail=error_msg) from exc

    async def count(
        self,
        filters: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Count records with optional filters.
        
        Args:
            filters: Dictionary of field-value pairs to filter by
            
        Returns:
            Number of matching records
        """
        try:
            query = select(func.count()).select_from(self.model)
            
            if filters:
                for field, value in filters.items():
                    if hasattr(self.model, field):
                        query = query.where(getattr(self.model, field) == value)
            
            result = await self.db_session.execute(query)
            count = result.scalar()
            
            logger.debug("Counted %d %s records", count, self.model.__name__)
            return count or 0
            
        except Exception as exc:
            error_msg = f"Failed to count {self.model.__name__} records: {str(exc)}"
            logger.error(error_msg, exc_info=True)
            raise ServiceException(detail=error_msg) from exc

    async def exists(
        self,
        filters: Dict[str, Any],
    ) -> bool:
        """
        Check if records exist matching the given filters.
        
        Args:
            filters: Dictionary of field-value pairs to filter by
            
        Returns:
            True if matching records exist, False otherwise
        """
        try:
            count = await self.count(filters=filters)
            return count > 0
            
        except Exception as exc:
            error_msg = f"Failed to check existence of {self.model.__name__}: {str(exc)}"
            logger.error(error_msg, exc_info=True)
            raise ServiceException(detail=error_msg) from exc

    async def bulk_create(
        self,
        schemas: List[CreateSchemaType],
        commit: bool = True,
    ) -> List[ModelType]:
        """
        Create multiple records in a single transaction.
        
        Args:
            schemas: List of Pydantic schemas with creation data
            commit: Whether to commit the transaction
            
        Returns:
            List of created model instances
            
        Raises:
            ServiceException: If bulk creation fails
        """
        if not schemas:
            return []
        
        try:
            instances = [
                self.model(**schema.model_dump(exclude_unset=True))
                for schema in schemas
            ]
            
            self.db_session.add_all(instances)
            
            if commit:
                await self.db_session.commit()
                for instance in instances:
                    await self.db_session.refresh(instance)
            
            logger.info(
                "Bulk created %d %s records",
                len(instances),
                self.model.__name__,
            )
            return instances
            
        except Exception as exc:
            await self.db_session.rollback()
            error_msg = f"Failed to bulk create {self.model.__name__} records: {str(exc)}"
            logger.error(error_msg, exc_info=True)
            raise ServiceException(detail=error_msg) from exc

    async def get_or_create(
        self,
        defaults: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> tuple[ModelType, bool]:
        """
        Get an existing record or create a new one.
        
        Args:
            defaults: Default values for creation if record doesn't exist
            **kwargs: Filter criteria to find existing record
            
        Returns:
            Tuple of (model instance, whether it was created)
        """
        try:
            instance = await self.get_multi(filters=kwargs, limit=1)
            
            if instance:
                return instance[0], False
            
            # Create new instance with defaults and kwargs
            create_data = {**kwargs, **(defaults or {})}
            schema = CreateSchemaType(**create_data)
            instance = await self.create(schema=schema)
            
            return instance, True
            
        except Exception as exc:
            error_msg = f"Failed to get or create {self.model.__name__}: {str(exc)}"
            logger.error(error_msg, exc_info=True)
            raise ServiceException(detail=error_msg) from exc