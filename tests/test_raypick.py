# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import raypick as mod  # noqa: E402
raypick = mod

def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def read_hex(path):
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def test_intersect_hit():
    r = raypick.Ray((0, 0, -5), (0, 0, 1))
    t = raypick.Triangle(0, (-1, -1, 0), (1, -1, 0), (0, 1, 0))
    hit = raypick.intersect(r, t)
    assert hit["hit"] is True
    assert abs(hit["t"] - 5.0) < 1e-6


def test_pick_all_returns_nearest():
    rays = [raypick.Ray((0, 0, -5), (0, 0, 1))]
    tris = [raypick.Triangle(0, (-1, -1, 0), (1, -1, 0), (0, 1, 0)),
            raypick.Triangle(1, (-1, -1, 2), (1, -1, 2), (0, 1, 2))]
    out = raypick.pick_all(rays, tris)
    assert out["hits"][0]["tri"] == 0
