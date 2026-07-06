"""
包裹条码模拟系统
— 生成正常/异常包裹 → 条码扫描 → 自动分拣 → 异常分流
"""
import uuid
import random
import time
import json
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
from ..config import UPLOADS_DIR


# ===== 条码数据模板 =====
TRACKING_PREFIXES = ["SF", "YT", "DB", "JD", "ZTO", "BS", "EMS", "TT", "YT2", "YC"]
DISTRICT_LIST = ["东湖区", "西湖区", "青云谱区", "青山湖区", "新建区", "红谷滩区"]
DISTRICT_ROADS = {
    "东湖区": ["阳明路", "八一大道", "南京西路", "福州路", "民德路", "叠山路"],
    "西湖区": ["中山路", "孺子路", "抚河路", "站前西路", "绳金塔街"],
    "青云谱区": ["井冈山大道", "广州路", "南莲路", "迎宾大道", "昌南大道"],
    "青山湖区": ["北京东路", "上海路", "青山湖大道", "高新大道", "南京东路"],
    "新建区": ["新建大道", "长堎大道", "文化大道", "礼步湖大道", "子实路"],
    "红谷滩区": ["红谷中大道", "凤凰中大道", "丰和中大道", "会展路", "怡园路"],
}

# 异常类型
DAMAGE_TYPES = {
    "tear":      {"label": "破损",         "barcode_readable": False, "weight": 3},
    "deformed":  {"label": "变形",         "barcode_readable": False, "weight": 2},
    "leaked":    {"label": "渗漏",         "barcode_readable": False, "weight": 2},
    "blurred":   {"label": "条码模糊",      "barcode_readable": False, "weight": 4},
    "scribbled": {"label": "条码涂鸦",      "barcode_readable": False, "weight": 3},
    "missing":   {"label": "条码缺失",      "barcode_readable": False, "weight": 1},
    "normal":    {"label": "正常",          "barcode_readable": True,  "weight": 85},
}

WEIGHT_KEY = [k for k, v in DAMAGE_TYPES.items() for _ in range(v["weight"])]


@dataclass
class SimPackage:
    tracking_number: str
    barcode_data: str      # CODE128 编码内容
    barcode_readable: bool
    province: str           # 固定为"江西"
    city: str               # 固定为"南昌市"
    district: str           # 南昌6大区之一
    size_cm: tuple          # (l, w, h)
    weight_kg: float
    defect_type: str
    defect_label: str
    target_chute: str       # 正常→对应分拣口  异常→CH-006
    status: str             # normal / damaged / exception
    scan_result: str        # 扫描结果描述
    scan_time_ms: float = 0
    file_id: str = ""


class BarcodeSimulator:
    """包裹条码模拟器"""

    @staticmethod
    def generate_batch(count: int, damage_rate: float = 0.15) -> list[dict]:
        """
        生成一批包裹
        count: 数量
        damage_rate: 异常包裹比例 (0.0-1.0)
        返回: list[SimPackage dict]
        """
        packages = []
        start = time.time()

        for i in range(count):
            # 1. 确定是否异常
            is_damaged = random.random() < damage_rate
            if is_damaged:
                defect_type = random.choice([k for k, v in DAMAGE_TYPES.items()
                                             if k != "normal" and v["barcode_readable"] is False])
            else:
                defect_type = "normal"

            defect_info = DAMAGE_TYPES[defect_type]
            barcode_readable = defect_info["barcode_readable"]

            # 2. 生成条码
            prefix = random.choice(TRACKING_PREFIXES)
            num = random.randint(1000000000, 9999999999)
            tracking_number = f"{prefix}{num}"
            barcode_data = f"(01){tracking_number}(420){random.randint(1000,9999)}"

            # 3. 目的地（南昌6大区）
            district = random.choice(DISTRICT_LIST)
            city = "南昌市"

            # 4. 物品尺寸 + 重量
            l = round(random.uniform(20, 55), 1)
            w = round(random.uniform(15, 40), 1)
            h = round(random.uniform(10, 30), 1)
            weight = round(random.uniform(0.3, 15.0), 2)

            # 5. 分拣决策
            target_chute = _assign_chute(district)

            # 6. 分流
            if not barcode_readable:
                target_chute = "CH-006"  # 异常通道
                status = "exception"
                scan_result = f"条码不可读: {defect_info['label']}"
            else:
                status = "normal"
                scan_result = f"扫描成功: CODE128 → {barcode_data[:30]}..."

            scan_time = round(random.uniform(20, 200), 1)

            pkg = {
                "tracking_number": tracking_number,
                "barcode_data": barcode_data,
                "barcode_readable": barcode_readable,
                "province": "江西", "city": city, "district": district,
                "size_cm": (l, w, h),
                "weight_kg": weight,
                "defect_type": defect_type,
                "defect_label": defect_info["label"],
                "target_chute": target_chute,
                "status": status,
                "scan_result": scan_result,
                "scan_time_ms": scan_time,
                "file_id": uuid.uuid4().hex[:12],
            }
            packages.append(pkg)

        total_time = round((time.time() - start) * 1000, 0)
        normal_count = sum(1 for p in packages if p["status"] == "normal")
        exception_count = sum(1 for p in packages if p["status"] == "exception")

        # 按分拣口统计
        chute_stats = {}
        defect_stats = {}
        for p in packages:
            chute_stats[p["target_chute"]] = chute_stats.get(p["target_chute"], 0) + 1
            defect_stats[p["defect_label"]] = defect_stats.get(p["defect_label"], 0) + 1

        return {
            "total": count,
            "normal": normal_count,
            "exception": exception_count,
            "damage_rate_actual": round(exception_count / count * 100, 1),
            "total_time_ms": total_time,
            "packages": packages,
            "chute_distribution": [{"chute": k, "count": v} for k, v in sorted(chute_stats.items())],
            "defect_breakdown": [{"type": k, "count": v, "label": DAMAGE_TYPES[k.split("_")[0] if "_" in k else k].get("label", k) if k in DAMAGE_TYPES else k}
                                  for k, v in defect_stats.items()],
        }


def _assign_chute(district: str) -> str:
    """根据南昌行政区分配分拣口"""
    mapping = {
        "东湖区": "CH-001", "西湖区": "CH-002", "青云谱区": "CH-003",
        "青山湖区": "CH-004", "新建区": "CH-005", "红谷滩区": "CH-005",
    }
    return mapping.get(district, "CH-005")
