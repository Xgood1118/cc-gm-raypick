# -*- coding: utf-8 -*-
"""批量射线拾取"""

from dataclasses import dataclass


@dataclass
class Ray:
    """射线。"""
    origin: tuple
    direction: tuple


@dataclass
class Triangle:
    """三角形。"""
    index: int
    a: tuple
    b: tuple
    c: tuple


def Ray:
    """class"""
    raise NotImplementedError("Ray 尚未实现")


def Triangle:
    """class"""
    raise NotImplementedError("Triangle 尚未实现")


def intersect(ray, tri):
    """单次求交"""
    raise NotImplementedError("intersect 尚未实现")


def pick_all(rays, tris):
    """批量拾取并返回统计"""
    raise NotImplementedError("pick_all 尚未实现")

