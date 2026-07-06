"""
3D装箱算法 — 基于First Fit Decreasing Height + 三维旋转
根据包裹长宽高尺寸，计算最优装载方案
"""
import random
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Package:
    id: str
    tracking_number: str
    l: float  # 长 cm
    w: float  # 宽 cm
    h: float  # 高 cm
    volume: float = 0
    weight: float = 0

    def __post_init__(self):
        self.volume = self.l * self.w * self.h


@dataclass
class PlacedPackage:
    pkg: Package
    x: float  # 放置坐标
    y: float
    z: float
    rotation: str  # 旋转方式: lwh, lhw, wlh, whl, hlw, hwl
    l_used: float  # 摆放后实际占用的长
    w_used: float  # 摆放后实际占用的宽
    h_used: float  # 摆放后实际占用的高


@dataclass
class LoadResult:
    vehicle_size: dict
    placed: list = field(default_factory=list)
    unplaced: list = field(default_factory=list)
    fill_rate: float = 0
    total_volume: float = 0
    used_volume: float = 0


class BinPacker3D:
    """三维装箱优化器"""

    # 六种旋转方式：(长,宽,高)
    ROTATIONS = [
        ("lwh", lambda p: (p.l, p.w, p.h)),
        ("lhw", lambda p: (p.l, p.h, p.w)),
        ("wlh", lambda p: (p.w, p.l, p.h)),
        ("whl", lambda p: (p.w, p.h, p.l)),
        ("hlw", lambda p: (p.h, p.l, p.w)),
        ("hwl", lambda p: (p.h, p.w, p.l)),
    ]

    def __init__(self, container_l: float, container_w: float, container_h: float):
        self.cL = container_l
        self.cW = container_w
        self.cH = container_h
        self.used_spaces = []  # [(x,y,z, l,w,h)] 已占用空间

    def _can_place(self, x: float, y: float, z: float, l: float, w: float, h: float) -> bool:
        """检查某位置是否可放置"""
        if x + l > self.cL or y + w > self.cW or z + h > self.cH:
            return False
        for ux, uy, uz, ul, uw, uh in self.used_spaces:
            if (x < ux + ul and x + l > ux and
                y < uy + uw and y + w > uy and
                z < uz + uh and z + h > uz):
                return False
        return True

    def find_best_placement(self, pkg: Package) -> Optional[PlacedPackage]:
        """遍历所有位置和旋转，找最佳放置位置（最低最左最前）"""
        best = None

        for rot_name, rot_fn in self.ROTATIONS:
            dl, dw, dh = rot_fn(pkg)
            if dl > self.cL or dw > self.cW or dh > self.cH:
                continue

            # 遍历所有可能的 z > y > x (bottom-up, front-to-back)
            found = False
            for z in self._candidate_z():
                if z + dh > self.cH:
                    continue
                for y in self._candidate_y(z):
                    if y + dw > self.cW:
                        continue
                    for x in self._candidate_x(y, z):
                        if x + dl > self.cL:
                            continue
                        if self._can_place(x, y, z, dl, dw, dh):
                            found = True
                            break
                    if found:
                        break
                if found:
                    break

            if found:
                candidate = PlacedPackage(
                    pkg=pkg, x=x, y=y, z=z,
                    rotation=rot_name,
                    l_used=dl, w_used=dw, h_used=dh,
                )
                if best is None:
                    best = candidate
                else:
                    # 选择更低、更靠前的
                    if (candidate.z, candidate.y, candidate.x) < (best.z, best.y, best.x):
                        best = candidate

        return best

    def _candidate_z(self):
        """候选 z 坐标（基于已放置包裹的顶部）"""
        levels = {0}
        for _, _, uz, _, _, uh in self.used_spaces:
            levels.add(uz + uh)
        return sorted(levels)

    def _candidate_y(self, current_z: float):
        """候选 y 坐标"""
        positions = {0}
        for _, uy, uz, _, uw, uh in self.used_spaces:
            if uz <= current_z < uz + uh or current_z < uz:
                positions.add(uy + uw)
        return sorted(positions)

    def _candidate_x(self, current_y: float, current_z: float):
        """候选 x 坐标"""
        positions = {0}
        for ux, uy, uz, ul, uw, uh in self.used_spaces:
            if uy <= current_y < uy + uw and uz <= current_z < uz + uh:
                positions.add(ux + ul)
        return sorted(positions)

    def place(self, pkg: Package) -> Optional[PlacedPackage]:
        """放置一个包裹"""
        placement = self.find_best_placement(pkg)
        if placement:
            self.used_spaces.append((
                placement.x, placement.y, placement.z,
                placement.l_used, placement.w_used, placement.h_used,
            ))
        return placement

    def get_used_volume(self) -> float:
        return sum(l * w * h for _, _, _, l, w, h in self.used_spaces)


def pack_packages(packages: list, vehicle_size: dict | None = None) -> LoadResult:
    """
    对包裹列表进行3D装箱优化
    vehicle_size: {"length": 420, "width": 230, "height": 220} (cm) 4.2m货车
    """
    if vehicle_size is None:
        vehicle_size = {"length": 420, "width": 230, "height": 220}

    packer = BinPacker3D(
        vehicle_size["length"],
        vehicle_size["width"],
        vehicle_size["height"],
    )

    vehicle_volume = packer.cL * packer.cW * packer.cH

    # 按体积降序排列（FFD策略）
    sorted_pkgs = sorted(packages, key=lambda p: p.volume, reverse=True)

    placed = []
    unplaced = []

    for pkg in sorted_pkgs:
        result = packer.place(pkg)
        if result:
            placed.append(result)
        else:
            unplaced.append(pkg)

    used_volume = packer.get_used_volume()
    fill_rate = round(used_volume / vehicle_volume * 100, 1)

    return LoadResult(
        vehicle_size=vehicle_size,
        placed=placed,
        unplaced=unplaced,
        fill_rate=fill_rate,
        total_volume=vehicle_volume,
        used_volume=used_volume,
    )
