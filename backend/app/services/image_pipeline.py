"""图像管线服务 — 串联 预处理→OCR→条码 的管线"""
import time
import uuid
from sqlalchemy.orm import Session

from .image_preprocess import ImagePreprocessor
from .ocr_service import OCRService
from .barcode_service import BarcodeService
from ..config import UPLOADS_DIR
from ..models.upload import UploadRecord
from ..models.ocr import OCRResult
from ..models.barcode import BarcodeResult


class ImagePipelineService:
    """图像处理管线 — 上传后触发"""

    @staticmethod
    async def process(file_id: str, db: Session) -> dict:
        """完整管线：预处理 → OCR → 条码"""
        start = time.time()

        # 查找上传记录
        record = db.query(UploadRecord).filter(UploadRecord.file_id == file_id).first()
        if not record:
            return {"error": "记录不存在"}

        record.status = "processing"
        db.commit()

        image_path = str(UPLOADS_DIR / record.file_path)

        # 读取原图
        try:
            import cv2
            image = cv2.imread(image_path)
        except Exception as e:
            record.status = "failed"
            db.commit()
            return {"error": f"读取图片失败: {e}"}

        # 质量检测
        quality = ImagePreprocessor.check_quality(image)

        # 预处理
        if quality["needs_enhance"]:
            preprocessed = ImagePreprocessor.preprocess(image)
        else:
            preprocessed = None

        # OCR 识别
        try:
            ocr_result = OCRService.recognize(image_path, preprocessed)
        except Exception as e:
            ocr_result = {
                "raw_text": "", "status": "manual_required",
                "processing_time_ms": 0, "fields": {},
            }

        # 写入 OCR 结果
        ocr_record = OCRResult(
            file_id=file_id,
            raw_text=ocr_result.get("raw_text", ""),
            receiver_name=ocr_result.get("fields", {}).get("receiver_name"),
            phone=ocr_result.get("fields", {}).get("phone"),
            province=ocr_result.get("fields", {}).get("province"),
            city=ocr_result.get("fields", {}).get("city"),
            district=ocr_result.get("fields", {}).get("district"),
            detail_address=ocr_result.get("fields", {}).get("detail_address"),
            tracking_number=ocr_result.get("fields", {}).get("tracking_number"),
            processing_time_ms=ocr_result.get("processing_time_ms", 0),
            status=ocr_result.get("status", "manual_required"),
        )
        db.add(ocr_record)

        # 条码解码
        try:
            barcode_result = BarcodeService.decode(image_path)
        except Exception:
            barcode_result = {"barcodes": [], "total_count": 0, "fusion_result": "manual_required"}

        # 写入条码结果
        barcodes = barcode_result.get("barcodes", [])
        barcode_record = None
        if barcodes:
            first = barcodes[0]
            barcode_record = BarcodeResult(
                file_id=file_id,
                barcode_type=first["type"],
                barcode_data=first["data"],
                rect_x=first["rect"]["x"],
                rect_y=first["rect"]["y"],
                rect_w=first["rect"]["w"],
                rect_h=first["rect"]["h"],
                total_count=barcode_result["total_count"],
                fusion_result=barcode_result["fusion_result"],
            )
            db.add(barcode_record)
        else:
            barcode_record = BarcodeResult(
                file_id=file_id,
                fusion_result=barcode_result.get("fusion_result", "ocr_fallback"),
                total_count=0,
            )
            db.add(barcode_record)

        # 更新上传记录状态
        record.status = "done"
        db.commit()

        total_time = int((time.time() - start) * 1000)

        return {
            "file_id": file_id,
            "quality": quality,
            "ocr": {
                "status": ocr_result.get("status"),
                "fields": ocr_result.get("fields"),
                "processing_time_ms": ocr_result.get("processing_time_ms"),
            },
            "barcode": {
                "type": barcode_record.barcode_type if barcode_record else None,
                "data": barcode_record.barcode_data if barcode_record else None,
                "total_count": barcode_result.get("total_count", 0),
                "fusion_result": barcode_result.get("fusion_result"),
            },
            "total_time_ms": total_time,
        }
