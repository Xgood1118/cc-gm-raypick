# -*- coding: utf-8 -*-
"""BVH（层次包围盒）加速结构，仅使用 Python 标准库。

构建与遍历都是确定性的：

* 构建按三角形在盒子中的排列顺序递归划分，分裂轴取包围盒最长轴，
  分裂点取质心坐标的中位数（偶数时取前中位，配合稳定排序）；
* 遍历采用显式栈，近子树优先；最终最近命中的选择规则与遍历顺序无关
  （见 ``core._traverse``）。
"""

from dataclasses import dataclass, field

from .geom import EPS, vcross, vnorm1, vsub

#: 叶子节点最多容纳的三角形数。
LEAF_SIZE = 4


def is_degenerate(tri):
    """三角形两条边共线（叉积接近零）即退化。阈值为相对容差。"""
    e1 = vsub(tri.b, tri.a)
    e2 = vsub(tri.c, tri.a)
    return vnorm1(vcross(e1, e2)) <= EPS * vnorm1(e1) * vnorm1(e2)


@dataclass
class Box:
    """轴对齐包围盒。"""
    lo: tuple
    hi: tuple

    @classmethod
    def empty(cls):
        inf = float("inf")
        return cls((inf, inf, inf), (-inf, -inf, -inf))

    def add_point(self, p):
        self.lo = (min(self.lo[0], p[0]), min(self.lo[1], p[1]),
                   min(self.lo[2], p[2]))
        self.hi = (max(self.hi[0], p[0]), max(self.hi[1], p[1]),
                   max(self.hi[2], p[2]))

    def union(self, other):
        return Box(
            (
                min(self.lo[0], other.lo[0]),
                min(self.lo[1], other.lo[1]),
                min(self.lo[2], other.lo[2]),
            ),
            (
                max(self.hi[0], other.hi[0]),
                max(self.hi[1], other.hi[1]),
                max(self.hi[2], other.hi[2]),
            ),
        )

    def centroid(self):
        return (
            (self.lo[0] + self.hi[0]) * 0.5,
            (self.lo[1] + self.hi[1]) * 0.5,
            (self.lo[2] + self.hi[2]) * 0.5,
        )

    def longest_axis(self):
        ext = (
            self.hi[0] - self.lo[0],
            self.hi[1] - self.lo[1],
            self.hi[2] - self.lo[2],
        )
        return 0 if ext[0] >= ext[1] and ext[0] >= ext[2] else (
            1 if ext[1] >= ext[2] else 2
        )


def tri_box(tri):
    box = Box.empty()
    for p in (tri.a, tri.b, tri.c):
        box.add_point(p)
    return box


@dataclass
class Node:
    """BVH 节点。叶子节点 ``tris`` 非空，内部节点 ``children`` 非空。"""
    box: Box
    leaf: bool
    tris: list = field(default_factory=list)
    children: list = field(default_factory=list)


class BVH:
    """三角形集合上的 BVH。"""

    def __init__(self, root, degenerate_count):
        self.root = root
        self.degenerate_count = degenerate_count

    @classmethod
    def build(cls, tris):
        degenerates = sum(1 for t in tris if is_degenerate(t))
        if not tris:
            return cls(Node(Box.empty(), leaf=True, tris=[]), degenerates)
        root = cls._build(list(tris))
        return cls(root, degenerates)

    @classmethod
    def _build(cls, tris):
        box = Box.empty()
        for t in tris:
            box = box.union(tri_box(t))

        if len(tris) <= LEAF_SIZE:
            return Node(box=box, leaf=True, tris=tris)

        axis = box.longest_axis()
        # 稳定排序：质心相同时保持输入顺序，构建过程确定。
        ordered = sorted(
            tris,
            key=lambda t: tri_box(t).centroid()[axis],
        )
        mid = len(ordered) // 2
        left = cls._build(ordered[:mid])
        right = cls._build(ordered[mid:])
        return Node(
            box=left.box.union(right.box),
            leaf=False,
            children=[left, right],
        )

    def hit_aabb(self, ray, box):
        """slab 法射线-包围盒求交，仅返回是否相交。

        零方向分量对应轴只检查起点是否落在该轴区间内。
        """
        ox, oy, oz = ray.origin
        dx, dy, dz = ray.direction
        origin = (ox, oy, oz)
        direction = (dx, dy, dz)

        t_lo = -float("inf")
        t_hi = float("inf")
        for axis in range(3):
            d = direction[axis]
            if d == 0.0:
                if origin[axis] < box.lo[axis] or origin[axis] > box.hi[axis]:
                    return False
                continue
            t1 = (box.lo[axis] - origin[axis]) / d
            t2 = (box.hi[axis] - origin[axis]) / d
            if t1 > t2:
                t1, t2 = t2, t1
            if t1 > t_lo:
                t_lo = t1
            if t2 < t_hi:
                t_hi = t2
            if t_lo > t_hi:
                return False
        # 只关心射线正向（t > 0）的相交。
        return t_hi > 0.0

    def order_children(self, ray, node):
        """按起点到两个子包围盒的距离返回 (近, 远)。

        距离取起点到盒子中心的欧氏距离；完全相等时保持构建顺序，
        保证确定性。
        """
        left, right = node.children

        def dist(box):
            c = box.centroid()
            o = ray.origin
            return (
                (c[0] - o[0]) ** 2
                + (c[1] - o[1]) ** 2
                + (c[2] - o[2]) ** 2
            )

        dl, dr = dist(left.box), dist(right.box)
        if dl <= dr:
            return left, right
        return right, left
