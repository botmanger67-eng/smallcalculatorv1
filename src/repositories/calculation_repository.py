"""Repository for managing calculation data persistence."""

from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import logging
from pathlib import Path
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import sqlite3

logger = logging.getLogger(__name__)


@dataclass
class CalculationRecord:
    """Data class representing a calculation record."""
    
    id: Optional[int]
    expression: str
    result: float
    operation_type: str
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None
    duration_ms: Optional[float] = None
    status: str = "completed"
    error_message: Optional[str] = None


class CalculationRepositoryError(Exception):
    """Base exception for calculation repository errors."""
    pass


class DatabaseConnectionError(CalculationRepositoryError):
    """Exception raised when database connection fails."""
    pass


class RecordNotFoundError(CalculationRepositoryError):
    """Exception raised when a calculation record is not found."""
    pass


class CalculationRepository:
    """Repository for managing calculation data persistence.
    
    This class provides methods for CRUD operations on calculation records
    stored in a SQLite database.
    """
    
    def __init__(self, db_path: str = "calculations.db") -> None:
        """Initialize the repository with database path.
        
        Args:
            db_path: Path to the SQLite database file.
            
        Raises:
            DatabaseConnectionError: If database initialization fails.
        """
        self._db_path = Path(db_path)
        self._initialize_database()
        logger.info(f"Calculation repository initialized with database: {db_path}")
    
    def _initialize_database(self) -> None:
        """Create the database and tables if they don't exist.
        
        Raises:
            DatabaseConnectionError: If database creation fails.
        """
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS calculations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        expression TEXT NOT NULL,
                        result REAL NOT NULL,
                        operation_type TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        metadata TEXT,
                        user_id TEXT,
                        duration_ms REAL,
                        status TEXT DEFAULT 'completed',
                        error_message TEXT
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_calculations_created_at 
                    ON calculations(created_at)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_calculations_user_id 
                    ON calculations(user_id)
                """)
                connection.commit()
                logger.debug("Database tables created successfully")
        except sqlite3.Error as error:
            raise DatabaseConnectionError(
                f"Failed to initialize database: {error}"
            ) from error
    
    @contextmanager
    def _get_connection(self) -> sqlite3.Connection:
        """Context manager for database connections.
        
        Yields:
            sqlite3.Connection: Database connection object.
            
        Raises:
            DatabaseConnectionError: If connection fails.
        """
        connection = None
        try:
            connection = sqlite3.connect(str(self._db_path))
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            yield connection
        except sqlite3.Error as error:
            raise DatabaseConnectionError(
                f"Database connection failed: {error}"
            ) from error
        finally:
            if connection:
                connection.close()
    
    def _serialize_record(self, record: CalculationRecord) -> Dict[str, Any]:
        """Serialize a CalculationRecord to a dictionary.
        
        Args:
            record: The calculation record to serialize.
            
        Returns:
            Dict[str, Any]: Serialized record data.
        """
        data = asdict(record)
        data["created_at"] = record.created_at.isoformat()
        if data["metadata"] is not None:
            data["metadata"] = json.dumps(data["metadata"])
        return data
    
    def _deserialize_record(self, row: sqlite3.Row) -> CalculationRecord:
        """Deserialize a database row to a CalculationRecord.
        
        Args:
            row: Database row to deserialize.
            
        Returns:
            CalculationRecord: Deserialized calculation record.
        """
        data = dict(row)
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data["metadata"] is not None:
            data["metadata"] = json.loads(data["metadata"])
        return CalculationRecord(**data)
    
    def save(self, record: CalculationRecord) -> CalculationRecord:
        """Save a new calculation record to the database.
        
        Args:
            record: The calculation record to save.
            
        Returns:
            CalculationRecord: The saved record with generated ID.
            
        Raises:
            DatabaseConnectionError: If database operation fails.
        """
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                data = self._serialize_record(record)
                
                columns = [key for key in data.keys() if key != "id"]
                placeholders = ", ".join(["?" for _ in columns])
                column_names = ", ".join(columns)
                
                values = [data[column] for column in columns]
                
                cursor.execute(
                    f"INSERT INTO calculations ({column_names}) VALUES ({placeholders})",
                    values
                )
                connection.commit()
                
                record.id = cursor.lastrowid
                logger.info(f"Calculation record saved with ID: {record.id}")
                return record
                
        except sqlite3.Error as error:
            raise DatabaseConnectionError(
                f"Failed to save calculation record: {error}"
            ) from error
    
    def get_by_id(self, record_id: int) -> Optional[CalculationRecord]:
        """Retrieve a calculation record by its ID.
        
        Args:
            record_id: The ID of the record to retrieve.
            
        Returns:
            Optional[CalculationRecord]: The found record or None.
            
        Raises:
            DatabaseConnectionError: If database operation fails.
        """
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    "SELECT * FROM calculations WHERE id = ?",
                    (record_id,)
                )
                row = cursor.fetchone()
                
                if row is None:
                    logger.debug(f"Calculation record not found with ID: {record_id}")
                    return None
                
                return self._deserialize_record(row)
                
        except sqlite3.Error as error:
            raise DatabaseConnectionError(
                f"Failed to retrieve calculation record: {error}"
            ) from error
    
    def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
        user_id: Optional[str] = None,
        operation_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[CalculationRecord]:
        """Retrieve calculation records with optional filtering.
        
        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip.
            user_id: Filter by user ID.
            operation_type: Filter by operation type.
            start_date: Filter records created after this date.
            end_date: Filter records created before this date.
            
        Returns:
            List[CalculationRecord]: List of matching calculation records.
            
        Raises:
            DatabaseConnectionError: If database operation fails.
        """
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                
                query = "SELECT * FROM calculations WHERE 1=1"
                params = []
                
                if user_id is not None:
                    query += " AND user_id = ?"
                    params.append(user_id)
                
                if operation_type is not None:
                    query += " AND operation_type = ?"
                    params.append(operation_type)
                
                if start_date is not None:
                    query += " AND created_at >= ?"
                    params.append(start_date.isoformat())
                
                if end_date is not None:
                    query += " AND created_at <= ?"
                    params.append(end_date.isoformat())
                
                query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                return [self._deserialize_record(row) for row in rows]
                
        except sqlite3.Error as error:
            raise DatabaseConnectionError(
                f"Failed to retrieve calculation records: {error}"
            ) from error
    
    def update(self, record: CalculationRecord) -> CalculationRecord:
        """Update an existing calculation record.
        
        Args:
            record: The calculation record to update.
            
        Returns:
            CalculationRecord: The updated record.
            
        Raises:
            RecordNotFoundError: If the record doesn't exist.
            DatabaseConnectionError: If database operation fails.
        """
        if record.id is None:
            raise RecordNotFoundError("Cannot update record without ID")
        
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                data = self._serialize_record(record)
                
                update_columns = [key for key in data.keys() if key != "id"]
                set_clause = ", ".join([f"{col} = ?" for col in update_columns])
                values = [data[col] for col in update_columns]
                values.append(record.id)
                
                cursor.execute(
                    f"UPDATE calculations SET {set_clause} WHERE id = ?",
                    values
                )
                
                if cursor.rowcount == 0:
                    raise RecordNotFoundError(
                        f"Calculation record not found with ID: {record.id}"
                    )
                
                connection.commit()
                logger.info(f"Calculation record updated with ID: {record.id}")
                return record
                
        except sqlite3.Error as error:
            raise DatabaseConnectionError(
                f"Failed to update calculation record: {error}"
            ) from error
    
    def delete(self, record_id: int) -> bool:
        """Delete a calculation record by its ID.
        
        Args:
            record_id: The ID of the record to delete.
            
        Returns:
            bool: True if the record was deleted, False otherwise.
            
        Raises:
            DatabaseConnectionError: If database operation fails.
        """
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    "DELETE FROM calculations WHERE id = ?",
                    (record_id,)
                )
                connection.commit()
                
                deleted = cursor.rowcount > 0
                if deleted:
                    logger.info(f"Calculation record deleted with ID: {record_id}")
                else:
                    logger.debug(f"Calculation record not found for deletion with ID: {record_id}")
                
                return deleted
                
        except sqlite3.Error as error:
            raise DatabaseConnectionError(
                f"Failed to delete calculation record: {error}"
            ) from error
    
    def count(
        self,
        user_id: Optional[str] = None,
        operation_type: Optional[str] = None
    ) -> int:
        """Count calculation records with optional filtering.
        
        Args:
            user_id: Filter by user ID.
            operation_type: Filter by operation type.
            
        Returns:
            int: Number of matching records.
            
        Raises:
            DatabaseConnectionError: If database operation fails.
        """
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                
                query = "SELECT COUNT(*) FROM calculations WHERE 1=1"
                params = []
                
                if user_id is not None:
                    query += " AND user_id = ?"
                    params.append(user_id)
                
                if operation_type is not None:
                    query += " AND operation_type = ?"
                    params.append(operation_type)
                
                cursor.execute(query, params)
                result = cursor.fetchone()
                
                return result[0] if result else 0
                
        except sqlite3.Error as error:
            raise DatabaseConnectionError(
                f"Failed to count calculation records: {error}"
            ) from error
    
    def get_statistics(
        self,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get calculation statistics.
        
        Args:
            user_id: Filter statistics by user ID.
            
        Returns:
            Dict[str, Any]: Dictionary containing statistics.
            
        Raises:
            DatabaseConnectionError: If database operation fails.
        """
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                
                base_condition = "WHERE 1=1"
                params = []
                
                if user_id is not None:
                    base_condition += " AND user_id = ?"
                    params.append(user_id)
                
                statistics = {}
                
                # Total calculations
                cursor.execute(
                    f"SELECT COUNT(*) FROM calculations {base_condition}",
                    params
                )
                statistics["total_calculations"] = cursor.fetchone()[0]
                
                # Average result
                cursor.execute(
                    f"SELECT AVG(result) FROM calculations {base_condition}",
                    params
                )
                statistics["average_result"] = cursor.fetchone()[0]
                
                # Operation type distribution
                cursor.execute(
                    f"""
                    SELECT operation_type, COUNT(*) as count 
                    FROM calculations {base_condition}
                    GROUP BY operation_type
                    ORDER BY count DESC
                    """,
                    params
                )
                statistics["operation_distribution"] = {
                    row["operation_type"]: row["count"]
                    for row in cursor.fetchall()
                }
                
                # Average duration
                cursor.execute(
                    f"""
                    SELECT AVG(duration_ms) 
                    FROM calculations 
                    {base_condition} AND duration_ms IS NOT NULL
                    """,
                    params
                )
                statistics["average_duration_ms"] = cursor.fetchone()[0]
                
                # Error rate
                cursor.execute(
                    f"""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors
                    FROM calculations {base_condition}
                    """,
                    params
                )
                row = cursor.fetchone()
                total = row["total"]
                errors = row["errors"]
                statistics["error_rate"] = errors / total if total > 0 else 0.0
                
                return statistics
                
        except sqlite3.Error as error:
            raise DatabaseConnectionError(
                f"Failed to get calculation statistics: {error}"
            ) from error
    
    def clear_all(self) -> int:
        """Delete all calculation records.
        
        Returns:
            int: Number of deleted records.
            
        Raises:
            DatabaseConnectionError: If database operation fails.
        """
        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute("DELETE FROM calculations")
                connection.commit()
                
                deleted_count = cursor.rowcount
                logger.warning(f"All calculation records cleared. Deleted: {deleted_count}")
                return deleted_count
                
        except sqlite3.Error as error:
            raise DatabaseConnectionError(
                f"Failed to clear calculation records: {error}"
            ) from error
    
    def close(self) -> None:
        """Close the repository and release resources."""
        logger.info("Calculation repository closed")