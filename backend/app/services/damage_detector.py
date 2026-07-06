"""模块5：破损包裹检测 — 图像分割+形态学分析"""
import cv2
import numpy as np
import time


class DamageDetector:
    """检测包裹的破损、变形、渗漏等异常"""

    @staticmethod
    def detect(image_path: str, db=None) -> dict:
        """完整检测管线，返回检测报告"""
        start = time.time()
        img = cv2.imread(image_path)
        if img is None:
            return {"damaged": False, "error": "无法读取图片"}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        result = {"damaged": False, "issues": [], "details": {}}

        # ===== 1. 破损/裂纹检测：Canny边缘 + 轮廓异常分析 =====
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        irregular_contours = 0
        for c in contours:
            area = cv2.contourArea(c)
            if area < 100:
                continue  # 忽略小噪点
            perimeter = cv2.arcLength(c, True)
            if perimeter == 0:
                continue
            circularity = 4 * np.pi * area / (perimeter * perimeter)
            hull = cv2.convexHull(c)
            hull_area = cv2.contourArea(hull)
            if hull_area == 0:
                continue
            solidity = area / hull_area
            # 不规则轮廓：圆形度低 + 实心度低 → 可能破损
            if circularity < 0.3 and solidity < 0.7:
                irregular_contours += 1

        result["details"]["irregular_contours"] = irregular_contours
        if irregular_contours > 5:
            result["issues"].append({
                "type": "damage",
                "severity": "high" if irregular_contours > 10 else "medium",
                "description": f"检测到{irregular_contours}处不规则边缘，疑似破损",
            })
            result["damaged"] = True

        # ===== 2. 变形检测：形态学开运算 + HU矩比较 =====
        kernel = np.ones((5, 5), np.uint8)
        morph_open = cv2.morphologyEx(edges, cv2.MORPH_OPEN, kernel)
        morph_close = cv2.morphologyEx(morph_open, cv2.MORPH_CLOSE, kernel)
        morph_diff = cv2.absdiff(morph_open, morph_close)
        deformation_score = float(np.sum(morph_diff) / (h * w * 255)) * 100

        result["details"]["deformation_score"] = round(deformation_score, 2)
        if deformation_score > 8.0:
            result["issues"].append({
                "type": "deformed",
                "severity": "high" if deformation_score > 15 else "medium",
                "description": f"形态差异度{deformation_score:.1f}%，疑似包裹变形",
            })
            result["damaged"] = True

        # ===== 3. 渗漏/污渍检测：HSV颜色阈值 + 纹理异常 =====
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        # 检测深色渗漏（低亮度区域）
        leak_mask = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 255, 60]))
        leak_area = float(np.sum(leak_mask == 255) / (h * w)) * 100

        # 检测异常颜色斑点
        stain_mask = cv2.inRange(hsv, np.array([10, 50, 50]), np.array([30, 255, 200]))
        stain_area = float(np.sum(stain_mask == 255) / (h * w)) * 100

        result["details"]["leak_area_percent"] = round(leak_area, 2)
        result["details"]["stain_area_percent"] = round(stain_area, 2)

        if leak_area > 5.0:
            result["issues"].append({
                "type": "leak",
                "severity": "high" if leak_area > 15 else "medium",
                "description": f"检测到{leak_area:.1f}%面积疑似渗漏",
            })
            result["damaged"] = True

        if stain_area > 8.0:
            result["issues"].append({
                "type": "stain",
                "severity": "low",
                "description": f"检测到{stain_area:.1f}%面积异常污渍",
            })
            result["damaged"] = True

        # ===== 4. 纹理异常：Laplacian方差 =====
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        texture_var = float(laplacian.var())
        result["details"]["texture_variance"] = round(texture_var, 1)
        if texture_var > 500:
            result["issues"].append({
                "type": "texture_anomaly",
                "severity": "medium",
                "description": f"表面纹理异常(方差={texture_var:.0f})，疑似外力损伤",
            })
            result["damaged"] = True

        processing_time = int((time.time() - start) * 1000)
        result["processing_time_ms"] = processing_time
        return result


def detect_damage_result_to_storage(file_id: str, image_path: str, db) -> dict:
    """便捷方法：检测并写入异常记录"""
    result = DamageDetector.detect(image_path)
    if result.get("damaged"):
        from ..models.exception import ExceptionRecord
        exc = ExceptionRecord(
            file_id=file_id,
            exception_type="damage",
            detail=str(result.get("issues", [])),
            status="pending",
        )
        db.add(exc)
        db.commit()
    return result
