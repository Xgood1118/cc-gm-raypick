# -*- coding: utf-8 -*-
"""命令行入口：读取射线/三角形数据，批量拾取并写出结果。"""

import argparse
import json
import sys

import raypick as m

# Windows GBK 控制台也能稳定输出中文与浮点结果。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):  # pragma: no cover - 老版本或非标准流
    pass


def _load(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    rays = [
        m.Ray(tuple(r["origin"]), tuple(r["direction"]))
        for r in data.get("rays", [])
    ]
    tris = [
        m.Triangle(t["index"], tuple(t["a"]), tuple(t["b"]), tuple(t["c"]))
        for t in data.get("tris", [])
    ]
    return rays, tris


def _distance_distribution(hits):
    """最近命中距离分布：按数量级分桶，并给出 min/max/mean。"""
    ts = sorted(h["t"] for h in hits if h["tri"] is not None)
    if not ts:
        return {"buckets": {}, "min": None, "max": None, "mean": None}

    buckets = {}
    for t in ts:
        if t <= 0.0:
            key = "<=0"
        else:
            key = "1e%d" % _floor_log10(t)
        buckets[key] = buckets.get(key, 0) + 1

    return {
        "buckets": dict(sorted(buckets.items())),
        "min": ts[0],
        "max": ts[-1],
        "mean": sum(ts) / len(ts),
    }


def _floor_log10(x):
    """不依赖 math 的 floor(log10(x))，x > 0。"""
    n = 0
    if x >= 1.0:
        while x >= 10.0:
            x /= 10.0
            n += 1
        return n
    while x < 1.0:
        x *= 10.0
        n -= 1
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description="批量射线拾取")
    ap.add_argument("input", help="射线与三角形数据 JSON，如 data/rays.json")
    ap.add_argument("--out", required=True, help="命中结果输出 JSON 路径")
    a = ap.parse_args(argv)

    rays, tris = _load(a.input)
    result = m.pick_all(rays, tris)
    stats = result["stats"]
    stats["distance_distribution"] = _distance_distribution(result["hits"])

    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    n_rays = stats["rays"]
    hit_rate = (stats["hits"] / n_rays) if n_rays else 0.0
    print("射线数: %d（其中零方向 %d）" % (n_rays, stats["zero_direction_rays"]))
    print("三角形数: %d（其中退化 %d）"
          % (stats["triangles"], stats["degenerate_triangles"]))
    print("命中: %d，命中率: %.4f" % (stats["hits"], hit_rate))
    print("实际求交次数: %d，全遍历基准: %d，加速比: %.2fx，平均每射线求交: %.2f"
          % (stats["intersection_tests"], stats["naive_tests"],
             stats["speedup"], stats["tests_per_ray"]))
    print("最近命中距离分布: %s" % json.dumps(
        stats["distance_distribution"], ensure_ascii=False))
    print("结果已写入 %s" % a.out)


if __name__ == "__main__":
    main()
