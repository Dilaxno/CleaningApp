"""
Pagination utilities for list endpoints
Ensures all list queries are paginated to handle millions of records
"""
from typing import TypeVar, Generic, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Query

T = TypeVar('T')


class PaginationParams(BaseModel):
    """Standard pagination parameters"""
    skip: int = Field(0, ge=0, description="Number of records to skip")
    limit: int = Field(50, ge=1, le=100, description="Maximum number of records to return (max 100)")
    
    @property
    def offset(self) -> int:
        """Alias for skip (for SQLAlchemy compatibility)"""
        return self.skip


class PageInfo(BaseModel):
    """Pagination metadata"""
    total: int = Field(..., description="Total number of records")
    skip: int = Field(..., description="Number of records skipped")
    limit: int = Field(..., description="Number of records per page")
    has_next: bool = Field(..., description="Whether there are more records")
    has_prev: bool = Field(..., description="Whether there are previous records")
    total_pages: int = Field(..., description="Total number of pages")
    current_page: int = Field(..., description="Current page number (1-indexed)")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response"""
    items: List[T] = Field(..., description="List of items")
    page_info: PageInfo = Field(..., description="Pagination metadata")


def paginate_query(
    query: Query,
    skip: int = 0,
    limit: int = 50,
    max_limit: int = 100
) -> tuple[List, int]:
    """
    Paginate a SQLAlchemy query
    
    Args:
        query: SQLAlchemy query object
        skip: Number of records to skip
        limit: Number of records to return
        max_limit: Maximum allowed limit
    
    Returns:
        Tuple of (items, total_count)
    
    Example:
        query = db.query(Client).filter(Client.user_id == user_id)
        items, total = paginate_query(query, skip=0, limit=50)
    """
    # Enforce max limit
    limit = min(limit, max_limit)
    
    # Get total count (before pagination)
    total = query.count()
    
    # Apply pagination
    items = query.offset(skip).limit(limit).all()
    
    return items, total


def create_page_info(
    total: int,
    skip: int,
    limit: int
) -> PageInfo:
    """
    Create pagination metadata
    
    Args:
        total: Total number of records
        skip: Number of records skipped
        limit: Number of records per page
    
    Returns:
        PageInfo object with pagination metadata
    """
    current_page = (skip // limit) + 1 if limit > 0 else 1
    total_pages = (total + limit - 1) // limit if limit > 0 else 1
    has_next = skip + limit < total
    has_prev = skip > 0
    
    return PageInfo(
        total=total,
        skip=skip,
        limit=limit,
        has_next=has_next,
        has_prev=has_prev,
        total_pages=total_pages,
        current_page=current_page
    )


def create_paginated_response(
    items: List[T],
    total: int,
    skip: int,
    limit: int
) -> dict:
    """
    Create a paginated response dictionary
    
    Args:
        items: List of items
        total: Total number of records
        skip: Number of records skipped
        limit: Number of records per page
    
    Returns:
        Dictionary with items and page_info
    
    Example:
        items, total = paginate_query(query, skip=0, limit=50)
        return create_paginated_response(items, total, skip=0, limit=50)
    """
    page_info = create_page_info(total, skip, limit)
    
    return {
        "items": items,
        "page_info": {
            "total": page_info.total,
            "skip": page_info.skip,
            "limit": page_info.limit,
            "has_next": page_info.has_next,
            "has_prev": page_info.has_prev,
            "total_pages": page_info.total_pages,
            "current_page": page_info.current_page
        }
    }


# Cursor-based pagination for very large datasets (alternative to offset-based)

class CursorPaginationParams(BaseModel):
    """Cursor-based pagination parameters (more efficient for large datasets)"""
    cursor: Optional[str] = Field(None, description="Cursor for next page")
    limit: int = Field(50, ge=1, le=100, description="Maximum number of records to return")


def paginate_by_cursor(
    query: Query,
    cursor_column,
    cursor_value: Optional[str] = None,
    limit: int = 50,
    max_limit: int = 100,
    ascending: bool = False
) -> tuple[List, Optional[str]]:
    """
    Cursor-based pagination (more efficient for large datasets)
    
    Args:
        query: SQLAlchemy query object
        cursor_column: Column to use for cursor (e.g., Client.id, Client.created_at)
        cursor_value: Current cursor value (None for first page)
        limit: Number of records to return
        max_limit: Maximum allowed limit
        ascending: Sort order (False = descending, True = ascending)
    
    Returns:
        Tuple of (items, next_cursor)
    
    Example:
        query = db.query(Client).filter(Client.user_id == user_id)
        items, next_cursor = paginate_by_cursor(
            query, 
            Client.created_at, 
            cursor_value=request.cursor,
            limit=50
        )
    """
    # Enforce max limit
    limit = min(limit, max_limit)
    
    # Apply cursor filter
    if cursor_value:
        if ascending:
            query = query.filter(cursor_column > cursor_value)
        else:
            query = query.filter(cursor_column < cursor_value)
    
    # Apply sorting
    if ascending:
        query = query.order_by(cursor_column.asc())
    else:
        query = query.order_by(cursor_column.desc())
    
    # Fetch limit + 1 to check if there are more records
    items = query.limit(limit + 1).all()
    
    # Check if there are more records
    has_next = len(items) > limit
    if has_next:
        items = items[:limit]
    
    # Get next cursor
    next_cursor = None
    if has_next and items:
        last_item = items[-1]
        next_cursor = str(getattr(last_item, cursor_column.key))
    
    return items, next_cursor


# Helper function for FastAPI dependencies

def get_pagination_params(
    skip: int = 0,
    limit: int = 50
) -> PaginationParams:
    """
    FastAPI dependency for pagination parameters
    
    Example:
        @router.get("/clients")
        async def list_clients(
            pagination: PaginationParams = Depends(get_pagination_params),
            db: Session = Depends(get_db)
        ):
            query = db.query(Client).filter(Client.user_id == user_id)
            items, total = paginate_query(query, pagination.skip, pagination.limit)
            return create_paginated_response(items, total, pagination.skip, pagination.limit)
    """
    return PaginationParams(skip=skip, limit=limit)
