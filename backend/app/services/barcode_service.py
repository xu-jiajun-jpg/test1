"""条码/二维码解码服务 — pyzbar 封装"""
import time
from pyzbar import pyzbar
import cv2


class BarcodeService:
    """条码解码服务"""

    @staticmethod
    def decode(image_path: str) -> dict:
        """解码图像中的所有条码/二维码"""
        start = time.time()
        img = cv2.imread(image_path)
        if img is None:
            return {"barcodes": [], "total_count": 0, "fusion_result": "manual_required"}

        barcodes = pyzbar.decode(img)
        processing_time = int((time.time() - start) * 1000)

        results = []
        for b in barcodes:
            x, y, w, h = b.rect
            results.append({
                "type": b.type,
                "data": b.data.decode("utf-8", errors="replace"),
                "rect": {"x": x, "y": y, "w": w, "h": h},
            })

        total = len(results)
        if total == 1:
            fusion_result = "barcode"
        elif total > 1:
            fusion_result = "barcode"  # 多码：取第一个
        else:
            fusion_result = "ocr_fallback"  # 需要OCR回退

        return {
            "barcodes": results,
            "total_count": total,
            "fusion_result": fusion_result,
            "processing_time_ms": processing_time,
        }
