"""模块10：路径优化与装载规划 — 遗传算法 + 蚁群算法 + 3D装箱"""
import numpy as np
import random, math
from typing import List, Dict, Tuple

# 南昌市6大行政区坐标（高德地图）+ 分拣中心
PROV_GEO = {
    "南昌": (115.8582, 28.6829),       # 分拣中心（起点）
    "东湖区": (115.8891, 28.6850),
    "西湖区": (115.8777, 28.6571),
    "青云谱区": (115.9258, 28.6214),
    "青山湖区": (115.9620, 28.6820),
    "新建区": (115.8150, 28.6920),
    "红谷滩区": (115.8582, 28.6982),
}

# 默认起点：南昌分拣中心
DEFAULT_DEPOT = (115.8582, 28.6829)

# 标准物流车厢：2.4m×1.2m×2.0m = 5760000 cm³
VEHICLE_DIMS = (240, 120, 200)


def _geo_distance(p1, p2):
    """基于经纬度计算真实地理距离(km)，使用 Haversine 公式"""
    R = 6371
    lon1, lat1 = math.radians(p1[0]), math.radians(p1[1])
    lon2, lat2 = math.radians(p2[0]), math.radians(p2[1])
    a = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return round(R * 2 * math.asin(math.sqrt(a)), 1)


class RouteOptimizer:

    # ==================== 遗传算法：装载方案组合优化 ====================
    @staticmethod
    def ga_pack(packages: List[Dict], vehicle_dims: Tuple[int,int,int] = VEHICLE_DIMS,
                generations: int = 200, pop_size: int = 80) -> dict:
        """遗传算法：寻找最优装箱顺序以最大化车辆填充率"""
        if len(packages) < 2:
            filled, fill_rate, vol = RouteOptimizer._fill_vehicle(packages, vehicle_dims)
            return {"bins_used": 1, "fill_rate": fill_rate, "filled_packages": len(filled),
                    "total_packages": len(packages), "order": [p["id"] for p in packages]}

        W, D, H = vehicle_dims
        n = len(packages)

        def create_individual():
            return random.sample(range(n), n)

        def fitness(ind):
            ordered = [packages[i] for i in ind]
            filled, fill_rate, _ = RouteOptimizer._fill_vehicle(ordered, vehicle_dims)
            return fill_rate / 100 * 1000 + len(filled) * 10  # 填充率为主，数量为辅

        population = [create_individual() for _ in range(pop_size)]
        best_ind, best_fitness = None, -1

        for gen in range(generations):
            scored = [(ind, fitness(ind)) for ind in population]
            scored.sort(key=lambda x: x[1], reverse=True)
            if scored[0][1] > best_fitness:
                best_fitness, best_ind = scored[0][1], scored[0][0][:]

            elite = [ind for ind, _ in scored[:pop_size // 2]]
            new_pop = elite[:]
            while len(new_pop) < pop_size:
                p1, p2 = random.sample(elite, 2)
                child = p1[:n//2] + [x for x in p2 if x not in p1[:n//2]]
                if random.random() < 0.15:
                    i, j = random.sample(range(n), 2)
                    child[i], child[j] = child[j], child[i]
                new_pop.append(child)
            population = new_pop

        ordered = [packages[i] for i in best_ind]
        filled, fill_rate, used_vol = RouteOptimizer._fill_vehicle(ordered, vehicle_dims)
        return {
            "bins_used": 1,
            "fill_rate": fill_rate,
            "filled_packages": len(filled),
            "total_packages": len(packages),
            "used_volume_l": round(used_vol / 1000, 1),
            "total_volume_l": round((W*D*H)/1000, 1),
            "order": [p["id"] for p in filled],
            "generations": generations,
        }

    @staticmethod
    def _fill_vehicle(packages: List[Dict], vehicle_dims: Tuple[int,int,int]):
        """贪心填充：按体积降序逐个放入车厢，校验每个包裹尺寸"""
        W, D, H = vehicle_dims
        sorted_pkgs = sorted(packages, key=lambda p: p.get("w",0)*p.get("d",0)*p.get("h",0), reverse=True)
        filled = []
        used_vol = 0
        # 简化空间追踪：用放置坐标追踪
        spaces = [(0, 0, 0, W, D, H)]  # (x, y, z, w, d, h) 可用空间

        for pkg in sorted_pkgs:
            pw, pd, ph = pkg.get("w", 0), pkg.get("d", 0), pkg.get("h", 0)
            if pw <= 0 or pd <= 0 or ph <= 0:
                continue
            # 校验单件不超过车厢
            if pw > W or pd > D or ph > H:
                continue

            placed = False
            for si, (sx, sy, sz, sw, sd, sh) in enumerate(spaces):
                if pw <= sw and pd <= sd and ph <= sh:
                    filled.append(pkg)
                    used_vol += pw * pd * ph
                    # 切分剩余空间
                    new_spaces = []
                    # 右侧剩余
                    if sw - pw > 1:
                        new_spaces.append((sx + pw, sy, sz, sw - pw, sd, sh))
                    # 前方剩余
                    if sd - pd > 1:
                        new_spaces.append((sx, sy + pd, sz, pw if sw-pw<=1 else sw, sd - pd, sh))
                    # 上方剩余
                    if sh - ph > 1:
                        new_spaces.append((sx, sy, sz + ph, sw, sd, sh - ph))
                    spaces.pop(si)
                    spaces.extend(new_spaces)
                    placed = True
                    break
            if not placed:
                # 尝试旋转放置
                for (rw, rd, rh) in [(pw,pd,ph), (pw,ph,pd), (pd,pw,ph), (pd,ph,pw), (ph,pw,pd), (ph,pd,pw)]:
                    for si, (sx, sy, sz, sw, sd, sh) in enumerate(spaces):
                        if rw <= sw and rd <= sd and rh <= sh:
                            filled.append({**pkg, "w": rw, "d": rd, "h": rh})
                            used_vol += rw * rd * rh
                            new_spaces = []
                            if sw - rw > 1: new_spaces.append((sx+rw, sy, sz, sw-rw, sd, sh))
                            if sd - rd > 1: new_spaces.append((sx, sy+rd, sz, rw if sw-rw<=1 else sw, sd-rd, sh))
                            if sh - rh > 1: new_spaces.append((sx, sy, sz+rh, sw, sd, sh-rh))
                            spaces.pop(si); spaces.extend(new_spaces)
                            placed = True
                            break
                    if placed: break

        total_vol = W * D * H
        fill_rate = round(used_vol / total_vol * 100, 1) if total_vol > 0 else 0
        return filled, fill_rate, used_vol

    # ==================== 蚁群算法：真实地理路径规划 ====================
    @staticmethod
    def aco_route_real(destinations: List[Dict], depot_coords: Tuple = (115.8582, 28.6829),
                       iterations: int = 100, ants: int = 30) -> dict:
        """蚁群算法：基于真实经纬度计算配送路径"""
        if len(destinations) < 2:
            return {"route": destinations, "total_distance_km": 0, "iterations": 0}

        points = [depot_coords] + [(d.get("lng",0), d.get("lat",0)) for d in destinations]
        n = len(points)

        # 真实距离矩阵（公里）
        dists = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                dists[i][j] = _geo_distance(points[i], points[j]) if i != j else 0

        pheromones = np.ones((n, n)) * 0.1
        alpha, beta, rho = 1.0, 2.0, 0.15
        best_route, best_dist = None, float("inf")

        for _ in range(iterations):
            for _ in range(ants):
                visited, unvisited = [0], set(range(1, n))
                while unvisited:
                    cur = visited[-1]
                    probs = [(pheromones[cur][j]**alpha * (1/max(dists[cur][j],0.01))**beta) for j in range(n) if j in unvisited]
                    if sum(probs) == 0:
                        nxt = random.choice(list(unvisited))
                    else:
                        probs = [p/sum(probs) for p in probs]
                        nxt = random.choices(list(unvisited), weights=probs)[0]
                    visited.append(nxt); unvisited.remove(nxt)
                visited.append(0)
                td = sum(dists[visited[i]][visited[i+1]] for i in range(len(visited)-1))
                if td < best_dist:
                    best_dist, best_route = td, visited[:]

            pheromones *= (1 - rho)
            for _ in range(ants):
                for i in range(len(best_route)-1):
                    pheromones[best_route[i]][best_route[i+1]] += 1.0 / max(best_dist, 0.1)

        route_info = []
        for i, idx in enumerate(best_route[1:-1] if best_route else [], 1):
            d = destinations[idx-1]
            route_info.append({
                "id": d.get("id", idx), "name": d.get("name", ""),
                "coords": points[idx], "demand": d.get("demand", 0),
                "order": i
            })

        return {
            "route": route_info,
            "total_distance_km": round(best_dist, 1),
            "iterations": iterations,
        }

    # ==================== 3D装载：固定车厢+精准校验 ====================
    @staticmethod
    def pack_bins(packages: List[Dict], container_dims: Tuple[int,int,int] = VEHICLE_DIMS) -> dict:
        """3D装箱：固定车厢(240×120×200cm)，校验每个包裹尺寸"""
        W, D, H = container_dims
        valid_pkgs = []  # 可以放入车厢的包裹
        oversized = []   # 超出车厢的包裹

        for p in packages:
            pw, pd_, ph = p.get("w",0), p.get("d",0), p.get("h",0)
            if pw <= 0 or pd_ <= 0 or ph <= 0:
                continue
            if pw > W or pd_ > D or ph > H:
                oversized.append({"id": p["id"], "dim": f"{pw}×{pd_}×{ph}", "reason": "超车厢尺寸"})
                continue
            valid_pkgs.append(p)

        # 调用 GA 优化装载
        if len(valid_pkgs) >= 2:
            result = RouteOptimizer.ga_pack(valid_pkgs, container_dims, generations=200, pop_size=80)
        else:
            result = RouteOptimizer.ga_pack(valid_pkgs, container_dims, generations=1, pop_size=1)

        result["vehicle"] = f"{W}×{D}×{H}cm"
        result["total_packages"] = len(packages)
        result["valid_packages"] = len(valid_pkgs)
        result["oversized"] = oversized
        result["target_utilization"] = ">= 95%" if result.get("fill_rate", 0) >= 95 else "装载率待提升"
        return result

    # ==================== 保留兼容旧API ====================
    @staticmethod
    def ga_optimize(packages: List[Dict], vehicle_capacity: int, generations: int = 100, pop_size: int = 50) -> dict:
        """遗传算法优化装车顺序（旧API兼容）"""
        if len(packages) < 2:
            return {"order": [p["id"] for p in packages], "fitness": 1.0, "vehicles_required": 1,
                    "load_rate_percent": 100, "generations": generations}
        n = len(packages)
        def create_individual():
            return random.sample([p["id"] for p in packages], n)
        def fitness(ind):
            om = {p["id"]: p for p in packages}
            s = sum(10 if om[ind[i]].get("destination")==om[ind[i+1]].get("destination") else 0 for i in range(len(ind)-1))
            return s
        pop = [create_individual() for _ in range(pop_size)]
        best, bf = None, -1
        for _ in range(generations):
            sc = sorted([(i, fitness(i)) for i in pop], key=lambda x: x[1], reverse=True)
            if sc[0][1] > bf: bf, best = sc[0][1], sc[0][0][:]
            el = [i for i, _ in sc[:pop_size//2]]
            npop = el[:]
            while len(npop) < pop_size:
                p1, p2 = random.sample(el, 2)
                ch = p1[:n//2] + [x for x in p2 if x not in p1[:n//2]]
                if random.random() < 0.1:
                    i, j = random.sample(range(n), 2); ch[i], ch[j] = ch[j], ch[i]
                npop.append(ch)
            pop = npop
        nv = max(1, (n+vehicle_capacity-1)//vehicle_capacity)
        return {"order": best, "fitness": bf, "vehicles_required": nv,
                "load_rate_percent": round(min(100, n/(nv*vehicle_capacity)*100),1), "generations": generations}

    @staticmethod
    def aco_optimize(depot: Tuple, destinations: List[Dict], iterations: int = 50, ants: int = 20) -> dict:
        """蚁群算法（旧API兼容）"""
        if not destinations: return {"route": [], "total_distance": 0, "iterations": 0}
        pts = [depot] + [d["coords"] for d in destinations]
        n = len(pts)
        dists = np.zeros((n,n))
        for i in range(n):
            for j in range(n):
                dists[i][j] = np.sqrt((pts[i][0]-pts[j][0])**2+(pts[i][1]-pts[j][1])**2)
        ph = np.ones((n,n))*0.1; br, bd = None, float("inf")
        for _ in range(iterations):
            for _ in range(ants):
                v, uv = [0], set(range(1,n))
                while uv:
                    c = v[-1]
                    ps = [(ph[c][j]**1.0*(1/max(dists[c][j],0.01))**2.0) for j in range(n) if j in uv]
                    nxt = random.choices(list(uv), weights=[p/sum(ps) for p in ps])[0] if sum(ps)>0 else random.choice(list(uv))
                    v.append(nxt); uv.remove(nxt)
                v.append(0); td = sum(dists[v[i]][v[i+1]] for i in range(len(v)-1))
                if td < bd: bd, br = td, v[:]
            ph *= 0.9
            for _ in range(ants):
                for i in range(len(br)-1): ph[br[i]][br[i+1]] += 1.0/max(bd,0.01)
        return {"route": [{"id": -1 if i==0 else destinations[i-1]["id"], "coords": pts[i]} for i in br] if br else [],
                "total_distance": round(bd,2), "iterations": iterations}
