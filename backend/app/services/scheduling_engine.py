"""模块9：智能排班与任务调度 — 基于历史数据AI预测分拣量"""
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict


class SchedulingEngine:
    """AI预测分拣量 + 自动生成排班计划"""

    @staticmethod
    def predict_volume(historical_data: list[dict], target_date: str) -> dict:
        """
        基于历史数据预测指定日期的分拣量
        historical_data: [{"date":"2024-01-01","hour":8,"count":520}, ...]
        使用加权移动平均 + 周期性因子
        """
        if not historical_data:
            # 无历史数据时使用标准工作日分布
            default_dist = [0.01,0.01,0.01,0.01,0.02,0.05,0.10,0.15,0.18,0.14,0.10,0.08,0.06,0.08,0.12,0.15,0.18,0.14,0.10,0.08,0.06,0.04,0.02,0.01]
            hourly = {h: round(500 * f) for h, f in enumerate(default_dist)}
            target = datetime.strptime(target_date, "%Y-%m-%d")
            return {"date": target_date, "day_of_week": target.weekday(), "total_predicted": 500, "hourly": hourly, "peak_hours": [(8,90),(15,90),(16,90)]}

        target = datetime.strptime(target_date, "%Y-%m-%d")
        dow = target.weekday()  # 0=Mon ... 6=Sun

        # 按小时聚合历史数据
        hourly_avg = defaultdict(list)
        for d in historical_data:
            d_date = datetime.strptime(d["date"], "%Y-%m-%d")
            if d_date >= target:
                continue
            days_diff = (target - d_date).days
            weight = max(1.0, 30.0 / (days_diff + 1))  # 越近权重越高
            if d.get("hour") is not None:
                hourly_avg[d["hour"]].append((d.get("count", 0), weight))

        # 预测每小时
        hourly_predictions = {}
        total = 0
        for h in range(24):
            data = hourly_avg.get(h, [])
            if data:
                total_weight = sum(w for _, w in data)
                pred = sum(c * w for c, w in data) / total_weight if total_weight > 0 else 0
            else:
                pred = 0
            # 工作日系数
            if dow < 5:  # 工作日
                pred *= 1.2
            else:  # 周末
                pred *= 0.6
            hourly_predictions[h] = round(pred)
            total += pred

        return {
            "date": target_date,
            "day_of_week": dow,
            "total_predicted": round(total),
            "hourly": hourly_predictions,
            "peak_hours": sorted(
                [(h, c) for h, c in hourly_predictions.items()],
                key=lambda x: x[1], reverse=True
            )[:3],
        }

    @staticmethod
    def generate_schedule(prediction: dict, operators_count: int = 10) -> dict:
        """
        根据预测生成排班计划
        策略：
        - 高峰时段(分拣量 > 平均值*1.5) → 全部上岗
        - 平峰时段 → 60%上岗
        - 低谷时段 → 30%上岗(轮休)
        - 夜班时段(22-6) → 安排值班人员
        """
        hourly = prediction.get("hourly", {})
        if not hourly:
            return {"shifts": [], "utilization": 0}

        avg_volume = sum(hourly.values()) / max(sum(1 for v in hourly.values() if v > 0), 1)
        high_threshold = avg_volume * 1.5
        low_threshold = avg_volume * 0.3

        shifts = []
        total_assigned = 0
        total_capacity = 0

        for h in range(24):
            vol = hourly.get(h, 0)
            if vol >= high_threshold:
                ratio = 1.0  # 全勤
            elif vol >= low_threshold:
                ratio = 0.6  # 60%
            elif h >= 22 or h <= 6:
                ratio = 0.15  # 夜班最低
            else:
                ratio = 0.3  # 低谷轮休

            assigned = max(1, round(operators_count * ratio)) if vol > 0 else 0
            total_assigned += assigned
            total_capacity += operators_count if vol > 0 else 0

            shifts.append({
                "hour": h,
                "volume_predicted": vol,
                "operators_needed": assigned,
                "ratio": round(ratio * 100),
                "type": "peak" if ratio >= 1.0 else "normal" if ratio >= 0.5 else "low",
            })

        utilization = round(total_assigned / max(total_capacity, 1) * 100, 1)

        return {
            "shifts": shifts,
            "total_operators": operators_count,
            "utilization_percent": utilization,
            "summary": {
                "peak_hours_count": sum(1 for s in shifts if s["type"] == "peak"),
                "normal_hours_count": sum(1 for s in shifts if s["type"] == "normal"),
                "low_hours_count": sum(1 for s in shifts if s["type"] == "low"),
                "total_man_hours": total_assigned,
            },
        }

    @staticmethod
    def optimize_equipment(prediction: dict) -> dict:
        """设备启停策略：根据预测分拣量决定设备开关"""
        hourly = prediction.get("hourly", {})
        avg = sum(hourly.values()) / max(len([v for v in hourly.values() if v > 0]), 1)

        strategy = []
        for h in range(24):
            vol = hourly.get(h, 0)
            if vol == 0 or h < 3:
                status = "off"
                reason = "夜间停机"
            elif vol > avg * 1.3:
                status = "full"
                reason = "高峰全速"
            elif vol > avg * 0.5:
                status = "eco"
                reason = "经济模式"
            else:
                status = "standby"
                reason = "待机"

            strategy.append({
                "hour": h,
                "volume_predicted": vol,
                "equipment_status": status,
                "reason": reason,
            })

        return {
            "total_runtime_hours": sum(1 for s in strategy if s["equipment_status"] != "off"),
            "full_load_hours": sum(1 for s in strategy if s["equipment_status"] == "full"),
            "estimated_energy_saving": f"{sum(1 for s in strategy if s['equipment_status'] in ('off','standby')) / 24 * 100:.1f}%",
            "strategy": strategy,
        }
