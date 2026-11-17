# 批量射线拾取

一个能对大量射线做批量求交、并保持最近命中顺序稳定的拾取器

## 保留签名

- `Ray`
- `Triangle`
- `intersect(ray, tri)`
- `pick_all(rays, tris)`

## 自测

```
python -m pytest tests -q
python -m raypick.cli data/rays.json --out hits.json
```
