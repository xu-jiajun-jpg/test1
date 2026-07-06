"""图像预处理服务"""
import cv2
import numpy as np


class ImagePreprocessor:
    """图像预处理管线 — CLAHE + 高斯滤波 + 自适应二值化"""

    @staticmethod
    def preprocess(image: np.ndarray) -> np.ndarray:
        """完整的预处理管线"""
        # 灰度化（如果不是灰度图）
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # CLAHE 自适应直方图均衡化
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # 高斯滤波去噪
        denoised = cv2.GaussianBlur(enhanced, (3, 3), 0)

        # 自适应阈值二值化
        binary = cv2.adaptiveThreshold(
            denoised, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11, 2
        )

        return binary

    @staticmethod
    def check_quality(image: np.ndarray) -> dict:
        """检测图像质量 (分辨率/亮度/模糊度)"""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        h, w = gray.shape[:2]
        brightness = float(np.mean(gray))
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        blur_score = float(laplacian.var())

        return {
            "resolution": f"{w}x{h}",
            "brightness": round(brightness, 1),
            "blur_score": round(blur_score, 1),
            "needs_enhance": blur_score < 50 or brightness < 50 or brightness > 220,
        }
