# -*- coding: utf-8 -*-
"""批量射线拾取。

仅使用 Python 标准库。

求交规则（详见 README）：

* 退化三角形（三条边共线 / 面积接近 0）直接判定为未命中，原因
  ``degenerate``；
* 射线与三角形所在平面平行时未命中，原因 ``parallel``；
* 三角形按双面材质处理：正面、背面命中都返回，不做背面剔除，
  命中结果用 ``face`` 字段（``front`` / ``back``）标明朝向；
* 命中距离 ``t`` 必须为正（大于相对容差），起点落在三角形平面内时
  ``t == 0``，按未命中处理并给出原因 ``behind``，结果确定；
* 坐标参数 ``u、v`` 必须满足 ``u >= 0、v >= 0、u + v <= 1``（边界容差
  ``EPS``），否则视为未命中，原因 ``outside``。
"""

from dataclasses import dataclass

from .bvh import BVH, is_degenerate
from .geom import EPS, vcross, vdot, vnorm1, vsub

__all__ = [
    "Ray",
    "Triangle",
    "Hit",
    "intersect",
    "pick_all",
    "is_degenerate",
    "EPS",
]


@dataclass
class Ray:
    """射线，``origin`` 为起点，``direction`` 为方向向量（无需归一化）。"""
    origin: tuple
    direction: tuple


@dataclass
class Triangle:
    """三角形，``index`` 为三角形编号，``a/b/c`` 为三个顶点。"""
    index: int
    a: tuple
    b: tuple
    c: tuple


@dataclass
class Hit:
    """单次命中结果。"""
    tri: int
    t: float
    point: tuple
    u: float
    v: float


def intersect(ray, tri):
    """射线与单个三角形求交（Möller–Trumbore 算法）。

    返回 dict：

    * 命中：``{"hit": True, "tri": 编号, "t": 距离, "point": 交点,
      "u": ..., "v": ..., "face": "front"|"back"}``；
    * 未命中：``{"hit": False, "tri": 编号, "reason": 原因}``，
      原因取值为 ``degenerate`` / ``parallel`` / ``outside`` /
      ``behind``。

    判定使用相对容差：平行与退化的阈值是 ``EPS`` 乘以参与向量的
    L1 长度，因此极短射线、小三角形不会被误判为平行或退化。
    """
    o = ray.origin
    d = ray.direction
    a, b, c = tri.a, tri.b, tri.c

    e1 = vsub(b, a)
    e2 = vsub(c, a)

    # 退化三角形：两条边共线（叉积接近零）。
    if vnorm1(vcross(e1, e2)) <= EPS * vnorm1(e1) * vnorm1(e2):
        return {"hit": False, "tri": tri.index, "reason": "degenerate"}

    pvec = vcross(d, e2)
    det = vdot(e1, pvec)

    # 平行：射线方向与三角形平面法向接近垂直。
    if abs(det) <= EPS * vnorm1(e1) * vnorm1(pvec):
        return {"hit": False, "tri": tri.index, "reason": "parallel"}

    # 双面材质：det > 0 为正面命中，det < 0 为背面命中，均返回。
    face = "front" if det > 0.0 else "back"
    inv_det = 1.0 / det

    svec = vsub(o, a)
    u = vdot(svec, pvec) * inv_det
    if u < -EPS or u > 1.0 + EPS:
        return {"hit": False, "tri": tri.index, "reason": "outside"}

    qvec = vcross(svec, e1)
    v = vdot(d, qvec) * inv_det
    if v < -EPS or (u + v) > 1.0 + EPS:
        return {"hit": False, "tri": tri.index, "reason": "outside"}

    t = vdot(e2, qvec) * inv_det

    # 命中距离必须为正：t == 0（起点在三角形平面内）按 behind 处理，
    # 不返回命中，结果确定、可复现。阈值随射线与三角形尺度缩放。
    if t <= EPS * max(1.0, vnorm1(d), vnorm1(e2)):
        return {"hit": False, "tri": tri.index, "reason": "behind"}

    point = (
        o[0] + d[0] * t,
        o[1] + d[1] * t,
        o[2] + d[2] * t,
    )
    return {
        "hit": True,
        "tri": tri.index,
        "t": t,
        "point": point,
        "u": u,
        "v": v,
        "face": face,
    }


def pick_all(rays, tris):
    """批量拾取，每条射线只返回最近命中。

    返回 ``{"hits": [...], "stats": {...}}``：

    * ``hits`` 与 ``rays`` 等长、顺序一致。命中元素为
      ``{"ray": 序号, "tri": 三角形编号, "t": 距离, "point": 交点}``，
      未命中元素为 ``{"ray": 序号, "tri": None, "t": None}``；
    * 同距离时按三角形编号取小（先按 ``t`` 严格比较，``t`` 完全相等时
      取编号更小者），与 BVH 遍历顺序无关，结果稳定；
    * 零方向射线不做任何求交，直接记为未命中。

    ``stats`` 口径：

    * ``intersection_tests``：实际调用 :func:`intersect` 的次数
      （BVH 包围盒裁剪、零方向跳过均不计入）；
    * ``naive_tests``：全遍历基准次数，即有效射线数 × 三角形数；
    * ``speedup``：``naive_tests / intersection_tests``。
    """
    rays = list(rays)
    tris = list(tris)

    bvh = BVH.build(tris)
    total_tris = len(tris)

    hits = []
    tests = 0
    valid_rays = 0

    for ray_i, ray in enumerate(rays):
        dx, dy, dz = ray.direction

        # 零方向射线：方向向量严格为 (0, 0, 0)，结果确定为未命中，
        # 且不产生任何求交次数。
        if dx == 0.0 and dy == 0.0 and dz == 0.0:
            hits.append({"ray": ray_i, "tri": None, "t": None})
            continue

        valid_rays += 1
        best, n_tests = _traverse(bvh, ray)
        tests += n_tests

        if best is None:
            hits.append({"ray": ray_i, "tri": None, "t": None})
        else:
            hits.append({
                "ray": ray_i,
                "tri": best.tri,
                "t": best.t,
                "point": best.point,
            })

    naive = valid_rays * total_tris
    stats = {
        "rays": len(rays),
        "triangles": total_tris,
        "valid_rays": valid_rays,
        "zero_direction_rays": len(rays) - valid_rays,
        "degenerate_triangles": bvh.degenerate_count,
        "hits": sum(1 for h in hits if h["tri"] is not None),
        "intersection_tests": tests,
        "naive_tests": naive,
        "speedup": (naive / tests) if tests else 0.0,
        "tests_per_ray": (tests / valid_rays) if valid_rays else 0.0,
    }
    return {"hits": hits, "stats": stats}


def _traverse(bvh, ray):
    """遍历 BVH 收集最近命中，返回 (Hit|None, 求交次数)。

    同距离（``t`` 完全相等）时取三角形编号更小者。
    """
    best = None
    n_tests = 0
    stack = [bvh.root]

    while stack:
        node = stack.pop()
        if not bvh.hit_aabb(ray, node.box):
            continue
        if node.leaf:
            for tri in node.tris:
                n_tests += 1
                res = intersect(ray, tri)
                if not res["hit"]:
                    continue
                cand = Hit(
                    tri=res["tri"],
                    t=res["t"],
                    point=res["point"],
                    u=res["u"],
                    v=res["v"],
                )
                if best is None or cand.t < best.t or (
                    cand.t == best.t and cand.tri < best.tri
                ):
                    best = cand
        else:
            # 先压远节点、后压近节点，使近子树优先被处理；
            # 最终选择规则本身与遍历顺序无关，这里只为尽早裁剪。
            near, far = bvh.order_children(ray, node)
            stack.append(far)
            stack.append(near)

    return best, n_tests
