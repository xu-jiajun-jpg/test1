"""上传路由 — F01 图片上传管理"""
import os
import uuid
import random
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from sqlalchemy.orm import Session

from ..database import get_db
from ..config import UPLOADS_DIR
from ..models.upload import UploadRecord
from ..middleware.auth_middleware import get_current_user_id
from ..utils.file_utils import validate_file, generate_file_path, create_thumbnail

router = APIRouter(prefix="/api/upload", tags=["上传"])


@router.post("/single")
async def upload_single(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """单张上传"""
    contents = await file.read()
    file_size = len(contents)

    valid, msg = validate_file(file.filename, file_size)
    if not valid:
        detail = "格式非法" if "格式" in msg else "大小超限"
        status_code = 400 if "格式" in msg else 413
        raise HTTPException(status_code=status_code, detail=msg)

    # 存储
    rel_path, date_dir = generate_file_path(file.filename)
    abs_dir = UPLOADS_DIR / date_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    abs_path = UPLOADS_DIR / rel_path
    with open(abs_path, "wb") as f:
        f.write(contents)

    # 缩略图
    thumb_rel = rel_path.replace(".", "_thumb.")
    thumb_abs = UPLOADS_DIR / thumb_rel
    thumb_rel_final = thumb_rel if create_thumbnail(str(abs_path), str(thumb_abs)) else None

    # 入库（带随机尺寸估算）
    record = UploadRecord(
        file_id=uuid.uuid4().hex,
        original_name=file.filename,
        file_path=rel_path,
        thumbnail_path=thumb_rel_final,
        file_size=file_size,
        mime_type=file.content_type,
        uploader_id=user_id,
        status="done",
        package_length=round(random.uniform(20, 60), 1),
        package_width=round(random.uniform(15, 45), 1),
        package_height=round(random.uniform(10, 40), 1),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "code": 200,
        "message": "上传成功",
        "data": {
            "file_id": record.file_id,
            "original_name": record.original_name,
            "file_url": f"/uploads/{rel_path}",
            "thumbnail_url": f"/uploads/{thumb_rel_final}" if thumb_rel_final else None,
            "file_size": file_size,
        },
    }


@router.post("/batch")
async def upload_batch(
    files: list[UploadFile] = File(...),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """批量上传（最多10张）"""
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="单次最多上传10张图片")

    results = []
    errors = []

    for file in files:
        contents = await file.read()
        file_size = len(contents)

        valid, msg = validate_file(file.filename, file_size)
        if not valid:
            errors.append({"filename": file.filename, "error": msg})
            continue

        rel_path, date_dir = generate_file_path(file.filename)
        abs_dir = UPLOADS_DIR / date_dir
        abs_dir.mkdir(parents=True, exist_ok=True)
        abs_path = UPLOADS_DIR / rel_path
        with open(abs_path, "wb") as f:
            f.write(contents)

        thumb_rel = rel_path.replace(".", "_thumb.")
        thumb_abs = UPLOADS_DIR / thumb_rel
        thumb_rel_final = thumb_rel if create_thumbnail(str(abs_path), str(thumb_abs)) else None

        record = UploadRecord(
            file_id=uuid.uuid4().hex,
            original_name=file.filename,
            file_path=rel_path,
            thumbnail_path=thumb_rel_final,
            file_size=file_size,
            mime_type=file.content_type,
            uploader_id=user_id,
            status="done",
            package_length=round(random.uniform(20, 60), 1),
            package_width=round(random.uniform(15, 45), 1),
            package_height=round(random.uniform(10, 40), 1),
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        results.append({
            "file_id": record.file_id,
            "original_name": record.original_name,
            "file_url": f"/uploads/{rel_path}",
            "thumbnail_url": f"/uploads/{thumb_rel_final}" if thumb_rel_final else None,
        })

    return {
        "code": 200,
        "message": f"成功 {len(results)} 张，失败 {len(errors)} 张",
        "data": {"success": results, "errors": errors},
    }


@router.get("/records")
def list_uploads(
    page: int = 1,
    page_size: int = 20,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """查询上传记录"""
    total = db.query(UploadRecord).count()
    records = (
        db.query(UploadRecord)
        .order_by(UploadRecord.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    from ..utils.response import paginated
    items = [
        {
            "file_id": r.file_id,
            "original_name": r.original_name,
            "file_url": f"/uploads/{r.file_path}",
            "thumbnail_url": f"/uploads/{r.thumbnail_path}" if r.thumbnail_path else None,
            "file_size": r.file_size,
            "package_length": r.package_length,
            "package_width": r.package_width,
            "package_height": r.package_height,
            "package_volume": round(r.package_length * r.package_width * r.package_height, 1) if (r.package_length and r.package_width and r.package_height) else None,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]
    return paginated(items, total, page, page_size)
