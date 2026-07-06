"""模拟包裹图片生成器 — 用 Pillow + python-barcode 生成仿真的运单面单图片"""
import os
import uuid
import random
import string
from datetime import datetime
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

try:
    import barcode
    from barcode.writer import ImageWriter
    HAS_BARCODE = True
except ImportError:
    HAS_BARCODE = False


class SimPackageGenerator:
    """模拟包裹运单面单图片生成"""

    # 南昌市6大行政区（所有分区都有匹配的分拣规则）
    DISTRICTS = ["东湖区", "西湖区", "青云谱区", "青山湖区", "新建区", "红谷滩区"]
    UNMATCHED_DISTRICTS = []  # 所有分区都有规则，无规则分区保留空列表
    DISTRICT_ADDRESS = {
        "东湖区": {"roads": ["阳明路", "八一大道", "南京西路", "福州路", "民德路", "叠山路"]},
        "西湖区": {"roads": ["中山路", "孺子路", "抚河路", "站前西路", "绳金塔街"]},
        "青云谱区": {"roads": ["井冈山大道", "广州路", "南莲路", "迎宾大道", "昌南大道"]},
        "青山湖区": {"roads": ["北京东路", "上海路", "青山湖大道", "高新大道", "南京东路"]},
        "新建区": {"roads": ["新建大道", "长堎大道", "文化大道", "礼步湖大道", "子实路"]},
        "红谷滩区": {"roads": ["红谷中大道", "凤凰中大道", "丰和中大道", "会展路", "怡园路"]},
    }

    # 随机姓名素材
    SURNAMES = ["张", "李", "王", "刘", "陈", "杨", "赵", "黄", "周", "吴",
                 "徐", "孙", "马", "朱", "胡", "郭", "何", "高", "林", "郑"]
    GIVEN_NAMES = ["伟", "芳", "娜", "秀英", "敏", "静", "丽", "强", "磊", "洋",
                   "勇", "艳", "杰", "娟", "涛", "明", "超", "秀兰", "霞", "平",
                   "刚", "桂英", "文", "华", "建华", "玉兰", "飞", "桂花", "波", "斌"]

    IMAGE_WIDTH = 800
    IMAGE_HEIGHT = 450

    @staticmethod
    def _random_phone() -> str:
        return f"1{random.choice(['3','5','6','7','8','9'])}{''.join(random.choices(string.digits, k=9))}"

    @staticmethod
    def _random_tracking_number() -> str:
        """生成仿真运单号 SF + 10位数字 + 2位校验"""
        nums = ''.join(random.choices(string.digits, k=10))
        return f"SF{nums}"

    @staticmethod
    def _random_name() -> str:
        return f"{random.choice(SimPackageGenerator.SURNAMES)}{random.choice(SimPackageGenerator.GIVEN_NAMES)}"

    @staticmethod
    def is_valid_nanchang_destination(fields: dict) -> bool:
        return fields.get("province") == "江西" and "南昌" in fields.get("city", "")

    @staticmethod
    def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """尝试加载中文字体，失败回退默认字体"""
        # Windows 常见中文字体路径
        font_candidates = [
            "C:/Windows/Fonts/simhei.ttf",      # 黑体
            "C:/Windows/Fonts/msyh.ttc",         # 微软雅黑
            "C:/Windows/Fonts/simsun.ttc",       # 宋体
            "C:/Windows/Fonts/STSONG.TTF",       # 华文宋体
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",  # Linux
            "/System/Library/Fonts/PingFang.ttc",  # macOS
        ]
        for path in font_candidates:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue
        return ImageFont.load_default()

    @staticmethod
    def generate(output_dir: str) -> tuple[str, dict]:
        """
        生成一张模拟运单面单图片

        Args:
            output_dir: 输出目录路径

        Returns:
            (file_path, field_dict)
        """
        # 随机选择南昌市大区
        district = random.choice(SimPackageGenerator.DISTRICTS)
        province = "江西"
        city = "南昌市"
        # 从对应大区的道路中随机选一条
        road = random.choice(SimPackageGenerator.DISTRICT_ADDRESS[district]["roads"])
        num = random.randint(1, 588)
        address = f"江西省南昌市{district}{road}{num}号"

        receiver_name = SimPackageGenerator._random_name()
        phone = SimPackageGenerator._random_phone()
        tracking_number = SimPackageGenerator._random_tracking_number()

        fields = {
            "receiver_name": receiver_name,
            "phone": phone,
            "province": province,
            "city": city,
            "district": district,
            "length": round(random.uniform(20, 60), 1),
            "width": round(random.uniform(15, 45), 1),
            "height": round(random.uniform(10, 40), 1),
            "address": address,
            "tracking_number": tracking_number,
        }
        fields["volume"] = round(fields["length"] * fields["width"] * fields["height"], 1)

        # 创建白色画布
        img = Image.new("RGB", (SimPackageGenerator.IMAGE_WIDTH, SimPackageGenerator.IMAGE_HEIGHT), "white")
        draw = ImageDraw.Draw(img)

        # 字体准备
        font_title = SimPackageGenerator._get_font(24)
        font_text = SimPackageGenerator._get_font(18)
        font_small = SimPackageGenerator._get_font(14)
        font_bold = SimPackageGenerator._get_font(20)

        # 绘制边框线
        draw.rectangle([15, 15, SimPackageGenerator.IMAGE_WIDTH - 15, SimPackageGenerator.IMAGE_HEIGHT - 15],
                       outline="black", width=2)

        # 顶部标题栏
        draw.rectangle([16, 16, SimPackageGenerator.IMAGE_WIDTH - 16, 50], fill="#e8f0fe")
        draw.text((SimPackageGenerator.IMAGE_WIDTH // 2 - 80, 20),
                  "物流运单", font=font_title, fill="#1a3a6b")

        # 运单号
        draw.text((30, 65), f"运单号: {tracking_number}", font=font_bold, fill="#333")

        # 分隔线
        draw.line([(30, 95), (SimPackageGenerator.IMAGE_WIDTH - 30, 95)], fill="#ccc", width=1)

        # 收件人信息区域
        draw.text((30, 110), "【收件人信息】", font=font_bold, fill="#1a3a6b")
        draw.text((30, 142), f"姓名: {receiver_name}", font=font_text, fill="#333")
        draw.text((30, 172), f"电话: {phone}", font=font_text, fill="#333")

        # 地址
        draw.text((30, 202), f"地址: {address}", font=font_text, fill="#333")
        draw.text((30, 232), f"       {province}{city}{district}", font=font_text, fill="#555")

        # 分隔线
        draw.line([(30, 270), (SimPackageGenerator.IMAGE_WIDTH - 30, 270)], fill="#ccc", width=1)

        # 备注区
        draw.text((30, 285), "发件人: 南昌分拣中心", font=font_small, fill="#888")
        draw.text((30, 305), f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", font=font_small, fill="#888")

        # 包裹尺寸信息
        dims_text = f"包裹尺寸: {fields['length']}×{fields['width']}×{fields['height']} cm  体积: {fields['volume']} cm³"
        draw.text((30, 325), dims_text, font=font_small, fill="#1a3a6b")

        # 底部条码区域
        barcode_y = 355
        if HAS_BARCODE:
            try:
                code128 = barcode.get("code128", tracking_number, writer=ImageWriter())
                barcode_img = code128.render()
                # 缩放条码适应画布宽度
                barcode_w = SimPackageGenerator.IMAGE_WIDTH - 80
                barcode_h = int(barcode_img.height * barcode_w / barcode_img.width)
                barcode_img = barcode_img.resize((barcode_w, barcode_h), Image.LANCZOS)
                # 粘贴到画布底部
                barcode_x = (SimPackageGenerator.IMAGE_WIDTH - barcode_w) // 2
                img.paste(barcode_img, (barcode_x, barcode_y))
                # 条码下方文字
                draw.text((SimPackageGenerator.IMAGE_WIDTH // 2 - 100, barcode_y + barcode_h + 5),
                          tracking_number, font=font_small, fill="#333")
            except Exception as e:
                print(f"[SimGen] 条码生成失败: {e}")
                draw.text((30, barcode_y), f"[条码: {tracking_number}]", font=font_text, fill="red")
        else:
            draw.text((30, barcode_y), f"[条码: {tracking_number}]", font=font_text, fill="#666")

        # 保存
        now = datetime.now()
        date_dir = now.strftime("%Y-%m")
        abs_dir = Path(output_dir) / date_dir
        abs_dir.mkdir(parents=True, exist_ok=True)
        filename = f"sim_{uuid.uuid4().hex[:12]}.jpg"
        file_path = str(abs_dir / filename)
        img.save(file_path, "JPEG", quality=85)

        rel_path = f"{date_dir}/{filename}"
        return rel_path, fields

    @staticmethod
    def add_damage_effect(image_path: str, damage_type: str | None = None) -> str:
        """
        给已有图片添加破损/变形/渗漏等视觉异常效果
        返回 damage_type 字符串，用于配合 DamageDetector 检测
        """
        types = ["damage", "deformed", "leak", "stain"]
        if damage_type is None:
            damage_type = random.choice(types)

        img = Image.open(image_path).convert("RGB")
        w, h = img.size
        draw = ImageDraw.Draw(img)

        if damage_type == "damage":
            # 添加裂纹/破损：随机深色锯齿线条
            for _ in range(random.randint(3, 8)):
                x0 = random.randint(50, w - 50)
                y0 = random.randint(80, h - 80)
                points = [(x0, y0)]
                for _ in range(random.randint(4, 10)):
                    x0 += random.randint(-40, 40)
                    y0 += random.randint(-30, 30)
                    x0 = max(10, min(w - 10, x0))
                    y0 = max(10, min(h - 10, y0))
                    points.append((x0, y0))
                draw.line(points, fill=(30, 30, 30), width=random.randint(2, 5))
            # 添加暗色缺口
            for _ in range(random.randint(2, 5)):
                rx = random.randint(20, w - 80)
                ry = random.randint(20, h - 80)
                draw.ellipse([rx, ry, rx + random.randint(15, 50), ry + random.randint(10, 30)], fill=(20, 20, 20))

        elif damage_type == "deformed":
            # 变形：裁剪+拉伸部分区域
            for _ in range(random.randint(2, 4)):
                sx = random.randint(30, w - 100)
                sy = random.randint(30, h - 100)
                sw = random.randint(40, 120)
                sh = random.randint(30, 80)
                region = img.crop((sx, sy, sx + sw, sy + sh))
                # 拉伸变形
                region = region.resize((sw + random.randint(20, 60), sh + random.randint(10, 30)), Image.LANCZOS)
                img.paste(region, (sx, sy))

        elif damage_type == "leak":
            # 渗漏：大面积深色斑块
            for _ in range(random.randint(1, 3)):
                cx = random.randint(80, w - 80)
                cy = random.randint(100, h - 100)
                for _ in range(random.randint(8, 15)):
                    rx = cx + random.randint(-60, 60)
                    ry = cy + random.randint(-50, 50)
                    rr = random.randint(20, 50)
                    color = (random.randint(10, 40), random.randint(10, 40), random.randint(10, 40))
                    draw.ellipse([rx - rr, ry - rr, rx + rr, ry + rr], fill=color)

        elif damage_type == "stain":
            # 污渍：黄褐色不规则斑点
            for _ in range(random.randint(6, 12)):
                sx = random.randint(30, w - 60)
                sy = random.randint(50, h - 60)
                sr = random.randint(15, 40)
                color = (random.randint(80, 160), random.randint(50, 120), random.randint(10, 60))
                draw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=color)

        img.save(image_path, "JPEG", quality=85)
        return damage_type

    @staticmethod
    def _add_scribble(image_path: str):
        """在图片上添加随机涂鸦线条（模拟人为污损）"""
        try:
            img = Image.open(image_path).convert("RGB")
            draw = ImageDraw.Draw(img)
            w, h = img.size
            # 随机数量黑色/深色涂鸦线条
            for _ in range(random.randint(5, 25)):
                color = random.choice([(0,0,0), (30,30,30), (60,60,60), (10,10,10)])
                x0, y0 = random.randint(0, w), random.randint(0, h)
                pts = [(x0, y0)]
                for _ in range(random.randint(3, 12)):
                    x0 = max(5, min(w-5, x0 + random.randint(-80, 80)))
                    y0 = max(5, min(h-5, y0 + random.randint(-50, 50)))
                    pts.append((x0, y0))
                draw.line(pts, fill=color, width=random.randint(1, 5))
            # 随机墨点
            for _ in range(random.randint(3, 15)):
                rx = random.randint(10, w-10)
                ry = random.randint(10, h-10)
                r = random.randint(3, 20)
                draw.ellipse([rx-r, ry-r, rx+r, ry+r], fill=(5,5,5))
            img.save(image_path, "JPEG", quality=85)
        except Exception:
            pass

    @staticmethod
    def batch_generate(count: int, output_dir: str) -> list:
        """批量生成模拟包裹图片
        Returns:
            [(rel_path, field_dict), ...]
        """
        results = []
        for i in range(count):
            rel_path, fields = SimPackageGenerator.generate(output_dir)
            results.append((rel_path, fields))
        return results
