"""
蚁群算法路径规划 — 南昌本地分区配送
基于南昌市5大行政区真实经纬度进行区内最短路径规划
"""
import math
import random
from dataclasses import dataclass, field


# ===== 南昌市6大行政区坐标（高德地图） =====
DISTRICT_COORDS = {
    "南昌": (115.8582, 28.6829),       # 分拣中心（起点）
    "东湖区": (115.8891, 28.6850),
    "西湖区": (115.8777, 28.6571),
    "青云谱区": (115.9258, 28.6214),
    "青山湖区": (115.9620, 28.6820),
    "新建区": (115.8150, 28.6920),
    "红谷滩区": (115.8582, 28.6982),
}


@dataclass
class City:
    name: str
    lng: float
    lat: float


@dataclass
class RouteResult:
    path: list   # 城市名列表（有序）
    total_distance_km: float
    iterations: int
    waypoints: list = field(default_factory=list)  # [(lng, lat, name), ...]
    distance_matrix: list = field(default_factory=list)
    convergence: list = field(default_factory=list)


def haversine(lng1, lat1, lng2, lat2):
    """计算两个经纬度之间的地球表面距离(km)"""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def aco_tsp(
    cities: list,
    n_ants: int = 30,
    n_iterations: int = 100,
    alpha: float = 1.0,   # 信息素重要度
    beta: float = 2.0,    # 启发因子重要度
    rho: float = 0.1,     # 信息素挥发率
    Q: float = 100,       # 信息素强度
) -> RouteResult:
    """
    蚁群算法求解TSP路径规划
    cities: [City(name, lng, lat), ...]
    """
    n = len(cities)
    if n < 2:
        return RouteResult(path=[c.name for c in cities], total_distance_km=0, iterations=0)

    # 构建距离矩阵
    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                dist[i][j] = haversine(
                    cities[i].lng, cities[i].lat,
                    cities[j].lng, cities[j].lat,
                )

    # 启发因子 = 1/距离
    eta = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j and dist[i][j] > 0:
                eta[i][j] = 1.0 / dist[i][j]

    # 信息素矩阵初始化
    tau = [[1.0] * n for _ in range(n)]

    best_path = None
    best_dist = float('inf')
    convergence = []

    for iteration in range(n_iterations):
        ant_paths = []
        ant_dists = []

        for ant in range(n_ants):
            unvisited = set(range(n))
            start = random.randint(0, n - 1)
            unvisited.discard(start)
            path = [start]
            current = start

            while unvisited:
                # 轮盘赌选择下一城市
                probs = []
                total_prob = 0
                for j in unvisited:
                    p = (tau[current][j] ** alpha) * (eta[current][j] ** beta)
                    probs.append((j, p))
                    total_prob += p

                if total_prob == 0:
                    choice = min(unvisited)
                else:
                    r = random.random() * total_prob
                    cumulative = 0
                    choice = None
                    for j, p in probs:
                        cumulative += p
                        if cumulative >= r:
                            choice = j
                            break
                    if choice is None:
                        choice = probs[-1][0]

                path.append(choice)
                unvisited.discard(choice)
                current = choice

            # 计算路径总距离
            total = 0
            for k in range(n - 1):
                total += dist[path[k]][path[k + 1]]
            total += dist[path[-1]][path[0]]  # 回到起点

            ant_paths.append(path)
            ant_dists.append(total)

            if total < best_dist:
                best_dist = total
                best_path = path[:]

        convergence.append(best_dist)

        # 信息素全局更新
        for i in range(n):
            for j in range(n):
                tau[i][j] *= (1 - rho)

        for path, d in zip(ant_paths, ant_dists):
            if d > 0:
                delta = Q / d
                for k in range(n - 1):
                    tau[path[k]][path[k + 1]] += delta
                tau[path[-1]][path[0]] += delta

    # 构建返回结果
    if best_path is None:
        best_path = list(range(n))

    # 【强制】旋转路径使 南昌（分拣中心，index 0）始终在第一位
    if 0 in best_path:
        idx = best_path.index(0)
        if idx != 0:
            best_path = best_path[idx:] + best_path[:idx]

    ordered_cities = [cities[i] for i in best_path]
    waypoints = [(c.lng, c.lat, c.name) for c in ordered_cities]

    return RouteResult(
        path=[c.name for c in ordered_cities],
        total_distance_km=round(best_dist, 2),
        iterations=n_iterations,
        waypoints=waypoints,
        distance_matrix=[[round(d, 1) for d in row] for row in dist],
        convergence=[round(v, 2) for v in convergence],
    )
