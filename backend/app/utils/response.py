"""统一响应格式"""
from typing import Any


def success(data: Any = None, message: str = "ok") -> dict:
    return {"code": 200, "message": message, "data": data}


def error(message: str = "error", code: int = 400) -> dict:
    return {"code": code, "message": message, "data": None}


def paginated(items: list, total: int, page: int, page_size: int) -> dict:
    return {
        "code": 200,
        "message": "ok",
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
    }
