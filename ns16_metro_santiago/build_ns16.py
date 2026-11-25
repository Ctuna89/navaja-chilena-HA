"""Tren Metro de Santiago NS-16 (Alstom) - modelo procedural para Blender (bpy).

Uso:  python3 build_ns16.py [salida.blend]
Genera: cabina de conduccion + interior de pasajeros + bogies, 5 coches.
Sin vias ni anden. Fondo de estudio neutro.
"""
import bpy, bmesh, math, sys, os, random
from mathutils import Vector, Matrix

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "ns16_metro_santiago.blend")
N_MID = 5                 # coches intermedios (tren de 7 coches) (total = 2 cabeceros + N_MID)
FLOOR = 1.05              # altura piso sobre riel
HW = 1.5                  # semiancho carroceria
RH = 0.45                 # flecha del techo
TOP = 3.1 + RH            # altura techo
random.seed(7)

# ----------------------------------------------------------------- geometria
class Geo:
    def __init__(s): s.d = {}
    def add(s, mat, verts, faces, M=None):
        v, f = s.d.setdefault(mat, ([], []))
        o = len(v)
        if M is not None:
            verts = [M @ Vector(p) for p in verts]
        v.extend(verts)
        f.extend([tuple(i + o for i in fc) for fc in faces])
    def tris(s):
        return sum(len(fc) - 2 for _, f in s.d.values() for fc in f)

def perp(a):
    a = Vector(a).normalized()
    t = Vector((0, 0, 1)) if abs(a.z) < 0.9 else Vector((1, 0, 0))
    u = a.cross(t).normalized(); v = a.cross(u).normalized()
    return u, v

def loft(g, mat, rings, close=False, caps=False, loop=False, M=None):
    n = len(rings[0]); R = len(rings)
    verts = [p for r in rings for p in r]; faces = []
    pairs = list(range(R - 1)) + ([R - 1] if loop else [])
    for i in pairs:
        i2 = (i + 1) % R
        for j in range(n if close else n - 1):
            j2 = (j + 1) % n
            faces.append((i * n + j, i * n + j2, i2 * n + j2, i2 * n + j))
    if caps and close and not loop:
        faces.append(tuple(range(n)))
        faces.append(tuple(range((R - 1) * n, R * n))[::-1])
    g.add(mat, verts, faces, M)

def box(g, mat, c, s, bev=0.0, seg=1, M=None):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * s[0], v.co.y * s[1], v.co.z * s[2]))
    if bev > 0:
        bev = min(bev, min(s) * 0.49)
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bev, segments=seg, affect='EDGES')
    bm.verts.ensure_lookup_table()
    verts = [Vector(v.co) + Vector(c) for v in bm.verts]
    idx = {v: i for i, v in enumerate(bm.verts)}
    faces = [tuple(idx[v] for v in f.verts) for f in bm.faces]
    bm.free()
    g.add(mat, verts, faces, M)

def cyl(g, mat, p0, p1, r0, r1=None, seg=32, caps=True, M=None):
    p0 = Vector(p0); p1 = Vector(p1); r1 = r0 if r1 is None else r1
    u, v = perp(p1 - p0); rings = []
    for p, r in ((p0, r0), (p1, r1)):
        rings.append([p + (u * math.cos(2 * math.pi * i / seg) + v * math.sin(2 * math.pi * i / seg)) * r
                      for i in range(seg)])
    loft(g, mat, rings, close=True, caps=caps, M=M)

def tube(g, mat, pts, r, sides=12, closed=False, caps=True, M=None):
    pts = [Vector(p) for p in pts]; n = len(pts); tans = []
    for i in range(n):
        t = pts[(i + 1) % n] - pts[i - 1] if closed else pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]
        tans.append(t.normalized())
    u, v = perp(tans[0]); rings = []
    for i in range(n):
        if i > 0:
            q = tans[i - 1].rotation_difference(tans[i]); u = q @ u; v = q @ v
        rings.append([pts[i] + (u * math.cos(2 * math.pi * k / sides) + v * math.sin(2 * math.pi * k / sides)) * r
                      for k in range(sides)])
    loft(g, mat, rings, close=True, caps=caps and not closed, loop=closed, M=M)

def revolve(g, mat, prof, seg, M=None):
    """prof: [(r, a)] poligono cerrado; eje = Z local."""
    rings = [[(r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg), a)
              for i in range(seg)] for r, a in prof]
    loft(g, mat, rings, close=True, loop=True, M=M)  # loop sobre perfil, close sobre giro
    # (loft recorre rings como 'perfil'; ver nota: loop=True cierra el perfil)

def torus(g, mat, c, R, r, segR=28, segr=10, M=None):
    pts = [(c[0] + R * math.cos(2 * math.pi * i / segR), c[1], c[2] + R * math.sin(2 * math.pi * i / segR))
           for i in range(segR)]
    tube(g, mat, pts, r, sides=segr, closed=True, M=M)

def oriented_box(g, mat, p, n, size, bev=0.0, seg=2):
    n = Vector(n).normalized(); up = Vector((0, 0, 1))
    t = up.cross(n).normalized(); w = n.cross(t).normalized()
    M = Matrix(((n.x, t.x, w.x, p[0]), (n.y, t.y, w.y, p[1]), (n.z, t.z, w.z, p[2]), (0, 0, 0, 1)))
    box(g, mat, (0, 0, 0), size, bev, seg, M=M)

def rot_x(deg): return Matrix.Rotation(math.radians(deg), 4, 'X')

def rrect(w, h, r, nc=8, cx=0.0, cz=0.0):
    """rectangulo redondeado CCW en plano (u, v)"""
    r = min(r, w / 2 - 1e-4, h / 2 - 1e-4); pts = []
    for (ux, vz, a0) in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for k in range(nc + 1):
            a = math.radians(a0 + 90 * k / nc)
            pts.append((cx + ux + r * math.cos(a), cz + vz + r * math.sin(a)))
    return pts

def frame_at(p, n):
    n = Vector(n).normalized(); up = Vector((0, 0, 1))
    t = up.cross(n)
    if t.length < 1e-6: t = Vector((0, 1, 0))
    t.normalize(); w = n.cross(t).normalized()
    return Matrix(((n.x, t.x, w.x, p[0]), (n.y, t.y, w.y, p[1]), (n.z, t.z, w.z, p[2]), (0, 0, 0, 1)))

def flat_poly(g, mat, pts_xz, y, t):
    loft(g, mat, [[(x, y, z) for x, z in pts_xz], [(x, y + t, z) for x, z in pts_xz]], close=True, caps=True)

def gasket(g, sgn, cx, cz, w, h, r, y_face, lip, recess, border=0.055, glass=True, mat="black"):
    """burlete de goma redondeado alrededor de una abertura (ventanas NS-16)"""
    o = rrect(w + 2 * border, h + 2 * border, r + border, 8, cx, cz)
    o2 = rrect(w + 2 * border - 0.016, h + 2 * border - 0.016, r + border - 0.008, 8, cx, cz)
    i1 = rrect(w + 0.016, h + 0.016, r + 0.008, 8, cx, cz)
    i = rrect(w, h, r, 8, cx, cz)
    Y = lambda v: sgn * v
    rings = [[(x, Y(y_face), z) for x, z in o], [(x, Y(y_face + lip), z) for x, z in o2],
             [(x, Y(y_face + lip), z) for x, z in i1], [(x, Y(y_face - recess), z) for x, z in i]]
    loft(g, mat, rings, close=True)
    if glass:
        g.add("glass", [(x, Y(y_face - recess), z) for x, z in i], [tuple(range(len(i)))])


# ----------------------------------------------------------------- materiales
MATS = {}
def mk(name, col, metal=0.0, rough=0.5, emit=None, strength=0.0, coat=0.0, glass=False):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    if glass:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        gl = nt.nodes.new("ShaderNodeBsdfGlossy"); gl.inputs["Roughness"].default_value = 0.03
        gl.inputs["Color"].default_value = (0.5, 0.58, 0.62, 1)
        mix = nt.nodes.new("ShaderNodeMixShader"); mix.inputs[0].default_value = 0.22
        tr.inputs["Color"].default_value = (0.42, 0.47, 0.5, 1)
        nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(gl.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs[0])
    else:
        b = nt.nodes.new("ShaderNodeBsdfPrincipled")
        b.inputs["Base Color"].default_value = (*col, 1)
        b.inputs["Metallic"].default_value = metal
        b.inputs["Roughness"].default_value = rough
        if coat: b.inputs["Coat Weight"].default_value = coat
        if emit:
            b.inputs["Emission Color"].default_value = (*emit, 1)
            b.inputs["Emission Strength"].default_value = strength
        nt.links.new(b.outputs[0], out.inputs[0])
    m.diffuse_color = (*col, 1)
    MATS[name] = m
    return m

def make_materials():
    mk("body", (0.46, 0.47, 0.49), 0.9, 0.38)          # acero inoxidable
    mk("roof", (0.16, 0.165, 0.17), 0.5, 0.45)
    mk("liner", (0.88, 0.88, 0.87), 0, 0.45)           # paredes interiores blancas
    mk("red", (0.95, 0.012, 0.015), 0.0, 0.25, coat=0.6)
    mk("black", (0.012, 0.012, 0.015), 0.3, 0.25)
    mk("skirt", (0.035, 0.035, 0.04), 0.2, 0.5)
    mk("glass", (1, 1, 1), glass=True)
    mk("steel", (0.8, 0.8, 0.82), 1.0, 0.2)
    mk("rubber", (0.015, 0.015, 0.016), 0, 0.85)
    mk("seat", (0.72, 0.025, 0.035), 0, 0.2, coat=0.9)  # asiento rojo moldeado
    mk("seat_dark", (0.55, 0.02, 0.03), 0, 0.25, coat=0.8)
    mk("seat_white", (0.9, 0.9, 0.9), 0, 0.25, coat=0.6)
    mk("seat_base", (0.1, 0.1, 0.11), 0.2, 0.5)
    mk("floor", (0.22, 0.225, 0.23), 0, 0.75)
    mk("groove", (0.25, 0.26, 0.27), 0, 0.9)
    mk("ceiling", (0.93, 0.93, 0.91), 0, 0.5)
    mk("light", (1, 1, 1), emit=(1.0, 0.97, 0.9), strength=2.5)
    mk("amber", (1, 0.5, 0.05), emit=(1.0, 0.45, 0.03), strength=18.0)
    mk("headlight", (1, 1, 1), emit=(1.0, 0.97, 0.9), strength=40.0)
    mk("taillight", (1, 0.05, 0.03), emit=(1.0, 0.03, 0.02), strength=14.0)
    mk("screen", (0.05, 0.4, 0.6), emit=(0.1, 0.7, 1.0), strength=3.0)
    mk("screen2", (0.02, 0.07, 0.08), 0.2, 0.2)
    mk("white", (0.95, 0.95, 0.95), 0, 0.4)
    mk("iron", (0.04, 0.045, 0.055), 0.6, 0.45)
    mk("motor", (0.18, 0.19, 0.2), 0.8, 0.4)
    mk("wheel", (0.42, 0.42, 0.43), 0.95, 0.35)
    mk("handle", (0.8, 0.8, 0.82), 1.0, 0.2)
    mk("strap", (0.04, 0.04, 0.045), 0, 0.7)
    mk("desk", (0.2, 0.21, 0.23), 0.2, 0.5)
    mk("pole", (0.8, 0.8, 0.82), 1.0, 0.2)
    mk("tire", (0.025, 0.025, 0.027), 0.0, 0.8)
    mk("gloss_black", (0.01, 0.01, 0.012), 0.2, 0.12, coat=1.0)
    mk("chrome", (0.9, 0.9, 0.92), 1.0, 0.08)

# ----------------------------------------------------------------- nariz de cabina
# NS-16 real: frente casi plano, marco rojo envolvente redondeado, mascara negra embutida,
# parabrisas grande, display de destino, placa de numero, logo, grupos opticos, enganche Scharfenberg
def a_of_z(z):
    if z <= 1.28: return 0.55 + 0.22 * ((1.28 - z) / 0.73) ** 1.5
    if z <= 3.05: return 0.55 - 0.35 * (z - 1.28) / 1.77
    return 0.20 * max(0.0, 1 - (z - 3.05) / (TOP - 3.05)) ** 0.6

def b_of_z(z):
    if z <= 3.1: return HW if z >= FLOOR else HW - 0.04
    return HW * math.sqrt(max(0.0, 1 - ((z - 3.1) / RH) ** 2))

SE = 4.0
def nose_xy(z, s_, d, x0):
    a = max(a_of_z(z) - d, 0); b = max(b_of_z(z) - d, 0)
    return (x0 + a * max(0.0, 1 - abs(s_) ** SE) ** (1 / SE), s_ * b, z)

def nose_at(y, z, x0, d=0.0):
    b = max(b_of_z(z) - d, 1e-3); s_ = max(-0.9995, min(0.9995, y / b))
    p = Vector(nose_xy(z, s_, d, x0)); e = 1e-3
    pz = Vector(nose_xy(z + e, s_, d, x0)) - p
    ds = e if s_ < 0.99 else -e
    ps = (Vector(nose_xy(z, s_ + ds, d, x0)) - p) * (1 if ds > 0 else -1)
    n = ps.cross(pz).normalized()
    if n.dot(p - Vector((x0 - 1.0, 0, z))) < 0: n = -n
    return p, n

GL_Y, GL_Z0, GL_Z1 = 1.17, 1.82, 2.55     # parabrisas
MK_Y, MK_Z0, MK_Z1 = 1.33, 1.30, 3.05     # mascara negra
def mask_half(z):
    r = 0.28
    if z >= MK_Z0 + r: return MK_Y
    t = z - MK_Z0
    return MK_Y - r + math.sqrt(max(0.0, r * r - (r - t) ** 2))

def plaque(g, mat, x0, y, z, w, h, r, off=0.004, depth=0.012, bevel=0.004, nc=8):
    p, n = nose_at(y, z, x0); ML = frame_at(p, n)
    ring = rrect(w, h, r, nc); ring_b = rrect(w - 2 * bevel, h - 2 * bevel, max(r - bevel, 0.001), nc)
    loft(g, mat, [[(off, u, v) for u, v in ring], [(off + depth - bevel, u, v) for u, v in ring],
                  [(off + depth, u, v) for u, v in ring_b]], close=True, caps=True, M=ML)
    return p, n, ML

def surf_patch(g, mat, x0, ylo, yhi, z0, z1, nz, ny, off):
    rows = []
    for i in range(nz + 1):
        z = z0 + (z1 - z0) * i / nz; row = []
        for j in range(ny + 1):
            y = ylo(z) + (yhi(z) - ylo(z)) * j / ny
            p, n = nose_at(y, z, x0); row.append(p + n * off)
        rows.append(row)
    loft(g, mat, rows)

def build_nose(g, x0, texts, dest=("501", "Plaza de Maipú"), num="141"):
    lin = [-0.80 + 1.6 * k / 64 for k in range(65)]
    cor = [0.80 + 0.20 * (1 - (1 - u / 28) ** 2) for u in range(1, 29)]
    ss = sorted(set(round(v, 6) for v in lin + cor + [-c for c in cor] + [GL_Y / HW, -GL_Y / HW]))
    zb = [0.55 + (TOP - 0.55) * (1 - (1 - i / 80) ** 2) for i in range(81)] + [0.95, MK_Z0, GL_Z0, GL_Z1, MK_Z1, 3.1]
    zs = []
    for z in sorted(zb):
        if not zs or z - zs[-1] > 0.004: zs.append(z)
    def outer_mat(zc, sc):
        if zc < 0.95: return "skirt"
        if zc < MK_Z0: return "red"
        if zc <= MK_Z1:
            if GL_Z0 <= zc <= GL_Z1 and abs(sc) * HW <= GL_Y: return "glass"
            return "red"
        return "roof"
    for i in range(len(zs) - 1):
        z0, z1 = zs[i], zs[i + 1]; zc = (z0 + z1) / 2
        for j in range(len(ss) - 1):
            sc = (ss[j] + ss[j + 1]) / 2
            m = outer_mat(zc, sc)
            q = [nose_xy(z0, ss[j], 0, x0), nose_xy(z0, ss[j + 1], 0, x0), nose_xy(z1, ss[j + 1], 0, x0), nose_xy(z1, ss[j], 0, x0)]
            g.add(m, q, [(0, 1, 2, 3)])
            if m != "glass" and z0 >= FLOOR - 0.02:
                qi = [nose_xy(z0, ss[j], 0.09, x0), nose_xy(z0, ss[j + 1], 0.09, x0), nose_xy(z1, ss[j + 1], 0.09, x0), nose_xy(z1, ss[j], 0.09, x0)]
                g.add("desk", qi[::-1], [(0, 1, 2, 3)])
    # mascara negra (superpuesta, borde curvo continuo)
    off = 0.003
    surf_patch(g, "gloss_black", x0, lambda z: -mask_half(z), lambda z: mask_half(z), MK_Z0, GL_Z0, 22, 90, off)
    surf_patch(g, "gloss_black", x0, lambda z: -MK_Y, lambda z: MK_Y, GL_Z1, MK_Z1, 14, 90, off)
    surf_patch(g, "gloss_black", x0, lambda z: GL_Y, lambda z: MK_Y, GL_Z0, GL_Z1, 20, 6, off)
    surf_patch(g, "gloss_black", x0, lambda z: -MK_Y, lambda z: -GL_Y, GL_Z0, GL_Z1, 20, 6, off)
    # reborde rojo (filete) alrededor de la mascara
    rim = [(-MK_Y, z) for z in [MK_Z1 - k * (MK_Z1 - MK_Z0 - 0.28) / 20 for k in range(21)]]
    rim += [(-mask_half(MK_Z0 + 0.28 * (1 - k / 16)), MK_Z0 + 0.28 * (1 - k / 16)) for k in range(1, 17)]
    rim += [(y, MK_Z0) for y in [-(MK_Y - 0.28) + 2 * (MK_Y - 0.28) * k / 20 for k in range(1, 20)]]
    rim += [(mask_half(MK_Z0 + 0.28 * k / 16), MK_Z0 + 0.28 * k / 16) for k in range(0, 17)]
    rim += [(MK_Y, z) for z in [MK_Z0 + 0.28 + k * (MK_Z1 - MK_Z0 - 0.28) / 20 for k in range(1, 21)]]
    pts = []
    for y, z in rim:
        p, n = nose_at(y, z, x0); pts.append(p + n * 0.006)
    tube(g, "red", pts, 0.02, 12)
    # burlete negro redondeado del parabrisas
    gp = []
    for u, v in rrect(2 * GL_Y, GL_Z1 - GL_Z0, 0.09, 10, 0.0, (GL_Z0 + GL_Z1) / 2):
        p, n = nose_at(u, v, x0); gp.append(p + n * 0.008)
    tube(g, "rubber", gp, 0.016, 10, closed=True)
    # display de destino
    p, n, ML = plaque(g, "screen2", x0, 0.0, 2.80, 2.2, 0.27, 0.04, off=0.004, depth=0.01)
    for u, v in ((-0.78, 0), (0.12, 0)):
        pass
    # grupos opticos en carcasas redondeadas
    for sg in (-1, 1):
        plaque(g, "gloss_black", x0, sg * 0.86, 1.43, 0.56, 0.18, 0.07, off=0.004, depth=0.025)
        for yy, mt in ((1.04, "headlight"), (0.87, "taillight"), (0.70, "amber")):
            p, n = nose_at(sg * yy, 1.43, x0); ML = frame_at(p + n * 0.03, n)
            cyl(g, mt, (0, 0, 0), (0.01, 0, 0), 0.047, seg=40, M=ML)
            torus(g, "chrome", (0, 0, 0), 0.054, 0.008, 40, 8, M=ML @ Matrix.Rotation(math.radians(90), 4, 'Y'))
            if mt == "headlight":
                for k in range(6):
                    a_ = 2 * math.pi * k / 6
                    cyl(g, "chrome", (0.006, 0.026 * math.cos(a_), 0.026 * math.sin(a_)), (0.014, 0.026 * math.cos(a_), 0.026 * math.sin(a_)), 0.012, seg=16, M=ML)
    # rejilla / tapa bajo el parabrisas
    plaque(g, "skirt", x0, 0.0, 1.60, 0.62, 0.16, 0.07, off=0.003, depth=0.015)
    # logo Metro: ovalo rojo con tres rombos
    p, n = nose_at(0, 1.40, x0); ML = frame_at(p + n * 0.004, n)
    def ell(rx, ry, x, N=56): return [(x, rx * math.cos(2 * math.pi * k / N), ry * math.sin(2 * math.pi * k / N)) for k in range(N)]
    loft(g, "red", [ell(0.19, 0.13, 0.0), ell(0.19, 0.13, 0.012), ell(0.182, 0.122, 0.016)], close=True, caps=True, M=ML)
    loft(g, "gloss_black", [ell(0.165, 0.105, 0.016), ell(0.165, 0.105, 0.019)], close=True, caps=True, M=ML)
    for k in (-1, 0, 1):
        box(g, "red", (0, 0, 0), (0.01, 0.066, 0.066), 0.004, 1,
            M=ML @ Matrix.Translation((0.022, k * 0.088, 0)) @ Matrix.Rotation(math.radians(45), 4, 'X'))
    # placa de numero (cruza el borde inferior del parabrisas)
    plaque(g, "red", x0, 0.0, GL_Z0 + 0.0, 0.44, 0.23, 0.03, off=0.01, depth=0.014)
    # camara sobre el capot
    p, n = nose_at(0, 3.32, x0); ML = frame_at(p, n)
    box(g, "gloss_black", (0.05, 0, 0), (0.16, 0.38, 0.14), 0.035, 4, M=ML)
    cyl(g, "glass", (0.13, 0, 0), (0.135, 0, 0), 0.03, seg=24, M=ML)
    # limpiaparabrisas (uno, como en el real)
    piv, n0 = nose_at(0.30, 1.74, x0)
    cyl(g, "black", piv + n0 * 0.01, piv + n0 * 0.06, 0.03, seg=24)
    arm = [nose_at(0.30 + 0.30 * t, 1.74 + 0.85 * t, x0) for t in (0, 0.25, 0.5, 0.75, 1.0)]
    tube(g, "black", [p + n * 0.05 for p, n in arm], 0.011, 10)
    blade = [nose_at(0.42 + 0.30 * t, 1.92 + 0.82 * t, x0) for t in (0, 0.33, 0.66, 1.0)]
    tube(g, "rubber", [p + n * 0.03 for p, n in blade], 0.009, 8)
    # topes rojos inferiores
    for sg in (-1, 1):
        plaque(g, "red", x0, sg * 0.93, 0.80, 0.62, 0.28, 0.06, off=-0.04, depth=0.24, bevel=0.03)
        plaque(g, "skirt", x0, sg * 0.93, 0.80, 0.34, 0.10, 0.03, off=0.19, depth=0.012)
    # deflector inferior negro con nervios
    for k in range(4):
        p, n = nose_at(0, 0.60 + k * 0.08, x0); ML = frame_at(p, n)
        box(g, "skirt", (0.01, 0, 0), (0.03, 1.1, 0.025), 0.008, 2, M=ML)
    coupler(g, x0 + a_of_z(0.65) - 0.55)
    # textos
    slope = math.radians(-11.2)
    R = Matrix.Rotation(slope, 4, 'Y') @ Matrix.Rotation(math.radians(90), 4, 'Z') @ Matrix.Rotation(math.radians(90), 4, 'X')
    for txt, y, z, size, mat, off in ((dest[0], -0.80, 2.80, 0.15, "amber", 0.016),
                                       (dest[1], 0.12, 2.80, 0.15, "amber", 0.016),
                                       (num, 0.0, GL_Z0, 0.19, "white", 0.026)):
        p, n = nose_at(y, z, x0)
        texts.append((txt, Matrix.Translation(p + n * off) @ R, size, mat))
    # piso de cabina
    pts = [nose_xy(1.05, sv, 0.09, x0) for sv in ss]
    loft(g, "floor", [[(x, y, FLOOR - 0.05) for x, y, _ in pts], [(x, y, FLOOR) for x, y, _ in pts]], close=True, caps=True)

def coupler(g, xf):
    """enganche automatico tipo Scharfenberg"""
    z = 0.66
    cyl(g, "iron", (xf - 0.9, 0, z), (xf + 0.55, 0, z), 0.07, seg=32)            # barra de traccion
    cyl(g, "iron", (xf - 0.2, 0, z), (xf + 0.25, 0, z), 0.11, 0.11, seg=40)       # amortiguador
    for k in range(6):
        torus(g, "iron", (0, 0, 0), 0.115, 0.012, 40, 8, M=Matrix.Translation((xf - 0.15 + k * 0.07, 0, z)) @ Matrix.Rotation(math.radians(90), 4, 'Y'))
    box(g, "iron", (xf + 0.68, 0, z), (0.26, 0.34, 0.36), 0.04, 3)                # cabeza
    box(g, "steel", (xf + 0.825, 0, z), (0.035, 0.40, 0.42), 0.012, 2)            # placa frontal
    cyl(g, "steel", (xf + 0.84, -0.09, z + 0.02), (xf + 0.96, -0.09, z + 0.02), 0.055, 0.03, seg=32)   # cono
    cyl(g, "black", (xf + 0.84, 0.09, z + 0.02), (xf + 0.845, 0.09, z + 0.02), 0.06, seg=32)          # embudo
    torus(g, "steel", (0, 0, 0), 0.062, 0.01, 32, 8, M=Matrix.Translation((xf + 0.845, 0.09, z + 0.02)) @ Matrix.Rotation(math.radians(90), 4, 'Y'))
    box(g, "steel", (xf + 0.85, 0, z - 0.16), (0.05, 0.22, 0.06), 0.01, 2)        # contacto electrico
    tube(g, "iron", [(xf + 0.7, 0.18, z + 0.05), (xf + 0.75, 0.25, z - 0.05), (xf + 0.72, 0.27, z - 0.3)], 0.014, 10)  # palanca
    tube(g, "rubber", [(xf + 0.6, -0.17, z - 0.1), (xf + 0.4, -0.22, z - 0.3), (xf + 0.1, -0.18, z - 0.25), (xf - 0.3, -0.12, z - 0.1)], 0.018, 10)
    box(g, "iron", (xf - 0.75, 0, z), (0.3, 0.5, 0.3), 0.04, 2)                   # soporte

# ----------------------------------------------------------------- coche
WZ0, WZ1 = 1.50, 2.62

def spans_to_windows(spans, cabwin=None):
    wins = []
    for a, b in spans:
        L = b - a - 0.36
        if L < 0.6: continue
        n = max(1, round(L / 1.9))
        w = (L - (n - 1) * 0.30) / n
        for k in range(n):
            x0 = a + 0.18 + k * (w + 0.30)
            wins.append((x0, x0 + w, "window"))
    return wins

def side_pieces(g, sgn, openings, xa, xb, red_from=None):
    z0, z1 = FLOOR, 3.1
    def solid(a, b, za, zb):
        if b - a < 1e-3 or zb - za < 1e-3: return
        box(g, "body", ((a + b) / 2, sgn * 1.47, (za + zb) / 2), (b - a, 0.06, zb - za), 0.006, 1)
        box(g, "liner", ((a + b) / 2, sgn * 1.42, (za + zb) / 2), (b - a, 0.04, zb - za), 0.006, 1)
    cur = xa
    for a, b, kind in sorted(openings):
        solid(cur, a, z0, z1)
        if kind == "door":
            solid(a, b, 2.95, z1)
        else:
            wz0, wz1 = (WZ0, WZ1) if kind == "window" else (1.95, 2.75)
            solid(a, b, z0, wz0); solid(a, b, wz1, z1)
            cx, cz, w, h = (a + b) / 2, (wz0 + wz1) / 2, b - a - 0.08, wz1 - wz0 - 0.08
            rr = 0.13 if kind == "window" else 0.09
            gasket(g, sgn, cx, cz, w, h, rr, 1.50, 0.014, 0.035)
            gasket(g, sgn, cx, cz, w, h, rr, 1.40, -0.010, -0.04, border=0.045, glass=False)
        cur = b
    solid(cur, xb, z0, z1)
    # zocalo inferior de acero
    box(g, "body", ((xa + xb) / 2, sgn * 1.47, 0.925), (xb - xa, 0.06, 0.25), 0.02, 2)
    box(g, "black", ((xa + xb) / 2, sgn * 1.502, 1.05), (xb - xa, 0.006, 0.012))
    # remaches en costuras (linea de techo y zocalo)
    for zz in (3.065, 0.86):
        x = xa + 0.1
        while x < xb - 0.1:
            cyl(g, "body", (x, sgn * 1.50, zz), (x, sgn * 1.507, zz), 0.0065, seg=8)
            x += 0.16

def red_band(g, sgn, spans, doors, xa, xb):
    """grafica roja NS-16: dos franjas paralelas + motivo escalonado entre puertas"""
    y = sgn * 1.502; t = sgn * 0.004
    cuts = sorted([(d - 0.66, d + 0.66) for d in doors])
    segs = []; cur = xa + 0.05
    for a, b in cuts:
        segs.append((cur, a)); cur = b
    segs.append((cur, xb - 0.05))
    for a, b in segs:
        if b - a < 0.05: continue
        flat_poly(g, "red", [(a, 1.255), (b, 1.255), (b, 1.285), (a, 1.285)], y, t)
        flat_poly(g, "red", [(a, 1.355), (b, 1.355), (b, 1.415), (a, 1.415)], y, t)
    for a, b in spans:
        if b - a < 2.6: continue
        flat_poly(g, "red", [(a + 0.55, 1.285), (b - 0.95, 1.285), (b - 0.70, 1.47), (a + 0.95, 1.47)], y, t)
        flat_poly(g, "red", [(a + 0.18, 1.30), (a + 0.40, 1.30), (a + 0.52, 1.35), (a + 0.30, 1.35)], y, t)
        flat_poly(g, "red", [(b - 0.62, 1.42), (b - 0.42, 1.42), (b - 0.36, 1.47), (b - 0.56, 1.47)], y, t)

def door_leaves(g, sgn, xd, is_open, w=1.3):
    lw = w / 2 - 0.01
    for k, d in enumerate((-1, 1)):
        xc = xd + d * (lw / 2 + 0.005)
        if is_open: xc = xd + d * (w / 2 + lw / 2 - 0.06)
        yc = 1.53 if is_open else 1.475
        y = sgn * yc
        zb, zt = FLOOR + 0.02, 2.93
        wz0, wz1 = 1.48, 2.78
        box(g, "body", (xc, y, (zb + wz0) / 2), (lw, 0.04, wz0 - zb), 0.01, 2)
        box(g, "body", (xc, y, (zt + wz1) / 2), (lw, 0.04, zt - wz1), 0.01, 2)
        for s2 in (-1, 1):
            box(g, "body", (xc + s2 * (lw / 2 - 0.07), y, (wz0 + wz1) / 2), (0.14, 0.04, wz1 - wz0), 0.01, 2)
        cx, cz, ww, hh = xc, (wz0 + wz1) / 2, lw - 0.22, wz1 - wz0 - 0.08
        gasket(g, sgn, cx, cz, ww, hh, 0.09, yc + 0.02, 0.01, 0.025, border=0.045)
        gasket(g, sgn, cx, cz, ww, hh, 0.09, yc - 0.02, -0.01, -0.02, border=0.045, glass=False)
        box(g, "rubber", (xc + d * -lw / 2, y, 1.99), (0.025, 0.05, 1.9), 0.006, 1)
        yy = sgn * (yc + 0.021); tt = sgn * 0.004
        flat_poly(g, "red", [(xc - lw / 2, 1.255), (xc + lw / 2, 1.255), (xc + lw / 2, 1.285), (xc - lw / 2, 1.285)], yy, tt)
        flat_poly(g, "red", [(xc - lw / 2, 1.355), (xc + lw / 2, 1.355), (xc + lw / 2, 1.415), (xc - lw / 2, 1.415)], yy, tt)
    for s2 in (-1, 1):
        box(g, "black", (xd + s2 * (w / 2 + 0.03), sgn * 1.5, 2.0), (0.05, 0.03, 1.95), 0.008, 2)
    box(g, "black", (xd, sgn * 1.5, 3.0), (w + 0.12, 0.03, 0.08), 0.008, 2)
    box(g, "steel", (xd, sgn * 1.43, FLOOR + 0.005), (w, 0.12, 0.012))
    # indicador luminoso de puerta
    box(g, "gloss_black", (xd + w / 2 + 0.17, sgn * 1.505, 2.55), (0.07, 0.014, 0.16), 0.012, 2)
    cyl(g, "taillight", (xd + w / 2 + 0.17, sgn * 1.512, 2.58), (xd + w / 2 + 0.17, sgn * 1.516, 2.58), 0.02, seg=20)
    cyl(g, "amber", (xd + w / 2 + 0.17, sgn * 1.512, 2.52), (xd + w / 2 + 0.17, sgn * 1.516, 2.52), 0.02, seg=20)

SEAT_P = [(0.045, 0.98), (0.055, 0.90), (0.068, 0.80), (0.082, 0.70), (0.095, 0.61), (0.11, 0.545), (0.135, 0.50),
          (0.175, 0.472), (0.24, 0.46), (0.32, 0.455), (0.40, 0.452), (0.455, 0.45), (0.485, 0.442), (0.50, 0.425), (0.503, 0.405)]

def seat_shell(g, mat, sgn, x0, x1, wall):
    P = SEAT_P; t = 0.022; offs = []
    for i in range(len(P)):
        a = P[max(i - 1, 0)]; b = P[min(i + 1, len(P) - 1)]
        dd, dh = b[0] - a[0], b[1] - a[1]; L = math.hypot(dd, dh)
        offs.append((P[i][0] + dh / L * t, P[i][1] - dd / L * t))
    ring2 = P + offs[::-1]
    cd = sum(p[0] for p in ring2) / len(ring2); ch = sum(p[1] for p in ring2) / len(ring2)
    def R(x, k):
        return [(x, sgn * (wall - (cd + (d - cd) * k)), FLOOR + ch + (h - ch) * k) for d, h in ring2]
    loft(g, mat, [R(x0, 0.86), R(x0 + 0.006, 0.97), R(x0 + 0.018, 1.0), R(x1 - 0.018, 1.0), R(x1 - 0.006, 0.97), R(x1, 0.86)],
         close=True, caps=True)

def seat_bank(g, sgn, a, b, white_first=False, white_last=False):
    n = int((b - a) // 0.52)
    if n < 1: return
    off = (b - a - n * 0.52) / 2
    wall = 1.40
    box(g, "liner", ((a + b) / 2, sgn * (wall - 0.05), FLOOR + 0.20), (n * 0.52 + 0.04, 0.08, 0.40), 0.015, 2)
    for k in range(n):
        x0 = a + off + k * 0.52 + 0.02; x1 = x0 + 0.48; xc = (x0 + x1) / 2
        m = "seat_white" if ((k == 0 and white_first) or (k == n - 1 and white_last)) else "seat"
        seat_shell(g, m, sgn, x0, x1, wall)
        # relieve circular
        cyl(g, "seat_dark" if m == "seat" else "liner", (xc, sgn * (wall - 0.30), FLOOR + 0.4565), (xc, sgn * (wall - 0.30), FLOOR + 0.4595), 0.15, seg=48)
        nb = Vector((0, -sgn * 0.993, 0.117)); pb = Vector((xc, sgn * (wall - 0.083), FLOOR + 0.72))
        cyl(g, "seat_dark" if m == "seat" else "liner", pb, pb + nb * 0.003, 0.14, seg=48)
        # mensula en voladizo
        if k % 2 == 0:
            tube(g, "steel", [(x0 + 0.02, sgn * (wall - 0.01), FLOOR + 0.25), (x0 + 0.02, sgn * (wall - 0.22), FLOOR + 0.40), (x0 + 0.02, sgn * (wall - 0.42), FLOOR + 0.425)], 0.016, 12)
    # extremos: mampara de vidrio + pasamanos en arco
    for xe in (a + 0.01, b - 0.01):
        box(g, "glass", (xe, sgn * 1.16, FLOOR + 0.98), (0.012, 0.42, 0.82))
        tube(g, "steel", [(xe, sgn * 0.96, FLOOR + 0.57), (xe, sgn * 1.37, FLOOR + 0.57)], 0.014, 12)
        pts = [(xe, sgn * 0.95, FLOOR), (xe, sgn * 0.95, 2.0)]
        for k in range(1, 19):
            ph = math.radians(90 * k / 18)
            pts.append((xe, sgn * (0.95 + 0.42 * (1 - math.cos(ph))), 2.0 + 0.42 * math.sin(ph)))
        tube(g, "pole", pts, 0.019, 20)
        cyl(g, "steel", (xe, sgn * 0.95, FLOOR), (xe, sgn * 0.95, FLOOR + 0.02), 0.04, seg=24)

def handles_rails(g, xa, xb, door_xs, w=1.3):
    def tri_loop():
        poly = [(0.0, 0.0), (-0.075, -0.14), (0.075, -0.14)]
        for _ in range(3):
            q = []
            for i in range(len(poly)):
                p0, p1 = poly[i], poly[(i + 1) % len(poly)]
                q.append((0.75 * p0[0] + 0.25 * p1[0], 0.75 * p0[1] + 0.25 * p1[1]))
                q.append((0.25 * p0[0] + 0.75 * p1[0], 0.25 * p0[1] + 0.75 * p1[1]))
            poly = q
        return poly
    tri = tri_loop()
    for sgn in (-1, 1):
        tube(g, "pole", [(xa, sgn * 0.80, 2.80), (xb, sgn * 0.80, 2.80)], 0.019, 24)
        x = xa + 1.0
        while x < xb - 0.5:
            tube(g, "pole", [(x, sgn * 0.80, 2.80), (x, sgn * 0.80, 3.02)], 0.014, 12)
            x += 2.0
        x = xa + 0.6
        while x < xb - 0.4:
            if all(abs(x - xd) > w / 2 + 0.15 for xd in door_xs):
                tube(g, "pole", [(x, sgn * 0.80, 2.80), (x, sgn * 0.80, 2.70)], 0.009, 10)
                path = [(x, sgn * 0.80 + px, 2.70 + pz) for px, pz in tri]
                tube(g, "handle", path, 0.011, 12, closed=True)
            x += 0.62
    for xd in door_xs:
        tube(g, "pole", [(xd, 0.0, FLOOR), (xd, 0.0, 3.0)], 0.021, 28)
        cyl(g, "steel", (xd, 0, FLOOR), (xd, 0, FLOOR + 0.02), 0.045, seg=28)
        tube(g, "pole", [(xd, -0.80, 2.80), (xd, 0.80, 2.80)], 0.019, 24)
        for sgn in (-1, 1):
            for s2 in (-1, 1):
                xx = xd + s2 * 0.76
                tube(g, "pole", [(xx, sgn * 1.40, 1.30), (xx, sgn * 1.32, 1.36), (xx, sgn * 1.32, 2.34), (xx, sgn * 1.40, 2.40)], 0.017, 16)
            box(g, "black", (xd, sgn * 1.37, 2.86), (0.95, 0.03, 0.15), 0.01, 2)
            for k in range(14):
                cyl(g, "amber" if k % 5 else "screen", (xd - 0.4 + k * 0.0615, sgn * 1.355, 2.86),
                    (xd - 0.4 + k * 0.0615, sgn * 1.34, 2.86), 0.012, seg=20)

def ceiling(g, xa, xb):
    L = xb - xa; xc = (xa + xb) / 2
    box(g, "ceiling", (xc, 0, 3.03), (L, 1.4, 0.05), 0.012, 2)
    for sgn in (-1, 1):
        prof = [(0.70, 3.06), (0.70, 3.0), (1.05, 2.97), (1.42, 2.70), (1.42, 2.76), (1.05, 3.04)]
        loft(g, "ceiling", [[(xa, sgn * y, z) for y, z in prof], [(xb, sgn * y, z) for y, z in prof]], close=True, caps=True)
        box(g, "light", (xc, sgn * 0.98, 2.965), (L - 0.3, 0.12, 0.012), 0.004, 1)
        box(g, "light", (xc, sgn * 1.30, 2.745), (L - 0.3, 0.05, 0.012), 0.004, 1)
        for k in range(8):                                  # ventilacion
            x = xa + 1.2 + k * ((L - 2.4) / 7)
            for m_ in range(4):
                box(g, "black", (x, sgn * (0.2 + m_ * 0.04), 3.0), (0.4, 0.012, 0.01))
    for k in range(int(L // 1.0)):                          # juntas de paneles
        box(g, "groove", (xa + 0.5 + k * 1.0, 0, 3.003), (0.012, 1.4, 0.006))

def underframe(g, xa, xb, bog):
    box(g, "skirt", ((xa + xb) / 2, 0, 0.985), (xb - xa, 2.9, 0.03), 0.01, 1)
    # faldones laterales
    for sgn in (-1, 1):
        for a, b in ((-4.1, -1.2), (-0.9, 1.8), (2.1, 4.2)):
            a2, b2 = max(a, xa + 0.1), min(b, xb - 0.1)
            if b2 - a2 > 0.3:
                pass
        # cajas de equipo
        for k in range(5):
            x = -3.6 + k * 1.8 + random.uniform(-0.15, 0.15)
            if xa + 1 < x < xb - 1:
                box(g, "iron", (x, sgn * 0.6, 0.78), (1.1 + random.uniform(-.2, .2), 0.7, 0.4), 0.03, 2)
        # cableado
        tube(g, "rubber", [(xa + 0.5, sgn * 0.15, 0.95), (xa + 2, sgn * 0.2, 0.9), (xb - 2, sgn * 0.2, 0.9), (xb - 0.5, sgn * 0.15, 0.95)], 0.025, 12)
    box(g, "iron", (0.5, 0, 0.7), (1.6, 0.9, 0.46), 0.04, 2)
    box(g, "iron", (-2.5, 0, 0.74), (0.8, 0.8, 0.3), 0.03, 2)
    # compresor
    cyl(g, "iron", (2.6, -0.3, 0.72), (2.6, 0.3, 0.72), 0.2, seg=48)

def roof_equipment(g, xa, xb):
    for xc in (-4.4, 3.6):
        if not (xa + 1.5 < xc < xb - 1.5): continue
        box(g, "roof", (xc, 0, TOP + 0.1), (2.3, 1.6, 0.25), 0.07, 4)
        for dx in (-0.55, 0.55):
            cyl(g, "black", (xc + dx, 0, TOP + 0.226), (xc + dx, 0, TOP + 0.24), 0.34, seg=64)
            for k in range(7):
                a = math.radians(k * 360 / 7)
                M = Matrix.Translation((xc + dx, 0, TOP + 0.243)) @ Matrix.Rotation(a, 4, 'Z')
                box(g, "steel", (0.14, 0, 0), (0.28, 0.07, 0.006), 0.002, 1, M=M)
            torus(g, "steel", (0, 0, 0), 0.34, 0.012, 48, 8,
                  M=Matrix.Translation((xc + dx, 0, TOP + 0.24)) @ rot_x(90))
        for k in range(10):
            box(g, "steel", (xc, 0, TOP + 0.2), (0.03, 1.58, 0.012), 0.002, 1, M=Matrix.Translation((-1.0 + k * 0.22, 0, 0)))
    box(g, "black", ((xa + xb) / 2, 0, TOP + 0.01), (1.0, 0.2, 0.05), 0.012, 2)

def passenger_end(g, x, sgn_dir):
    """cierre de testero con abertura de intercirculacion"""
    for s in (-1, 1):
        box(g, "body", (x, s * 1.1, 2.07), (0.08, 0.64, 2.05), 0.012, 2)
        box(g, "liner", (x - sgn_dir * 0.05, s * 1.1, 2.07), (0.03, 0.64, 2.05), 0.008, 1)
    box(g, "body", (x, 0, 2.99), (0.08, 1.56, 0.2), 0.012, 2)
    box(g, "liner", (x - sgn_dir * 0.05, 0, 2.99), (0.03, 1.56, 0.2), 0.008, 1)
    box(g, "steel", (x, 0, FLOOR + 0.005), (0.3, 1.6, 0.012))

def tire_profile(R, W, rim, grooves):
    hw = W / 2
    left = [(rim, -hw + 0.012), (rim + 0.02, -hw - 0.006), (rim + 0.06, -hw - 0.014), ((rim + R) / 2, -hw - 0.018),
            (R - 0.05, -hw - 0.014), (R - 0.022, -hw - 0.004), (R - 0.006, -hw + 0.012), (R, -hw + 0.03)]
    tread = []
    for gp in grooves:
        tread += [(R, gp - 0.011), (R - 0.004, gp - 0.008), (R - 0.014, gp - 0.006), (R - 0.014, gp + 0.006), (R - 0.004, gp + 0.008), (R, gp + 0.011)]
    right = [(r, -a) for r, a in left[::-1]]
    return left + tread + right

def hub(g, M, r=0.29, bolts=10):
    prof = [(0.06, -0.13), (r, -0.13), (r, 0.125), (r - 0.02, 0.135), (0.24, 0.12), (0.20, 0.095), (0.15, 0.09),
            (0.12, 0.12), (0.09, 0.14), (0.06, 0.14)]
    revolve(g, "steel", prof, 64, M=M)
    for k in range(bolts):
        a = 2 * math.pi * k / bolts
        cyl(g, "chrome", (0.17 * math.cos(a), 0.17 * math.sin(a), 0.09), (0.17 * math.cos(a), 0.17 * math.sin(a), 0.115), 0.016, seg=6, M=M)
    cyl(g, "chrome", (0, 0, 0.14), (0, 0, 0.17), 0.07, 0.05, seg=32, M=M)

def coil(g, c, r, wire, h, turns, mat="iron"):
    N = int(turns * 26)
    pts = [(c[0] + r * math.cos(2 * math.pi * turns * i / N), c[1] + r * math.sin(2 * math.pi * turns * i / N), c[2] + h * i / N) for i in range(N + 1)]
    tube(g, mat, pts, wire, 10)

def bogie(g, xb):
    """bogie de rodado neumatico (metro de Santiago L2/L5): neumaticos portantes, ruedas de seguridad
    de acero, ruedas guia horizontales, suspension helicoidal, motores y frenos"""
    ZA = 0.48
    for ax in (-0.95, 0.95):
        x = xb + ax
        cyl(g, "iron", (x, -1.16, ZA), (x, 1.16, ZA), 0.075, seg=32)
        box(g, "iron", (x, 0, ZA), (0.30, 0.38, 0.40), 0.06, 3)                       # diferencial
        for sg in (-1, 1):
            M = Matrix.Translation((x, sg * 0.99, ZA)) @ rot_x(-90 * sg)
            revolve(g, "tire", tire_profile(0.48, 0.30, 0.29, (-0.075, 0.0, 0.075)), 80, M=M)
            hub(g, M)
            # rueda de seguridad de acero (interior)
            prof = [(0.10, 0.0), (0.20, 0.0), (0.20, 0.03), (0.36, 0.03), (0.36, 0.0), (0.42, 0.005), (0.452, 0.015),
                    (0.452, 0.025), (0.42, 0.045), (0.415, 0.11), (0.36, 0.11), (0.36, 0.06), (0.20, 0.06), (0.20, 0.10), (0.10, 0.10)]
            revolve(g, "wheel", prof, 72, M=Matrix.Translation((x, sg * 0.66, ZA)) @ rot_x(-90 * sg))
            bx = x + (0.5 if ax > 0 else -0.5)
            box(g, "iron", (bx, sg * 0.72, ZA), (0.10, 0.14, 0.26), 0.02, 2)           # freno de zapata
            cyl(g, "iron", (bx + (0.08 if ax > 0 else -0.08), sg * 0.72, ZA), (bx + (0.22 if ax > 0 else -0.22), sg * 0.72, ZA), 0.05, seg=20)
    # bastidor
    for sg in (-1, 1):
        box(g, "iron", (xb, sg * 1.23, 0.60), (2.5, 0.16, 0.22), 0.045, 3)
        for k in range(8):
            box(g, "iron", (xb - 1.05 + k * 0.3, sg * 1.23, 0.73), (0.03, 0.16, 0.05), 0.008, 1)
        for ex in (-1, 1):                                                              # brazos de ruedas guia
            box(g, "iron", (xb + ex * 1.40, sg * 1.16, 0.46), (0.34, 0.16, 0.14), 0.035, 3)
            gx = xb + ex * 1.55
            revolve(g, "tire", tire_profile(0.20, 0.13, 0.11, (0.0,)), 56, M=Matrix.Translation((gx, sg * 1.18, 0.33)))
            revolve(g, "steel", [(0.03, -0.075), (0.11, -0.075), (0.11, 0.075), (0.09, 0.085), (0.05, 0.085), (0.03, 0.08)], 40,
                    M=Matrix.Translation((gx, sg * 1.18, 0.33)))
            cyl(g, "iron", (gx, sg * 1.18, 0.33), (gx, sg * 1.18, 0.50), 0.035, seg=20)
            box(g, "iron", (gx, sg * 1.18, 0.50), (0.14, 0.14, 0.06), 0.02, 2)
            # zapata captadora sobre barra guia
            box(g, "iron", (xb + ex * 0.62, sg * 1.36, 0.36), (0.30, 0.06, 0.10), 0.015, 2)
            cyl(g, "white", (xb + ex * 0.62, sg * 1.30, 0.42), (xb + ex * 0.62, sg * 1.30, 0.55), 0.035, seg=16)
            # resortes helicoidales secundarios + amortiguadores
            coil(g, (xb + ex * 0.36, sg * 1.23, 0.71), 0.085, 0.016, 0.20, 5.5)
            cyl(g, "iron", (xb + ex * 0.36, sg * 1.23, 0.70), (xb + ex * 0.36, sg * 1.23, 0.72), 0.11, seg=28)
            cyl(g, "iron", (xb + ex * 0.36, sg * 1.23, 0.91), (xb + ex * 0.36, sg * 1.23, 0.93), 0.11, seg=28)
            tube(g, "iron", [(xb + ex * 1.62, -1.12, 0.40), (xb + ex * 1.62, 1.12, 0.40)], 0.05, 16) if sg == 1 else None
        cyl(g, "motor", (xb, sg * 1.33, 0.62), (xb, sg * 1.33, 0.92), 0.035, seg=20)
        cyl(g, "chrome", (xb, sg * 1.33, 0.80), (xb, sg * 1.33, 0.94), 0.022, seg=16)
        tube(g, "iron", [(xb, sg * 0.30, 0.86), (xb + 0.55, sg * 0.30, 0.64)], 0.03, 12)  # barra de traccion
    box(g, "iron", (xb, 0, 0.60), (0.40, 2.40, 0.26), 0.05, 3)                           # travesano
    box(g, "iron", (xb, 0, 0.88), (0.55, 2.5, 0.12), 0.04, 3)                            # bolster
    cyl(g, "steel", (xb, 0, 0.94), (xb, 0, 0.98), 0.26, seg=48)                          # pivote
    tube(g, "motor", [(xb - 0.15, -0.9, 0.80), (xb + 0.15, 0.9, 0.78)], 0.03, 12)         # amortiguador lateral
    for mx in (-0.55, 0.55):
        cyl(g, "motor", (xb + mx, -0.36, 0.45), (xb + mx, 0.36, 0.45), 0.19, seg=56)
        for k in range(14):
            a = math.radians(k * 360 / 14)
            cyl(g, "motor", (xb + mx + 0.19 * math.cos(a), -0.32, 0.45 + 0.19 * math.sin(a)),
                (xb + mx + 0.19 * math.cos(a), 0.32, 0.45 + 0.19 * math.sin(a)), 0.012, seg=8)
        cyl(g, "iron", (xb + mx, -0.40, 0.45), (xb + mx, 0.40, 0.45), 0.12, seg=40)
    tube(g, "rubber", [(xb, 0.4, 0.95), (xb + 0.2, 0.8, 0.85), (xb + 0.6, 1.1, 0.6)], 0.02, 10)

def build_car(kind, dest=("501", "Plaza de Maipú"), num="141"):
    g = Geo(); texts = []
    cab = kind == "cab"
    xa, xb = -8.0, (7.0 if cab else 8.0)
    if cab:
        doors = [-5.4, -0.2]
        spans = [(xa, -6.05), (-4.75, -0.85), (0.45, 3.45)]
        openings = [(d - 0.65, d + 0.65, "door") for d in doors]
        openings += spans_to_windows(spans)
        openings += [(5.15, 6.05, "door"), (6.22, 6.62, "cabwin")]
    else:
        doors = [-5.4, 0.0, 5.4]
        spans = [(xa, -6.05), (-4.75, -0.65), (0.65, 4.75), (6.05, xb)]
        openings = [(d - 0.65, d + 0.65, "door") for d in doors]
        openings += spans_to_windows(spans)
    for sgn in (-1, 1):
        side_pieces(g, sgn, openings, xa, xb)
        red_band(g, sgn, spans, doors, xa, (5.0 if cab else xb))
        for d in doors:
            door_leaves(g, sgn, d, is_open=(sgn == 1))
    if cab:
        for sgn in (-1, 1):   # puerta lateral de cabina (cerrada) + asideros + rejilla
            xc = 5.6
            box(g, "body", (xc, sgn * 1.475, 2.02), (0.86, 0.04, 1.85), 0.01, 2)
            gasket(g, sgn, xc, 2.30, 0.30, 0.95, 0.09, 1.495, 0.012, 0.03, border=0.045)
            for xx in (5.08, 6.12):
                tube(g, "pole", [(xx, sgn * 1.50, 1.25), (xx, sgn * 1.56, 1.30), (xx, sgn * 1.56, 2.55), (xx, sgn * 1.50, 2.60)], 0.016, 14)
            for k in range(9):
                box(g, "black", (3.75 + k * 0.13, sgn * 1.505, 2.83), (0.07, 0.012, 0.18), 0.004, 1)
                box(g, "body", (3.75 + k * 0.13 + 0.03, sgn * 1.51, 2.83), (0.03, 0.012, 0.18), 0.004, 1)
            box(g, "red", (6.82, sgn * 1.502, 2.07), (0.36, 0.006, 2.04), 0.0, 1)
    # logo lateral
    for sgn in (-1, 1):
        lx = doors[0] + 0.98
        cyl(g, "red", (lx, sgn * 1.50, 1.14), (lx, sgn * 1.51, 1.14), 0.075, seg=40)
        cyl(g, "gloss_black", (lx, sgn * 1.51, 1.14), (lx, sgn * 1.513, 1.14), 0.062, seg=40)
        for k in (-1, 0, 1):
            box(g, "red", (0, 0, 0), (0.026, 0.004, 0.026), 0, 1,
                M=Matrix.Translation((lx + k * 0.035, sgn * 1.515, 1.14)) @ Matrix.Rotation(math.radians(45), 4, 'Y'))
    # ----- techo
    N = 44
    pts = [(HW * math.cos(math.pi * k / N), 3.1 + RH * math.sin(math.pi * k / N)) for k in range(N + 1)] + \
          [(HW * 0.943 * math.cos(math.pi * k / N), 3.1 + (RH - 0.04) * math.sin(math.pi * k / N)) for k in range(N, -1, -1)]
    loft(g, "roof", [[(xa, y, z) for y, z in pts], [(xb, y, z) for y, z in pts]], close=True, caps=True)
    # ----- piso
    box(g, "floor", ((xa + xb) / 2, 0, FLOOR - 0.025), (xb - xa, 2.9, 0.05), 0.005, 1)
    # ----- interior
    for si, (a_, b_) in enumerate(spans):
        for sgn in (-1, 1):
            seat_bank(g, sgn, a_ + 0.12, b_ - 0.12, white_first=(si == len(spans) - 1 and not cab), white_last=(si == 0))
    pax_b = 3.5 if cab else xb
    handles_rails(g, xa + 0.3, pax_b - 0.1, doors)
    ceiling(g, xa, pax_b + (0.1 if cab else 0))
    passenger_end(g, xa + 0.02, -1)
    if not cab: passenger_end(g, xb - 0.02, 1)
    roof_equipment(g, xa, xb)
    underframe(g, xa, xb, None)
    for xb_ in ((-5.9, 5.9) if not cab else (-5.9, 4.6)):
        bogie(g, xb_)
    # ----- cabina
    if cab:
        px = 3.5
        box(g, "desk", (px, 0.9, 2.07), (0.08, 1.2, 2.05), 0.01, 2)
        box(g, "desk", (px, -1.05, 2.07), (0.08, 0.7, 2.05), 0.01, 2)
        box(g, "desk", (px, -0.15, 2.65), (0.08, 0.9, 0.9), 0.01, 2)
        box(g, "glass", (px, -0.15, 2.0), (0.01, 0.62, 0.85))
        box(g, "ceiling", ((px + 7.0) / 2, 0, 3.03), (7.0 - px, 2.8, 0.04), 0.01, 2)
        box(g, "light", ((px + 7.0) / 2, 0, 3.0), (2.6, 0.2, 0.02), 0.006, 2)
        dx = 6.55
        prof = [(dx - 0.15, 1.05), (dx + 0.45, 1.05), (dx + 0.45, 1.5), (dx + 0.12, 1.66), (dx - 0.1, 1.56), (dx - 0.15, 1.3)]
        loft(g, "desk", [[(x, -1.05, z) for x, z in prof], [(x, 1.05, z) for x, z in prof]], close=True, caps=True)
        for yy, ww in ((-0.55, 0.34), (-0.1, 0.34), (0.35, 0.3)):
            M = Matrix.Translation((dx + 0.15, yy, 1.6)) @ Matrix.Rotation(math.radians(-24), 4, 'Y')
            box(g, "black", (0, 0, 0), (0.03, ww + 0.04, 0.25), 0.008, 2, M=M)
            M2 = Matrix.Translation((dx + 0.15 - 0.017, yy, 1.6)) @ Matrix.Rotation(math.radians(-24), 4, 'Y')
            box(g, "screen", (0, 0, 0), (0.006, ww - 0.02, 0.2), 0.002, 1, M=M2)
        for r in range(3):
            for c in range(14):
                xx = dx - 0.06 + r * 0.06; yy = -0.9 + c * 0.065
                cyl(g, "amber" if (r * 14 + c) % 7 == 0 else ("headlight" if (r + c) % 9 == 0 else "steel"),
                    (xx, yy, 1.62 - r * 0.03), (xx + 0.02, yy, 1.62 - r * 0.03 + 0.012), 0.014, seg=24)
        cyl(g, "black", (dx, 0.82, 1.58), (dx, 0.82, 1.62), 0.05, seg=40)
        tube(g, "black", [(dx, 0.82, 1.62), (dx - 0.05, 0.82, 1.75)], 0.014, 14)
        box(g, "black", (0, 0, 0), (0.12, 0.05, 0.06), 0.018, 4, M=Matrix.Translation((dx - 0.05, 0.82, 1.78)))
        sx, sy = 5.5, 0.0
        cyl(g, "iron", (sx, sy, FLOOR), (sx, sy, FLOOR + 0.28), 0.06, seg=24)
        cyl(g, "iron", (sx, sy, FLOOR), (sx, sy, FLOOR + 0.03), 0.26, 0.26, seg=48)
        box(g, "seat_base", (sx, sy, FLOOR + 0.32), (0.48, 0.5, 0.1), 0.04, 4)
        M = Matrix.Translation((sx - 0.22, sy, FLOOR + 0.66)) @ Matrix.Rotation(math.radians(10), 4, 'Y')
        box(g, "seat_base", (0, 0, 0), (0.1, 0.46, 0.62), 0.04, 4, M=M)
        for s2 in (-1, 1):
            box(g, "seat_base", (sx, sy + s2 * 0.29, FLOOR + 0.5), (0.34, 0.05, 0.05), 0.015, 2)
        tube(g, "pole", [(px + 0.05, 0.4, FLOOR), (px + 0.05, 0.4, 2.9)], 0.02, 24)
        build_nose(g, xb, texts, dest, num)
    return g, (xa, xb, cab), texts

# ----------------------------------------------------------------- fuelles intercirculacion
def bellows(g, xa, xb):
    nr, npnts = 112, 48
    rings = []
    for k in range(nr):
        t = k / (nr - 1)
        x = xa + (xb - xa) * t
        taper = min(1.0, t * 12, (1 - t) * 12)
        rip = abs(((t * 9) % 1) - 0.5) * 2          # onda triangular
        s = 1.0 + 0.09 * rip * taper
        ring = []
        for i in range(npnts):
            th = 2 * math.pi * i / npnts
            c, sn = math.cos(th), math.sin(th)
            y = 0.80 * s * math.copysign(abs(c) ** 0.5, c)
            z = 2.07 + 1.0 * s * math.copysign(abs(sn) ** 0.5, sn)
            ring.append((x, y, z))
        rings.append(ring)
    loft(g, "rubber", rings, close=True)
    # marcos de acero en los extremos
    for x in (xa, xb):
        r1 = [(x, 0.80 * math.copysign(abs(math.cos(2 * math.pi * i / npnts)) ** 0.5, math.cos(2 * math.pi * i / npnts)),
               2.07 + 1.0 * math.copysign(abs(math.sin(2 * math.pi * i / npnts)) ** 0.5, math.sin(2 * math.pi * i / npnts)))
              for i in range(npnts)]
        r2 = [(x + (0.03 if x == xa else -0.03), y * 1.02, 2.07 + (z - 2.07) * 1.02) for _, y, z in r1]
        loft(g, "steel", [r1, r2], close=True)
    # piso pasarela
    box(g, "steel", ((xa + xb) / 2, 0, FLOOR - 0.01), (xb - xa + 0.1, 1.5, 0.02), 0.004, 1)

# ----------------------------------------------------------------- emision a Blender
def emit(g, name, coll, M=Matrix.Identity(4), recalc=True):
    total = 0
    for mat, (verts, faces) in g.d.items():
        if not faces: continue
        bm = bmesh.new()
        bv = [bm.verts.new(p) for p in verts]
        for fc in faces:
            try: bm.faces.new([bv[i] for i in fc])
            except ValueError: pass
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        for f in bm.faces: f.smooth = True
        for e in bm.edges:
            if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(32): e.smooth = False
        me = bpy.data.meshes.new(f"{name}_{mat}")
        bm.to_mesh(me); bm.free()
        me.materials.append(MATS[mat])
        ob = bpy.data.objects.new(f"{name}_{mat}", me)
        ob.matrix_world = M
        coll.objects.link(ob)

def add_text(name, coll, txt, M, size, mat):
    cu = bpy.data.curves.new(name, 'FONT'); cu.body = txt; cu.size = size
    cu.align_x = 'CENTER'; cu.align_y = 'CENTER'; cu.extrude = 0.004
    ob = bpy.data.objects.new(name + "_c", cu); bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob); bpy.data.curves.remove(cu)
    me.materials.append(MATS[mat])
    o2 = bpy.data.objects.new(name, me); o2.matrix_world = M; coll.objects.link(o2)

# ----------------------------------------------------------------- escena
def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    make_materials()
    root = bpy.data.collections.new("NS16_Metro_Santiago"); bpy.context.scene.collection.children.link(root)
    kinds = ["cab"] + ["mid"] * N_MID + ["cab"]
    cursor = 0.0; total_tris = 0; ends = []
    for i, k in enumerate(kinds):
        g, (xa, xb, cab), texts = build_car(k, *((("501", "Vicente Valdés"), "142") if i == 0 else (("501", "Plaza de Maipú"), "141")))
        F = (xb + 0.8) if cab else xb
        rotated = (i == 0)
        if rotated:
            X0 = cursor + F; M = Matrix.Translation((X0, 0, 0)) @ Matrix.Rotation(math.pi, 4, 'Z')
            span = (cursor, cursor + F + 8.0)
        else:
            X0 = cursor + 8.0; M = Matrix.Translation((X0, 0, 0))
            span = (cursor, cursor + 8.0 + F)
        c = bpy.data.collections.new(f"Coche_{i + 1}_{'cabina' if cab else 'intermedio'}")
        root.children.link(c)
        emit(g, f"C{i + 1}", c, M)
        for k_, (txt, T, size, mat) in enumerate(texts):
            add_text(f"C{i + 1}_txt{k_}", c, txt, M @ T, size, mat)
        total_tris += g.tris(); ends.append(span)
        cursor = span[1] + 0.9
        print(f"coche {i + 1}: {g.tris():,} triangulos", flush=True)
    # fuelles
    gb = Geo()
    cb = bpy.data.collections.new("Fuelles"); root.children.link(cb)
    for (a0, a1), (b0, b1) in zip(ends[:-1], ends[1:]):
        bellows(gb, a1 + 0.0, b0)
    emit(gb, "Fuelle", cb); total_tris += gb.tris()
    print(f"fuelles: {gb.tris():,}")
    print(f"TOTAL ~{total_tris:,} triangulos (pre-merge)")
    xmin, xmax = ends[0][0], ends[-1][1]
    return xmin, xmax

def scene_setup(xmin, xmax):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'; sc.cycles.samples = 48; sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6; sc.cycles.transparent_max_bounces = 12
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    sc.view_settings.view_transform = 'AgX'
    # fondo de estudio: suelo infinito neutro (no es via ni anden)
    w = bpy.data.worlds.new("Studio"); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.55, 0.6, 0.66, 1); bg.inputs[1].default_value = 0.9
    mk("studio_floor", (0.5, 0.5, 0.52), 0.0, 0.55)
    cx = (xmin + xmax) / 2
    bpy.ops.mesh.primitive_plane_add(size=1, location=(cx, 0, -0.0))
    fl = bpy.context.object; fl.name = "Suelo_estudio"; fl.scale = (400, 400, 1)
    fl.data.materials.append(MATS["studio_floor"])
    # luces de estudio
    def area(name, loc, rot, size, energy, col=(1, 1, 1)):
        d = bpy.data.lights.new(name, 'AREA'); d.energy = energy; d.size = size; d.color = col
        o = bpy.data.objects.new(name, d); o.location = loc; o.rotation_euler = rot
        sc.collection.objects.link(o); return o
    area("Key", (cx - 20, 30, 28), (math.radians(60), 0, math.radians(215)), 25, 120000, (1, 0.96, 0.9))
    area("Fill", (cx + 30, -25, 18), (math.radians(65), 0, math.radians(-45)), 30, 40000, (0.85, 0.92, 1))
    area("Top", (cx, 0, 20), (0, 0, 0), 40, 60000)
    # luces interiores
    for i in range(len(bpy.data.collections["NS16_Metro_Santiago"].children) - 1):
        pass
    return cx

if __name__ == "__main__":
    xmin, xmax = build()
    cx = scene_setup(xmin, xmax)
    # estadistica final real (mallas evaluadas)
    dg = bpy.context.evaluated_depsgraph_get()
    t = 0
    for ob in bpy.data.objects:
        if ob.type == 'MESH' and ob.name != "Suelo_estudio":
            t += sum(len(p.vertices) - 2 for p in ob.data.polygons)
    print(f"TRIANGULOS REALES EN MALLAS (sin suelo de estudio): {t:,}")
    bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
    print("guardado", OUT, round(os.path.getsize(OUT) / 1e6, 1), "MB")
