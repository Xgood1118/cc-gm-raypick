# -*- coding: utf-8 -*-
"""共享常量与基础向量运算（仅标准库）。"""

#: 几何容差。相对量（与射线长度、三角形尺寸比较），不依赖绝对坐标尺度。
EPS = 1e-9


def vsub(p, q):
    return (p[0] - q[0], p[1] - q[1], p[2] - q[2])


def vcross(p, q):
    return (
        p[1] * q[2] - p[2] * q[1],
        p[2] * q[0] - p[0] * q[2],
        p[0] * q[1] - p[1] * q[0],
    )


def vdot(p, q):
    return p[0] * q[0] + p[1] * q[1] + p[2] * q[2]


def vnorm1(p):
    """L1 范数，用于相对容差比较。"""
    return abs(p[0]) + abs(p[1]) + abs(p[2])
