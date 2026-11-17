# -*- coding: utf-8 -*-
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import raypick as raypick  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------- 基础求交

def test_intersect_hit():
    r = raypick.Ray((0, 0, -5), (0, 0, 1))
    t = raypick.Triangle(0, (-1, -1, 0), (1, -1, 0), (0, 1, 0))
    hit = raypick.intersect(r, t)
    assert hit["hit"] is True
    assert abs(hit["t"] - 5.0) < 1e-6


def test_intersect_face_annotation_double_sided():
    """双面材质：同一三角形从两侧打都命中，face 字段标明朝向。"""
    tri = raypick.Triangle(0, (-1, -1, 0), (1, -1, 0), (0, 1, 0))
    back = raypick.intersect(raypick.Ray((0, 0, -5), (0, 0, 1)), tri)
    front = raypick.intersect(raypick.Ray((0, 0, 5), (0, 0, -1)), tri)
    assert back["hit"] is True and back["face"] == "back"
    assert front["hit"] is True and front["face"] == "front"
    assert abs(back["t"] - 5.0) < 1e-6 and abs(front["t"] - 5.0) < 1e-6


def test_intersect_parallel():
    """射线与三角形平面平行 -> 未命中，原因 parallel。"""
    r = raypick.Ray((0, 0, -5), (1, 0, 0))
    t = raypick.Triangle(0, (-1, -1, 0), (1, -1, 0), (0, 1, 0))
    out = raypick.intersect(r, t)
    assert out["hit"] is False
    assert out["reason"] == "parallel"


def test_intersect_degenerate():
    """三个顶点共线的退化三角形 -> 未命中，原因 degenerate。"""
    r = raypick.Ray((0, 0, -5), (0, 0, 1))
    t = raypick.Triangle(7, (0, 0, 0), (1, 0, 0), (2, 0, 0))
    out = raypick.intersect(r, t)
    assert out["hit"] is False
    assert out["reason"] == "degenerate"
    assert raypick.is_degenerate(t) is True


def test_intersect_outside():
    """射线穿过三角形所在平面但落在三角形外 -> outside。"""
    r = raypick.Ray((5, 5, -5), (0, 0, 1))
    t = raypick.Triangle(0, (-1, -1, 0), (1, -1, 0), (0, 1, 0))
    out = raypick.intersect(r, t)
    assert out["hit"] is False
    assert out["reason"] == "outside"


def test_intersect_origin_inside_triangle_is_behind():
    """起点在三角形平面内（t=0）不返回命中，原因 behind，结果确定。"""
    tri = raypick.Triangle(0, (-1, -1, 0), (1, -1, 0), (0, 1, 0))
    at_vertex = raypick.intersect(raypick.Ray((-1, -1, 0), (0, 0, 1)), tri)
    inside = raypick.intersect(raypick.Ray((0.0, 0.2, 0.0), (0, 0, 1)), tri)
    assert at_vertex["hit"] is False and at_vertex["reason"] == "behind"
    assert inside["hit"] is False and inside["reason"] == "behind"
    # 两次调用结果完全一致。
    assert raypick.intersect(
        raypick.Ray((0.0, 0.2, 0.0), (0, 0, 1)), tri
    ) == inside


def test_intersect_very_short_direction():
    """极短方向射线：距离按比例放大但交点不变，且不会被误判为平行。"""
    tri = raypick.Triangle(0, (-1, -1, 0), (1, -1, 0), (0, 1, 0))
    r = raypick.Ray((0, 0, -1e-10), (0, 0, 1e-12))
    out = raypick.intersect(r, tri)
    assert out["hit"] is True
    assert abs(out["t"] - 100.0) < 1e-9
    px, py, pz = out["point"]
    assert abs(px) < 1e-12 and abs(py) < 1e-12 and abs(pz) < 1e-12


# ---------------------------------------------------------------- 批量拾取

def _tri(index, cx, cy, size=1.0, z=0.0):
    """以 (cx, cy, z) 为一个顶点的直角三角形，覆盖 [cx, cx+size]² 左下三角。"""
    return raypick.Triangle(
        index,
        (cx, cy, z),
        (cx + size, cy, z),
        (cx, cy + size, z),
    )


def test_pick_all_returns_nearest():
    rays = [raypick.Ray((0, 0, -5), (0, 0, 1))]
    tris = [raypick.Triangle(0, (-1, -1, 0), (1, -1, 0), (0, 1, 0)),
            raypick.Triangle(1, (-1, -1, 2), (1, -1, 2), (0, 1, 2))]
    out = raypick.pick_all(rays, tris)
    assert out["hits"][0]["tri"] == 0


def test_pick_all_nearest_with_distance():
    """更近的三角形优先，即便它的编号更大。"""
    rays = [raypick.Ray((0.5, 0.5, -5), (0, 0, 1))]
    tris = [
        raypick.Triangle(0, (0, 0, 4), (2, 0, 4), (0, 2, 4)),
        raypick.Triangle(1, (0, 0, 1), (2, 0, 1), (0, 2, 1)),
    ]
    out = raypick.pick_all(rays, tris)
    assert out["hits"][0]["tri"] == 1
    assert abs(out["hits"][0]["t"] - 6.0) < 1e-9


def test_pick_all_tie_break_by_index_stable():
    """同距离时按三角形编号取小；颠倒输入顺序结果不变。"""
    ray = raypick.Ray((1, 1, -2), (0, 0, 1))
    tri0 = raypick.Triangle(0, (0, 0, 0), (2, 0, 0), (0, 2, 0))
    tri1 = raypick.Triangle(1, (0, 0, 0), (3, 0, 0), (0, 3, 0))

    out_ab = raypick.pick_all([ray], [tri0, tri1])
    out_ba = raypick.pick_all([ray], [tri1, tri0])
    assert out_ab["hits"][0]["tri"] == 0
    assert out_ba["hits"][0]["tri"] == 0
    assert abs(out_ab["hits"][0]["t"] - out_ba["hits"][0]["t"]) < 1e-12


def test_pick_all_zero_direction():
    """零方向射线确定未命中，且不产生任何求交次数。"""
    good = raypick.Ray((0, 0, -5), (0, 0, 1))
    zero = raypick.Ray((0, 0, 0), (0, 0, 0))
    tris = [raypick.Triangle(0, (-1, -1, 0), (1, -1, 0), (0, 1, 0))]

    out = raypick.pick_all([zero, good, zero], tris)
    assert out["hits"][0]["tri"] is None
    assert out["hits"][1]["tri"] == 0
    assert out["hits"][2]["tri"] is None
    stats = out["stats"]
    assert stats["zero_direction_rays"] == 2
    assert stats["valid_rays"] == 1
    # 只有 1 条有效射线、1 个三角形：求交次数恰为 1，零方向不计入。
    assert stats["intersection_tests"] == 1
    assert stats["naive_tests"] == 1

    # 直接对零方向射线做单次求交也有确定结果（平行）。
    single = raypick.intersect(zero, tris[0])
    assert single["hit"] is False and single["reason"] == "parallel"


def test_pick_all_empty_scene():
    """空场景与空射线批次都有确定结果。"""
    r = raypick.Ray((0, 0, -5), (0, 0, 1))
    out = raypick.pick_all([r], [])
    assert out["hits"] == [{"ray": 0, "tri": None, "t": None}]
    assert out["stats"]["intersection_tests"] == 0
    assert out["stats"]["naive_tests"] == 0
    assert out["stats"]["speedup"] == 0.0

    assert raypick.pick_all([], [])["hits"] == []


def test_pick_all_deterministic_two_runs():
    """同一批射线两次结果完全一致（含交点浮点值与统计）。"""
    rays, tris = _grid_scene(n=8, seed=42)
    first = raypick.pick_all(rays, tris)
    second = raypick.pick_all(rays, tris)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_pick_all_matches_brute_force():
    """BVH 结果与全遍历暴力求解逐条一致（最近命中 + tie-break）。"""
    rays, tris = _grid_scene(n=10, seed=7)
    out = raypick.pick_all(rays, tris)

    for ray_i, ray in enumerate(rays):
        best = None
        for tri in tris:
            res = raypick.intersect(ray, tri)
            if not res["hit"]:
                continue
            if best is None or res["t"] < best["t"] or (
                res["t"] == best["t"] and res["tri"] < best["tri"]
            ):
                best = res
        got = out["hits"][ray_i]
        if best is None:
            assert got["tri"] is None
        else:
            assert got["tri"] == best["tri"]
            assert got["t"] == best["t"]


def test_pick_all_acceleration_stats():
    """BVH 裁剪使实际求交次数显著少于全遍历，统计口径自洽。"""
    rays, tris = _grid_scene(n=16, seed=123)
    out = raypick.pick_all(rays, tris)
    stats = out["stats"]

    n_rays = len(rays)
    n_tris = len(tris)
    assert n_tris == 16 * 16
    assert stats["naive_tests"] == n_rays * n_tris
    assert stats["intersection_tests"] < stats["naive_tests"]
    assert stats["speedup"] > 3.0
    assert abs(
        stats["tests_per_ray"]
        - stats["intersection_tests"] / stats["valid_rays"]
    ) < 1e-12
    # 退化三角形计数正确（本场景没有退化三角形）。
    assert stats["degenerate_triangles"] == 0


def test_pick_all_counts_degenerate():
    rays = [raypick.Ray((0, 0, -5), (0, 0, 1))]
    tris = [
        raypick.Triangle(0, (-1, -1, 0), (1, -1, 0), (0, 1, 0)),
        raypick.Triangle(1, (0, 0, 0), (1, 0, 0), (2, 0, 0)),
        raypick.Triangle(2, (0, 0, 1), (1, 0, 1), (2, 0, 1)),
    ]
    stats = raypick.pick_all(rays, tris)["stats"]
    assert stats["degenerate_triangles"] == 2


# ---------------------------------------------------------------- CLI 端到端

def test_cli_end_to_end():
    data_path = os.path.join(ROOT, "data", "rays.json")
    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "hits.json")
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", "-m", "raypick.cli", data_path,
             "--out", out_path],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert proc.returncode == 0, proc.stderr
        with open(out_path, encoding="utf-8") as f:
            payload = json.load(f)
    assert len(payload["hits"]) == 2
    assert payload["hits"][0]["tri"] == 0
    assert payload["hits"][1]["tri"] is None
    assert payload["stats"]["intersection_tests"] >= 1


# ---------------------------------------------------------------- 辅助

def _grid_scene(n=16, seed=0):
    """n×n 网格三角形 + 确定性伪随机射线（含部分打空的射线）。"""
    import random

    rng = random.Random(seed)
    tris = [_tri(i * n + j, i, j) for i in range(n) for j in range(n)]
    rays = []
    for _ in range(n * 2):
        i = rng.randrange(n)
        j = rng.randrange(n)
        # 打在三角形内部（i+0.25, j+0.25）。
        rays.append(raypick.Ray((i + 0.25, j + 0.25, -3.0), (0, 0, 1)))
    for _ in range(n):
        # 打在网格间隙 (i+0.75, j+0.75) 附近，大多落空。
        i = rng.randrange(n)
        j = rng.randrange(n)
        rays.append(raypick.Ray((i + 0.9, j + 0.9, -3.0), (0, 0, 1)))
    return rays, tris
