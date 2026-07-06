"""OCR识别服务 — PaddleOCR 封装"""
import os
import cv2
import numpy as np
import re
import time

# 解决 PaddlePaddle 3.x oneDNN + PIR 兼容性问题
os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")
os.environ.setdefault("FLAGS_enable_pir_api", "0")
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("FLAGS_use_onednn", "0")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# 全局单例
_ocr_engine = None


def get_ocr_engine():
    """懒加载 PaddleOCR 引擎"""
    global _ocr_engine
    if _ocr_engine is None:
        try:
            from paddleocr import PaddleOCR
            _ocr_engine = PaddleOCR(lang="ch")
        except Exception as e:
            raise RuntimeError(f"PaddleOCR初始化失败: {e}")
    return _ocr_engine


class OCRService:
    """运单OCR识别服务"""

    @staticmethod
    def recognize(image_path: str, preprocessed: np.ndarray | None = None) -> dict:
        """识别运单文字 返回结构化结果"""
        start = time.time()
        engine = get_ocr_engine()

        # PaddleOCR predict 返回 generator，转为 list
        try:
            raw_results = list(engine.predict(image_path))
        except Exception:
            # 回退：用preprocessed图像
            if preprocessed is not None:
                cv2.imwrite(image_path + "_pre.png", preprocessed)
                raw_results = list(engine.predict(image_path + "_pre.png"))
            else:
                raise

        processing_time = int((time.time() - start) * 1000)

        if not raw_results:
            return {
                "raw_text": "",
                "status": "manual_required",
                "processing_time_ms": processing_time,
                "fields": {},
            }

        # 新版 PaddleOCR predict() 返回 OCRResult(dict子类)，用 .get() 取值
        lines = []
        for r in raw_results:
            texts = r.get("rec_texts", []) or []
            for text in texts:
                lines.append(text)

        raw_text = "\n".join(lines)

        # 提取结构化字段
        fields = OCRService._extract_fields(raw_text)

        # 运单有效性校验：至少需要2个关键字段才认为是运单
        is_waybill = OCRService._is_waybill(fields)
        if not is_waybill:
            return {
                "raw_text": raw_text,
                "status": "not_waybill",
                "processing_time_ms": processing_time,
                "fields": fields,
            }

        # 分档状态：纯字段完整性判定（不依赖置信度）
        # 关键字段：运单号、电话、分区——三者齐全即可自动通过
        critical_keys = ["tracking_number", "phone", "district"]
        critical_ok = sum(1 for k in critical_keys if fields.get(k))

        if critical_ok == len(critical_keys):
            status = "auto_pass"
        elif critical_ok >= 2:
            status = "need_review"
        else:
            status = "manual_required"
            missing_critical = [k for k in critical_keys if not fields.get(k)]
            if missing_critical:
                fields["_missing"] = ",".join(missing_critical)

        return {
            "raw_text": raw_text,
            "status": status,
            "processing_time_ms": processing_time,
            "fields": fields,
        }

    @staticmethod
    def _is_waybill(fields: dict) -> bool:
        """校验是否像运单：有运单号+1辅助字段，或≥3辅助字段"""
        has_tn = bool(fields.get("tracking_number"))
        aux = ["receiver_name", "phone", "city", "district"]
        aux_count = sum(1 for k in aux if fields.get(k))
        return (has_tn and aux_count >= 1) or (aux_count >= 3)

    @staticmethod
    def _extract_fields(text: str) -> dict:
        """从OCR文本中提取结构化字段"""
        fields = {
            "receiver_name": "",
            "phone": "",
            "province": "",
            "city": "",
            "district": "",
            "detail_address": "",
            "tracking_number": "",
        }

        # 手机号：优先匹配"电话/手机/联系方式"标签后的号码
        phone_match = re.search(r'(?:电话|手机|联系方式|Tel)[:：\s]*(\+?1[3-9]\d{9})', text)
        if not phone_match:
            # 退而全局匹配（用更严格的号段：工信部公布的合法号段）
            phone_match = re.search(r'\b(1(3[0-9]|4[5-9]|5[0-35-9]|6[2567]|7[0-8]|8[0-9]|9[0-35-9])\d{8})\b', text)
        if phone_match:
            fields["phone"] = phone_match.group(1) if phone_match.lastindex else phone_match.group()

        # 运单号：常见快递前缀 + 数字，排除纯11位数字（避免误匹配手机号）
        tn_match = re.search(r'(?:运单号|单号|Tracking|TN)[:：\s]*([A-Z]{2,3}\d{9,15}|\d{12,20})', text)
        if not tn_match:
            # 全局匹配字母开头+数字组合（常见快递单号格式）
            tn_match = re.search(r'\b([A-Z]{2,3}\d{9,15})\b', text)
        if tn_match:
            tn = tn_match.group(1) if tn_match.lastindex else tn_match.group()
            # 排除纯11位数字（手机号）
            if not (tn.isdigit() and len(tn) == 11):
                fields["tracking_number"] = tn

        # 省份/区域 - 优先匹配南昌大区
        nanchang_districts = ["东湖区", "西湖区", "青云谱区", "青山湖区", "新建区", "红谷滩区"]
        found_district = ""
        for d in nanchang_districts:
            if d in text:
                found_district = d
                fields["district"] = d
                break

        # 匹配省份（保留原有逻辑作为fallback）
        provinces = ["北京", "上海", "天津", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江",
                     "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南",
                     "广东", "广西", "海南", "四川", "贵州", "云南", "西藏", "陕西", "甘肃",
                     "青海", "宁夏", "新疆", "内蒙古"]
        for p in provinces:
            if p in text:
                fields["province"] = p
                # 如果是江西且找到了南昌大区，city 自动设南昌
                if p == "江西" and found_district:
                    fields["city"] = "南昌市"
                break

        # 城市 — 以"市"结尾的词（排除含冒号的前缀）
        city_match = re.search(r'(?:^|\s)([^\s：:]{2,6}市)', text)
        if city_match:
            raw_city = city_match.group(1)
            # 去掉可能附带的省份前缀（如"江西南昌市" → "南昌市"）
            if fields.get("province") and raw_city.startswith(fields["province"]):
                raw_city = raw_city[len(fields["province"]):]
            fields["city"] = raw_city

        # 区县 — 以"区/县"结尾（排除含冒号的前缀）；不覆盖南昌大区已匹配结果
        if not fields.get("district"):
            district_match = re.search(r'(?:^|\s)([^\s：:]{2,6}[区县])', text)
            if district_match:
                fields["district"] = district_match.group(1)

        # 收件人 — 匹配 "收件人:" "收货人:" "姓名:" 后面
        name_match = re.search(r'(?:收件人|收货人|姓名)[：:]\s*([^\s]{2,4})', text)
        if name_match:
            fields["receiver_name"] = name_match.group(1)

        # 详细地址 — 优先匹配含"地址"的行，其次含省/市/区/路/巷的行（排除运单号行）
        lines = text.split("\n")
        for line in lines:
            if "地址" in line or ("号" in line and ("省" in line or "市" in line or "路" in line or "巷" in line)):
                fields["detail_address"] = line.strip()
                break

        return fields
