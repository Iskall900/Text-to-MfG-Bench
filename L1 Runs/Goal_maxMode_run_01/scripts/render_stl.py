"""Simple STL software renderer -> PNG (z-buffer, flat shading)."""
import struct
import sys
import numpy as np
from PIL import Image


def load_stl(path):
    with open(path, "rb") as f:
        head = f.read(80)
        n = struct.unpack("<I", f.read(4))[0]
        data = np.frombuffer(f.read(n * 50), dtype=np.uint8).reshape(n, 50)
    tri = data[:, 12:48].copy().view("<f4").reshape(n, 3, 3).astype(np.float64)
    return tri


def render(tri, viewdir, updir, res=700, pad=0.05):
    viewdir = np.array(viewdir, float)
    viewdir /= np.linalg.norm(viewdir)
    updir = np.array(updir, float)
    right = np.cross(viewdir, updir)
    right /= np.linalg.norm(right)
    up = np.cross(right, viewdir)
    # project all vertices
    pts = tri.reshape(-1, 3)
    c = (pts.min(0) + pts.max(0)) / 2
    pts = pts - c
    x = pts @ right
    y = pts @ up
    z = pts @ viewdir  # depth: larger = closer to viewer? we use -viewdir as normal
    span = max(x.max() - x.min(), y.max() - y.min())
    scale = (1 - 2 * pad) * res / span
    px = (x * scale + res / 2)
    py = (res / 2 - y * scale)
    pz = z * scale
    P = np.stack([px, py, pz], 1).reshape(-1, 3, 3)
    # face normals
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    n = n / ln
    light = np.array([0.4, 0.5, 0.76], float)
    light /= np.linalg.norm(light)
    shade = 0.25 + 0.75 * np.abs(n @ light)
    depth = P[:, :, 2].mean(1)
    order = np.argsort(depth)  # far first (we render larger z = closer? choose)
    img = np.ones((res, res, 3), np.float64)
    zbuf = np.full((res, res), -1e18)
    for i in order:
        p = P[i]
        s = shade[i]
        x0, y0 = p[:, 0], p[:, 1]
        xmin, xmax = int(max(0, np.floor(x0.min()))), int(min(res - 1, np.ceil(x0.max())))
        ymin, ymax = int(max(0, np.floor(y0.min()))), int(min(res - 1, np.ceil(y0.max())))
        if xmin > xmax or ymin > ymax:
            continue
        xs, ys = np.meshgrid(np.arange(xmin, xmax + 1), np.arange(ymin, ymax + 1))
        d = np.zeros(xs.shape, bool)
        # barycentric
        x1, y1 = x0[0], y0[0]
        x2, y2 = x0[1], y0[1]
        x3, y3 = x0[2], y0[2]
        den = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        if abs(den) < 1e-12:
            continue
        w1 = ((y2 - y3) * (xs - x3) + (x3 - x2) * (ys - y3)) / den
        w2 = ((y3 - y1) * (xs - x3) + (x1 - x3) * (ys - y3)) / den
        w3 = 1 - w1 - w2
        inside = (w1 >= -1e-9) & (w2 >= -1e-9) & (w3 >= -1e-9)
        if not inside.any():
            continue
        zz = w1 * p[0, 2] + w2 * p[1, 2] + w3 * p[2, 2]
        sub = zbuf[ymin:ymax + 1, xmin:xmax + 1]
        upd = inside & (zz > sub)
        if upd.any():
            sub[upd] = zz[upd]
            col = np.array([0.62, 0.70, 0.80]) * s
            img[ymin:ymax + 1, xmin:xmax + 1][upd] = col
            # edge darkening for silhouettes
            edge = inside & ~np.pad(inside, 1)[1:-1, 1:-1]
            img[ymin:ymax + 1, xmin:xmax + 1][edge] = np.array([0.15, 0.15, 0.2])
    return Image.fromarray(np.clip(img * 255, 0, 255).astype(np.uint8))


def main():
    stl, out = sys.argv[1], sys.argv[2]
    tri = load_stl(stl)
    views = [
        ((0, -1, 0.0), (0, 0, 1)),      # front (X-Z)
        ((-1, 0, 0.0), (0, 0, 1)),      # side (Y-Z)
        ((0, 0, 1.0), (0, 1, 0)),       # top (X-Y)
        ((-0.7, -0.7, 0.45), (0, 0, 1)),  # iso
    ]
    imgs = [render(tri, v, u, res=520) for v, u in views]
    W = sum(i.width for i in imgs)
    H = max(i.height for i in imgs)
    out_img = Image.new("RGB", (W, H), (255, 255, 255))
    x = 0
    for im in imgs:
        out_img.paste(im, (x, 0))
        x += im.width
    out_img.save(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
