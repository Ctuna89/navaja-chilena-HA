"""Tren Metro de Santiago NS-16 (Alstom, rodado neumatico) - modelo procedural para Blender (bpy).

Uso:  python3 build_ns16.py [salida.blend]
Formacion de 7 coches S+N+NP+R+N+N+S. Cabina de conduccion, interior de pasajeros y bogies.
Dimensiones (ancho 2,6 m, piso 1,20 m, 4 puertas/lado, bogies a +-5,6 m) tomadas del tren
NS-2016 para OpenBVE (OBCL: LucasBVE, DiazMedinarBVE, Manuel Mejias) y de fotos del tren real.
La grafica roja lateral (ns16_livery.json) es un trazado vectorial de sus texturas.
"""
import bpy, bmesh, math, sys, os, random, json
from mathutils import Vector, Matrix

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "ns16_metro_santiago.blend")
N_MID = 5                 # coches intermedios (tren de 7 coches)
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
        mix = nt.nodes.new("ShaderNodeMixShader"); mix.inputs[0].default_value = 0.30
        tr.inputs["Color"].default_value = (0.30, 0.34, 0.36, 1)
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
    mk("liner", (0.90, 0.89, 0.84), 0, 0.45)           # paredes interiores blancas
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
    mk("floor", (0.40, 0.41, 0.42), 0, 0.7)
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
    mk("desk", (0.085, 0.10, 0.135), 0.35, 0.42)
    mk("pole", (0.8, 0.8, 0.82), 1.0, 0.2)
    mk("tire", (0.025, 0.025, 0.027), 0.0, 0.8)
    mk("gloss_black", (0.01, 0.01, 0.012), 0.2, 0.12, coat=1.0)
    mk("chrome", (0.9, 0.9, 0.92), 1.0, 0.08)
    mk("guard", (0.36, 0.38, 0.42), 0.3, 0.5)
    mk("hubmetal", (0.16, 0.17, 0.19), 0.7, 0.4)
    mk("cab_gray", (0.70, 0.71, 0.70), 0.0, 0.5)
    mk("dmi", (0.05, 0.25, 0.85), emit=(0.10, 0.30, 1.0), strength=2.5)
    mk("ui_green", (0.2, 0.8, 0.2), emit=(0.3, 1.0, 0.25), strength=3.0)
    mk("ui_white", (0.9, 0.9, 0.9), emit=(1, 1, 1), strength=2.0)
    mk("screen_dim", (0.05, 0.06, 0.08), 0.2, 0.15, emit=(0.15, 0.17, 0.22), strength=0.6)
    mk("btn_blue", (0.05, 0.25, 0.9), 0.0, 0.25, emit=(0.1, 0.3, 1.0), strength=0.8)
    mk("btn_green", (0.1, 0.7, 0.2), 0.0, 0.25, emit=(0.2, 1.0, 0.3), strength=0.8)
    mk("btn_yellow", (0.95, 0.75, 0.05), 0.0, 0.25, emit=(1.0, 0.8, 0.1), strength=0.8)
    mk("btn_red", (0.85, 0.03, 0.03), 0.0, 0.2, coat=0.8)
    mk("desk_dark", (0.12, 0.13, 0.15), 0.2, 0.6)
    mk("panel", (0.22, 0.24, 0.28), 0.3, 0.45)
    mk("ad1", (0.15, 0.35, 0.7), 0, 0.4)
    mk("ad2", (0.95, 0.75, 0.1), 0, 0.4)
    mk("ad3", (0.2, 0.6, 0.35), 0, 0.4)

# ================================================================= DIMENSIONES
# Medidas tomadas del tren NS-2016 para OpenBVE (Train.dat y geometria de los .csv)
# y contrastadas con fotos del tren real.
FLOOR = 1.20                 # piso sobre superficie de rodadura
HW = 1.295                   # semiancho exterior (ancho 2,6 m)
SK_IN = 1.245                # cara interior de la piel
LIN_O, LIN_I = 1.24, 1.20    # revestimiento interior
SILL = 0.74                  # borde inferior del faldon
ROOF_E, ROOF_T = 3.40, 3.58  # arranque y cumbrera del techo (casi plano)
XB = 7.90                    # semilargo de caja
DOORS = (-6.54, -2.18, 2.18, 6.54)
DW, DZ1 = 1.30, 3.08         # ancho y dintel de puertas
WINS = (-4.36, 0.0, 4.36)
WW, WZ0, WZ1 = 1.50, 2.08, 3.05
BOGIES = (-5.6, 5.6)
AXLE, RT, ZA = 0.95, 0.49, 0.54
GAP = 0.60                   # separacion entre cajas (fuelle)
CAB_P = 7.25                 # mampara de cabina (coche S)
HERE = os.path.dirname(os.path.abspath(__file__))
LIVERY = json.load(open(os.path.join(HERE, "ns16_livery.json")))

def roof_half(z):
    if z <= ROOF_E: return HW
    t = min((z - ROOF_E) / (ROOF_T - ROOF_E), 1.0)
    return HW * max(0.0, 1 - t ** 4) ** 0.25

# ================================================================= NARIZ (casquete frontal)
def xf_of_z(z):
    """perfil lateral del frente (x de la cara frontal en el eje) segun el modelo OpenBVE + fotos"""
    if z <= 0.88: return 8.60 + (z - SILL) / (0.88 - SILL) * 0.06
    if z <= 1.22: return 8.66 + (z - 0.88) / 0.34 * 0.21
    if z <= 1.80: return 8.87 + 0.03 * math.sin(math.pi / 2 * (z - 1.22) / 0.58)
    if z <= 3.30: return 8.90 - 0.14 * (z - 1.80) / 1.5
    R = 0.28; dz = min(z - 3.30, R)
    return 8.76 - R + math.sqrt(max(R * R - dz * dz, 0.0))

def corner_a(z): return min(0.20, xf_of_z(z) - XB - 0.03)
def x0_of_z(z): return xf_of_z(z) - corner_a(z)

SE = 3.2
def cap_xy(z, s_, d=0.0):
    A = max(corner_a(z) - d, 0.0); b = max(roof_half(z) - d, 0.0)
    return (x0_of_z(z) + A * max(0.0, 1 - abs(s_) ** SE) ** (1 / SE) - (d if A <= 0 else 0), s_ * b, z)

def nose_at(y, z, d=0.0):
    b = max(roof_half(z) - d, 1e-3); s_ = max(-0.9995, min(0.9995, y / b))
    p = Vector(cap_xy(z, s_, d)); e = 1e-3
    pz = Vector(cap_xy(z + e, s_, d)) - p
    ds = e if s_ < 0.99 else -e
    ps = (Vector(cap_xy(z, s_ + ds, d)) - p) * (1 if ds > 0 else -1)
    n = ps.cross(pz).normalized()
    if n.dot(p - Vector((XB - 1.0, 0, z))) < 0: n = -n
    return p, n

GL_Y, GL_Z0, GL_Z1 = 0.97, 2.50, 3.47      # luna (incluye display de destino)
MK_Y, MK_Z0, MK_Z1 = 1.06, 1.47, 3.51      # mascara negra
def mask_half(z):
    r = 0.26
    if z >= MK_Z0 + r: return MK_Y
    t = z - MK_Z0
    return MK_Y - r + math.sqrt(max(0.0, r * r - (r - t) ** 2))

def plaque(g, mat, y, z, w, h, r, off=0.004, depth=0.012, bevel=0.004, nc=8, rot=0.0):
    p, n = nose_at(y, z); ML = frame_at(p, n) @ Matrix.Rotation(rot, 4, 'X')
    ring = rrect(w, h, r, nc); ring_b = rrect(w - 2 * bevel, h - 2 * bevel, max(r - bevel, 0.001), nc)
    loft(g, mat, [[(off, u, v) for u, v in ring], [(off + depth - bevel, u, v) for u, v in ring],
                  [(off + depth, u, v) for u, v in ring_b]], close=True, caps=True, M=ML)
    return p, n, ML

def surf_patch(g, mat, ylo, yhi, z0, z1, nz, ny, off):
    rows = []
    for i in range(nz + 1):
        z = z0 + (z1 - z0) * i / nz; row = []
        for j in range(ny + 1):
            y = ylo(z) + (yhi(z) - ylo(z)) * j / ny
            p, n = nose_at(y, z); row.append(p + n * off)
        rows.append(row)
    loft(g, mat, rows)

def build_nose(g, texts, dest, num):
    NS, NC = 14, 90
    cap_s = [-1 + 2 * k / NC for k in range(NC + 1)]
    cap_s += [GL_Y / HW, -GL_Y / HW, MK_Y / HW, -MK_Y / HW]
    cap_s = sorted(set(round(v, 6) for v in cap_s))
    zb = [SILL + (ROOF_T - SILL) * (1 - (1 - i / 110) ** 2.2) for i in range(111)]
    zb += [0.88, 1.22, MK_Z0, GL_Z0, GL_Z1, MK_Z1, 3.30, 3.45, ROOF_E]
    zs = []
    for z in sorted(zb):
        if not zs or z - zs[-1] > 0.003: zs.append(z)
    def outline(z, d=0.0):
        pts = []; x0 = x0_of_z(z) - (d if corner_a(z) - d <= 0 else 0)
        b = max(roof_half(z) - d, 0.0)
        for k in range(NS + 1):                                       # costado izquierdo
            pts.append(((XB + (x0 - XB) * k / NS), -b, z, "side", k))
        for s_ in cap_s[1:]:                                          # casquete
            pts.append(cap_xy(z, s_, d) + ("cap", s_))
        for k in range(NS - 1, -1, -1):                               # costado derecho
            pts.append(((XB + (x0 - XB) * k / NS), b, z, "side", k))
        return pts
    def mat_of(xc, yc, zc, kind):
        if zc < 0.88: return "skirt"
        if kind == "side":
            if zc < 1.22: return "red"
            if xc > x0_of_z(zc) - 0.05: return "red"
            if 3.30 <= zc <= 3.45: return "red"
            if zc > 3.45: return "roof"
            return "body"
        # casquete frontal
        if zc < MK_Z0: return "red"
        if GL_Z0 <= zc <= GL_Z1 and abs(yc) <= GL_Y: return "glass"
        if zc > MK_Z1: return "gloss_black"
        return "red"
    O = [outline(z) for z in zs]; I = [outline(z, 0.06) for z in zs]
    for i in range(len(zs) - 1):
        for j in range(len(O[0]) - 1):
            a, b_, c, d = O[i][j], O[i][j + 1], O[i + 1][j + 1], O[i + 1][j]
            xc = (a[0] + b_[0] + c[0] + d[0]) / 4; yc = (a[1] + b_[1] + c[1] + d[1]) / 4; zc = (a[2] + d[2]) / 2
            kind = "cap" if (a[3] == "cap" and b_[3] == "cap") else "side"
            m = mat_of(xc, yc, zc, kind)
            g.add(m, [a[:3], b_[:3], c[:3], d[:3]], [(0, 1, 2, 3)])
            if m != "glass" and a[2] >= FLOOR - 0.01:
                ai, bi, ci, di = I[i][j], I[i][j + 1], I[i + 1][j + 1], I[i + 1][j]
                g.add("desk", [di[:3], ci[:3], bi[:3], ai[:3]], [(0, 1, 2, 3)])
    # mascara negra brillante superpuesta (borde inferior con esquinas curvas)
    off = 0.003
    surf_patch(g, "gloss_black", lambda z: -mask_half(z), lambda z: mask_half(z), MK_Z0, GL_Z0, 26, 80, off)
    surf_patch(g, "gloss_black", lambda z: GL_Y, lambda z: MK_Y, GL_Z0, GL_Z1, 30, 4, off)
    surf_patch(g, "gloss_black", lambda z: -MK_Y, lambda z: -GL_Y, GL_Z0, GL_Z1, 30, 4, off)
    surf_patch(g, "gloss_black", lambda z: -MK_Y, lambda z: MK_Y, GL_Z1, MK_Z1, 6, 80, off)
    # reborde rojo redondeado alrededor de la mascara
    r = 0.26; rim = []
    for k in range(25): rim.append((-MK_Y, MK_Z1 - k * (MK_Z1 - MK_Z0 - r) / 24))
    for k in range(1, 17):
        zz = MK_Z0 + r * (1 - k / 16); rim.append((-mask_half(zz), zz))
    for k in range(1, 24): rim.append((-(MK_Y - r) + 2 * (MK_Y - r) * k / 24, MK_Z0))
    for k in range(0, 17):
        zz = MK_Z0 + r * k / 16; rim.append((mask_half(zz), zz))
    for k in range(1, 25): rim.append((MK_Y, MK_Z0 + r + k * (MK_Z1 - MK_Z0 - r) / 24))
    tube(g, "red", [p + n * 0.004 for p, n in (nose_at(y, z) for y, z in rim)], 0.018, 12)
    # burlete de la luna
    gp = [p + n * 0.007 for p, n in (nose_at(u, v) for u, v in rrect(2 * GL_Y, GL_Z1 - GL_Z0, 0.07, 10, 0.0, (GL_Z0 + GL_Z1) / 2))]
    tube(g, "rubber", gp, 0.014, 10, closed=True)
    # display de destino detras de la luna + cortina enrollable
    p, n = nose_at(0, 3.37, 0.0)
    ML = frame_at(p - n * 0.05, n)
    box(g, "screen2", (0, 0, 0), (0.02, 1.42, 0.17), 0.006, 2, M=ML)
    box(g, "desk", (-0.06, 0, 0.12), (0.10, 1.9, 0.07), 0.02, 2, M=ML)
    R = Matrix.Rotation(math.radians(-5.3), 4, 'Y') @ Matrix.Rotation(math.radians(90), 4, 'Z') @ Matrix.Rotation(math.radians(90), 4, 'X')
    texts.append((dest[0], Matrix.Translation(p - n * 0.038 + Vector((0, -0.55, 0))) @ R, 0.11, "amber"))
    texts.append((dest[1], Matrix.Translation(p - n * 0.038 + Vector((0, 0.12, 0))) @ R, 0.11, "amber"))
    # placa de numero
    plaque(g, "red", 0.02, 2.36, 0.51, 0.27, 0.035, off=0.006, depth=0.012)
    p, n = nose_at(0.02, 2.36)
    texts.append((num, Matrix.Translation(p + n * 0.022) @ R, 0.21, "white"))
    # tapa rebajada bajo la placa
    plaque(g, "skirt", 0.0, 2.08, 0.82, 0.22, 0.09, off=0.002, depth=0.012)
    for yy in (-0.36, 0.36):
        for zz in (2.0, 2.16):
            p, n = nose_at(yy, zz); cyl(g, "chrome", p + n * 0.012, p + n * 0.02, 0.008, seg=10)
    # logo Metro: ovalo rojo + tres rombos
    p, n = nose_at(0, 1.77); ML = frame_at(p + n * 0.004, n)
    def ell(rx, ry, x, N=56): return [(x, rx * math.cos(2 * math.pi * k / N), ry * math.sin(2 * math.pi * k / N)) for k in range(N)]
    loft(g, "red", [ell(0.19, 0.145, 0.0), ell(0.19, 0.145, 0.010), ell(0.183, 0.138, 0.013)], close=True, caps=True, M=ML)
    loft(g, "gloss_black", [ell(0.168, 0.124, 0.013), ell(0.168, 0.124, 0.016)], close=True, caps=True, M=ML)
    for k in (-1, 0, 1):
        box(g, "red", (0, 0, 0), (0.008, 0.074, 0.074), 0.003, 1,
            M=ML @ Matrix.Translation((0.02, k * 0.093, 0)) @ Matrix.Rotation(math.radians(45), 4, 'X'))
    # grupos opticos: blanco (exterior), rojo, ambar
    for sg in (-1, 1):
        plaque(g, "gloss_black", sg * 0.55, 1.615, 0.58, 0.17, 0.06, off=0.004, depth=0.02, rot=math.radians(-sg * 4))
        for yy, mt in ((0.73, "headlight"), (0.555, "taillight"), (0.385, "amber")):
            p, n = nose_at(sg * yy, 1.615 + (0.012 if yy > 0.6 else 0) * 0); ML = frame_at(p + n * 0.026, n)
            cyl(g, mt, (0, 0, 0), (0.012, 0, 0), 0.046, seg=40, M=ML)
            torus(g, "chrome", (0, 0, 0), 0.053, 0.008, 40, 8, M=ML @ Matrix.Rotation(math.radians(90), 4, 'Y'))
            if mt == "headlight":
                for k in range(6):
                    a_ = 2 * math.pi * k / 6
                    cyl(g, "chrome", (0.008, 0.025 * math.cos(a_), 0.025 * math.sin(a_)), (0.016, 0.025 * math.cos(a_), 0.025 * math.sin(a_)), 0.011, seg=16, M=ML)
        # rejillas inferiores (louvers)
        p, n = nose_at(sg * 0.80, 1.05); ML = frame_at(p, n)
        box(g, "skirt", (0.0, 0, 0), (0.02, 0.36, 0.24), 0.02, 2, M=ML)
        for k in range(6):
            box(g, "gloss_black", (0.012, 0, -0.1 + k * 0.04), (0.018, 0.32, 0.012), 0.004, 1, M=ML @ Matrix.Rotation(math.radians(-25), 4, 'Y'))
    # camara sobre el capot
    ML = Matrix.Translation((xf_of_z(3.5) - 0.12, 0, 3.55))
    box(g, "gloss_black", (0, 0, 0.04), (0.20, 0.40, 0.11), 0.04, 4, M=ML)
    cyl(g, "glass", (0.10, 0, 0.04), (0.105, 0, 0.04), 0.03, seg=24, M=ML)
    # limpiaparabrisas: pivote bajo-centro, brazo hacia arriba-izquierda
    piv, n0 = nose_at(0.02, 2.16)
    cyl(g, "black", piv + n0 * 0.01, piv + n0 * 0.06, 0.028, seg=24)
    arm = [nose_at(0.02 - 0.62 * t, 2.16 + 0.70 * t) for t in (0, 0.25, 0.5, 0.75, 1.0)]
    tube(g, "black", [p + n * (0.05 - 0.02 * i / 4) for i, (p, n) in enumerate(arm)], 0.011, 10)
    blade = [nose_at(-0.62, 2.55 + 0.62 * t) for t in (0, 0.33, 0.66, 1.0)]
    tube(g, "rubber", [p + n * 0.025 for p, n in blade], 0.009, 8)
    # topes y enganche
    coupler(g, 8.25, 1.0)
    # deflector de obstaculos (barra gris inferior)
    box(g, "guard", (8.55, 0, 0.32), (0.10, 2.0, 0.14), 0.03, 3)
    for sg in (-1, 1):
        box(g, "guard", (8.55, sg * 1.0, 0.25), (0.14, 0.02, 0.30), 0.006, 2)
        box(g, "guard", (8.30, sg * 0.95, 0.62), (0.12, 0.10, 0.55), 0.02, 2, M=Matrix.Translation((0, 0, 0)))
    # costado de cabina: puerta, ventanilla trapezoidal, asideros, peldano
    for sg in (-1, 1):
        y = sg * (HW + 0.004)
        door = rrect(0.44, 2.05, 0.09, 8, 8.15, 2.28)
        tube(g, "black", [(x, y, z) for x, z in door], 0.006, 6, closed=True)
        gasket(g, sg, 8.15, 2.82, 0.22, 0.78, 0.07, HW + 0.002, 0.010, 0.012, border=0.04, glass=False)
        g.add("gloss_black", [(x, sg * (HW + 0.004), z) for x, z in rrect(0.22, 0.78, 0.07, 8, 8.15, 2.82)], [tuple(range(36))])
        wpts = [(8.43, 2.52), (8.62, 2.52), (8.60, 3.02), (8.45, 3.02)]
        g.add("gloss_black", [(x, sg * (HW + 0.004), z) for x, z in wpts], [(0, 1, 2, 3)])
        tube(g, "rubber", [(x, sg * (HW + 0.006), z) for x, z in wpts], 0.012, 8, closed=True)
        for xx in (7.88, 8.42):
            tube(g, "pole", [(xx, sg * HW, 1.45), (xx, sg * (HW + 0.05), 1.50), (xx, sg * (HW + 0.05), 2.65), (xx, sg * HW, 2.70)], 0.014, 14)
        cyl(g, "chrome", (8.04, y, 2.25), (8.04, sg * (HW + 0.012), 2.25), 0.018, seg=20)
        box(g, "guard", (8.15, sg * (HW + 0.03), 0.80), (0.40, 0.10, 0.03), 0.008, 2)
        for xx in (7.98, 8.32):
            box(g, "guard", (xx, sg * (HW + 0.0), 0.86), (0.03, 0.06, 0.12), 0.005, 1)
    # piso de cabina
    pts = [cap_xy(FLOOR, sv, 0.06) for sv in cap_s]
    pts = [(CAB_P, -LIN_I, 0)] + [(min(x, 8.82), y, 0) for x, y, _ in pts] + [(CAB_P, LIN_I, 0)]
    loft(g, "floor", [[(x, y, FLOOR - 0.05) for x, y, _ in pts], [(x, y, FLOOR) for x, y, _ in pts]], close=True, caps=True)

def coupler(g, xf, z):
    """enganche automatico tipo Scharfenberg"""
    cyl(g, "iron", (xf - 0.9, 0, z), (xf + 0.55, 0, z), 0.07, seg=32)
    cyl(g, "iron", (xf - 0.2, 0, z), (xf + 0.25, 0, z), 0.11, 0.11, seg=40)
    for k in range(6):
        torus(g, "iron", (0, 0, 0), 0.115, 0.012, 40, 8, M=Matrix.Translation((xf - 0.15 + k * 0.07, 0, z)) @ Matrix.Rotation(math.radians(90), 4, 'Y'))
    box(g, "iron", (xf + 0.68, 0, z), (0.26, 0.34, 0.36), 0.04, 3)
    box(g, "steel", (xf + 0.825, 0, z), (0.035, 0.40, 0.42), 0.012, 2)
    cyl(g, "steel", (xf + 0.84, -0.09, z + 0.02), (xf + 0.96, -0.09, z + 0.02), 0.055, 0.03, seg=32)
    cyl(g, "black", (xf + 0.84, 0.09, z + 0.02), (xf + 0.845, 0.09, z + 0.02), 0.06, seg=32)
    torus(g, "steel", (0, 0, 0), 0.062, 0.01, 32, 8, M=Matrix.Translation((xf + 0.845, 0.09, z + 0.02)) @ Matrix.Rotation(math.radians(90), 4, 'Y'))
    box(g, "steel", (xf + 0.85, 0, z - 0.16), (0.05, 0.22, 0.06), 0.01, 2)
    tube(g, "iron", [(xf + 0.7, 0.18, z + 0.05), (xf + 0.75, 0.25, z - 0.05), (xf + 0.72, 0.27, z - 0.3)], 0.014, 10)
    tube(g, "rubber", [(xf + 0.6, -0.17, z - 0.1), (xf + 0.4, -0.22, z - 0.3), (xf + 0.1, -0.18, z - 0.25), (xf - 0.3, -0.12, z - 0.1)], 0.018, 10)
    box(g, "iron", (xf - 0.75, 0, z), (0.3, 0.5, 0.3), 0.04, 2)

# ================================================================= CAJA
def skin(g, sgn, a, b, za, zb):
    if b - a < 1e-3 or zb - za < 1e-3: return
    box(g, "body", ((a + b) / 2, sgn * (HW + SK_IN) / 2, (za + zb) / 2), (b - a, HW - SK_IN, zb - za), 0.004, 1)
    box(g, "liner", ((a + b) / 2, sgn * (LIN_O + LIN_I) / 2, (za + zb) / 2), (b - a, LIN_O - LIN_I, zb - za), 0.004, 1)

def side_wall(g, sgn, cab):
    xb = XB
    ops = [(d - DW / 2, d + DW / 2, "door") for d in DOORS] + [(w - WW / 2, w + WW / 2, "win") for w in WINS]
    cur = -XB
    for a, b, kind in sorted(ops):
        skin(g, sgn, cur, a, FLOOR, ROOF_E)
        if kind == "door":
            skin(g, sgn, a, b, DZ1, ROOF_E)
        else:
            skin(g, sgn, a, b, FLOOR, WZ0); skin(g, sgn, a, b, WZ1, ROOF_E)
            cx, cz, w, h = (a + b) / 2, (WZ0 + WZ1) / 2, b - a - 0.06, WZ1 - WZ0 - 0.06
            gasket(g, sgn, cx, cz, w, h, 0.13, HW, 0.012, 0.03, border=0.05)
            gasket(g, sgn, cx, cz, w, h, 0.13, LIN_I, -0.010, -0.04, border=0.05, glass=False)
            # marco interior marron oscuro (como el real)
            gasket(g, sgn, cx, cz, w - 0.05, h - 0.05, 0.11, LIN_I - 0.012, -0.004, -0.02, border=0.03, glass=False, mat="seat_base")
        cur = b
    skin(g, sgn, cur, XB, FLOOR, ROOF_E)
    # faldon con arcos sobre los neumaticos
    pts = [(-XB, FLOOR)]
    xs = sorted([b + a for b in BOGIES for a in (-AXLE, AXLE)])
    x = -XB
    poly = [(-XB, SILL)]
    for c in xs:
        for k in range(17):
            t = math.pi * k / 16
            poly.append((c - 0.52 * math.cos(t), SILL + 0.13 * math.sin(t)))
    poly += [(XB, SILL), (XB, FLOOR), (-XB, FLOOR)]
    poly = poly[::-1] if sgn < 0 else poly
    flat_poly(g, "body", poly, sgn * SK_IN, sgn * (HW - SK_IN))
    box(g, "black", (0, sgn * (HW + 0.002), FLOOR + 0.004), (2 * XB, 0.004, 0.01))
    # remaches de costura (zocalo y alero)
    for zz in (3.36, 0.80):
        x = -XB + 0.1
        while x < XB - 0.1:
            if zz > 1 or all(abs(x - c) > 0.55 for c in xs):
                cyl(g, "body", (x, sgn * HW, zz), (x, sgn * (HW + 0.006), zz), 0.0055, seg=8)
            x += 0.15
    # grafica roja (trazada)
    y = sgn * (HW + 0.002); t = sgn * 0.003
    for q in LIVERY["cab" if cab else "mid"]:
        xs_q = [p[0] for p in q]
        if any(abs(xx - d) < DW / 2 + 0.02 for d in DOORS for xx in xs_q): continue
        flat_poly(g, "red", [(px, pz) for px, pz in q], y, t)
    # letrero de destino lateral sobre ventana central
    box(g, "gloss_black", (0, sgn * (HW + 0.01), 3.19), (1.32, 0.02, 0.17), 0.012, 2)
    box(g, "screen2", (0, sgn * (HW + 0.021), 3.19), (1.24, 0.004, 0.12), 0.002, 1)
    # pulsador e intercomunicador junto a la primera puerta
    xp = DOORS[-1] - DW / 2 - 0.25
    box(g, "white", (xp, sgn * (HW + 0.004), 2.66), (0.12, 0.008, 0.12), 0.01, 2)
    cyl(g, "taillight", (xp, sgn * (HW + 0.008), 2.66), (xp, sgn * (HW + 0.014), 2.66), 0.035, seg=24)
    box(g, "steel", (xp, sgn * (HW + 0.004), 2.42), (0.10, 0.008, 0.14), 0.01, 2)
    for d in DOORS:
        door_leaves(g, sgn, d, is_open=(sgn == 1))

def door_leaves(g, sgn, xd, is_open):
    lw = DW / 2 - 0.008
    for d in (-1, 1):
        xc = xd + d * (lw / 2 + 0.004)
        if is_open: xc = xd + d * (DW / 2 + lw / 2 - 0.05)
        yc = (HW + 0.035) if is_open else (HW - 0.02)
        y = sgn * yc
        zb, zt = FLOOR + 0.01, DZ1 - 0.02
        wz0, wz1 = 1.62, 2.92
        box(g, "body", (xc, y, (zb + wz0) / 2), (lw, 0.035, wz0 - zb), 0.008, 2)
        box(g, "body", (xc, y, (zt + wz1) / 2), (lw, 0.035, zt - wz1), 0.008, 2)
        for s2 in (-1, 1):
            box(g, "body", (xc + s2 * (lw / 2 - 0.08), y, (wz0 + wz1) / 2), (0.16, 0.035, wz1 - wz0), 0.008, 2)
        cx, cz, ww, hh = xc, (wz0 + wz1) / 2, lw - 0.24, wz1 - wz0 - 0.06
        gasket(g, sgn, cx, cz, ww, hh, 0.10, yc + 0.018, 0.008, 0.02, border=0.04)
        gasket(g, sgn, cx, cz, ww, hh, 0.10, yc - 0.018, -0.008, -0.016, border=0.04, glass=False)
        box(g, "rubber", (xc - d * lw / 2, y, (zb + zt) / 2), (0.022, 0.045, zt - zb), 0.006, 1)
        yy = sgn * (yc + 0.0185); tt = sgn * 0.003
        for z0, z1 in ((1.855, 1.91), (1.665, 1.80)):
            if z1 < wz0 or z0 > wz1:
                flat_poly(g, "red", [(xc - lw / 2, z0), (xc + lw / 2, z0), (xc + lw / 2, z1), (xc - lw / 2, z1)], yy, tt)
            else:
                for xa_, xb_ in ((xc - lw / 2, xc - lw / 2 + 0.16), (xc + lw / 2 - 0.16, xc + lw / 2)):
                    flat_poly(g, "red", [(xa_, z0), (xb_, z0), (xb_, z1), (xa_, z1)], yy, tt)
    for s2 in (-1, 1):
        box(g, "black", (xd + s2 * (DW / 2 + 0.025), sgn * (HW + 0.002), (FLOOR + DZ1) / 2), (0.04, 0.02, DZ1 - FLOOR), 0.006, 2)
    box(g, "black", (xd, sgn * (HW + 0.002), DZ1 + 0.02), (DW + 0.09, 0.02, 0.05), 0.006, 2)
    box(g, "steel", (xd, sgn * (SK_IN + LIN_I) / 2, FLOOR + 0.005), (DW, HW - LIN_I + 0.04, 0.012))
    # interior: dintel de acero con remaches, tiradores, adhesivos y caja de emergencia
    box(g, "body", (xd, sgn * (LIN_I - 0.006), (DZ1 + 3.07) / 2), (DW + 0.1, 0.012, 3.07 - DZ1), 0.003, 1)
    for k in range(7):
        xx = xd - DW / 2 + 0.05 + k * (DW - 0.1) / 6
        cyl(g, "chrome", (xx, sgn * (LIN_I - 0.012), 3.06), (xx, sgn * (LIN_I - 0.016), 3.06), 0.006, seg=8)
    if not is_open:
        yin = sgn * (HW - 0.02 - 0.019)
        for dd in (-1, 1):
            xh = xd + dd * 0.09
            box(g, "chrome", (xh, yin, 1.95), (0.045, 0.008, 0.16), 0.012, 3)
            box(g, "desk_dark", (xh, yin - sgn * 0.003, 1.95), (0.025, 0.004, 0.12), 0.006, 2)
            xs_ = xd + dd * (DW / 2 - 0.20)
            box(g, "white", (xs_, sgn * (HW - 0.02 - 0.03), 2.05), (0.07, 0.003, 0.30), 0.002, 1)
            for k in range(3):
                box(g, "gloss_black", (xs_, sgn * (HW - 0.02 - 0.032), 2.16 - k * 0.09), (0.05, 0.002, 0.06))
            box(g, "gloss_black", (xs_, sgn * (HW - 0.02 - 0.032), 1.85), (0.07, 0.002, 0.10))
    xe = xd - DW / 2 - 0.20
    box(g, "white", (xe, sgn * (LIN_I - 0.01), 2.40), (0.14, 0.02, 0.15), 0.012, 2)
    box(g, "btn_red", (xe, sgn * (LIN_I - 0.022), 2.40), (0.10, 0.006, 0.11), 0.004, 1)
    cyl(g, "chrome", (xe, sgn * (LIN_I - 0.025), 2.40), (xe, sgn * (LIN_I - 0.033), 2.40), 0.012, seg=16)
    box(g, "white", (xe, sgn * (LIN_I - 0.006), 2.18), (0.13, 0.006, 0.10), 0.004, 1)
    box(g, "btn_red", (xe, sgn * (LIN_I - 0.03), 2.06), (0.025, 0.05, 0.06), 0.008, 2)
    box(g, "cab_gray", (xe, sgn * (LIN_I - 0.01), 1.88), (0.09, 0.02, 0.17), 0.01, 2)
    cyl(g, "chrome", (xe, sgn * (LIN_I - 0.02), 1.90), (xe, sgn * (LIN_I - 0.028), 1.90), 0.012, seg=16)
    # indicador luminoso de puerta
    box(g, "gloss_black", (xd + DW / 2 + 0.12, sgn * (HW + 0.004), 3.18), (0.06, 0.012, 0.10), 0.01, 2)
    cyl(g, "amber", (xd + DW / 2 + 0.12, sgn * (HW + 0.01), 3.18), (xd + DW / 2 + 0.12, sgn * (HW + 0.014), 3.18), 0.018, seg=20)

def roof(g, xa, xb):
    N = 48
    out = [(HW * math.copysign(abs(math.cos(math.pi * k / N)) ** 0.5, math.cos(math.pi * k / N)),
            ROOF_E + (ROOF_T - ROOF_E) * abs(math.sin(math.pi * k / N)) ** 0.5) for k in range(N + 1)]
    inn = [((HW - 0.05) * math.copysign(abs(math.cos(math.pi * k / N)) ** 0.5, math.cos(math.pi * k / N)),
            ROOF_E + (ROOF_T - ROOF_E - 0.05) * abs(math.sin(math.pi * k / N)) ** 0.5) for k in range(N, -1, -1)]
    pts = [(HW, ROOF_E - 0.001)] + out + [(-HW, ROOF_E - 0.001)] + inn
    loft(g, "roof", [[(xa, y, z) for y, z in pts], [(xb, y, z) for y, z in pts]], close=True, caps=True)
    # equipo de aire acondicionado bajo perfil (centro del techo)
    box(g, "roof", (0, 0, ROOF_T + 0.01), (4.1, 2.3, 0.06), 0.025, 3)
    for k in range(2):
        xc = -1.0 + 2.0 * k
        box(g, "gloss_black", (xc, 0, ROOF_T + 0.045), (1.2, 1.4, 0.012), 0.004, 1)
        for j in range(16):
            box(g, "roof", (xc - 0.56 + j * 0.075, 0, ROOF_T + 0.05), (0.02, 1.36, 0.012), 0.003, 1)
    for xc in (-5.6, 5.6):
        box(g, "roof", (xc, 0, ROOF_T + 0.008), (1.2, 1.6, 0.03), 0.01, 2)

def ceiling(g, xa, xb):
    L = xb - xa; xc = (xa + xb) / 2
    for sgn in (-1, 1):
        prof = [(LIN_I, 3.07), (1.017, 3.14), (1.017, 3.40), (1.03, 3.40), (1.03, 3.15), (LIN_I + 0.02, 3.08)]
        loft(g, "ceiling", [[(xa, sgn * y, z) for y, z in prof], [(xb, sgn * y, z) for y, z in prof]], close=True, caps=True)
        # paneles de informacion (blanco y negro) en la cara vertical
        x = xa + 0.35
        while x + 1.2 < xb - 0.2:
            box(g, "white", (x + 0.6, sgn * 1.012, 3.27), (1.16, 0.006, 0.22), 0.002, 1)
            box(g, "gloss_black", (x + 0.12, sgn * 1.009, 3.27), (0.22, 0.004, 0.22))
            box(g, "gloss_black", (x + 1.07, sgn * 1.009, 3.27), (0.18, 0.004, 0.22))
            for k in range(5):
                box(g, "black", (x + 0.32 + k * 0.12, sgn * 1.009, 3.26), (0.07, 0.003, 0.07))
                box(g, "white", (x + 0.32 + k * 0.12, sgn * 1.008, 3.26), (0.055, 0.002, 0.055))
            x += 1.3
        # franja luminosa continua bajo la cornisa + rejilla de ventilacion
        box(g, "light", (xc, sgn * 1.10, 3.103), (L - 0.3, 0.16, 0.01), 0.003, 1)
        box(g, "desk_dark", (xc, sgn * 0.94, 3.398), (L - 0.4, 0.09, 0.006))
        for k in range(4):
            box(g, "ceiling", (xc, sgn * (0.905 + k * 0.023), 3.396), (L - 0.4, 0.008, 0.006))
    box(g, "ceiling", (xc, 0, 3.42), (L, 2.06, 0.04), 0.01, 2)
    # juntas diagonales/rectas de paneles y puntos (parlantes / sensores)
    x = xa + 0.8
    while x < xb - 0.5:
        box(g, "groove", (x, 0, 3.399), (0.006, 1.7, 0.003))
        for sd in (-1, 1):
            cyl(g, "chrome", (x + 0.4, sd * 0.45, 3.40), (x + 0.4, sd * 0.45, 3.39), 0.035, seg=24)
            cyl(g, "black", (x + 0.4, sd * 0.45, 3.389), (x + 0.4, sd * 0.45, 3.388), 0.022, seg=24)
        x += 1.6
    # domo de camara
    revolve(g, "gloss_black", [(0.0, 0.0), (0.075, 0.0), (0.072, -0.03), (0.055, -0.06), (0.03, -0.075), (0.0, -0.08)], 40,
            M=Matrix.Translation((xc + 1.0, 0.3, 3.40)))
    cyl(g, "white", (xc + 1.0, 0.3, 3.40), (xc + 1.0, 0.3, 3.385), 0.09, seg=40)

def interior(g, cab):
    xa, xb = -XB + 0.05, (CAB_P - 0.05) if cab else XB - 0.05
    # piso con bandas de goma
    box(g, "floor", (0, 0, FLOOR - 0.03), (2 * XB, 2 * SK_IN, 0.06), 0.004, 1)
    edges = sorted([d + s * DW / 2 for d in DOORS for s in (-1, 1)])
    spans = [(-XB, edges[0])] + [(edges[i], edges[i + 1]) for i in range(1, len(edges) - 1, 2)] + [(edges[-1], XB)]
    for si, (a, b) in enumerate(spans):
        if cab and a > CAB_P - 0.1: continue
        bb = min(b, CAB_P - 0.05) if cab else b
        for sgn in (-1, 1):
            L = bb - a - 0.24
            if L < 0.45: continue
            n = max(1, min(4, int((L + 0.02) // 0.515)))
            w = n * 0.515
            c = (a + bb) / 2
            seat_bank(g, sgn, c - w / 2, c + w / 2, white_last=(sgn == 1), white_first=(sgn == -1))
    handles_rails(g, xa + 0.25, xb - 0.25)
    ceiling(g, -XB, (CAB_P if cab else XB))
    # testeros
    def end_wall(x, sd):
        for s in (-1, 1):
            box(g, "liner", (x, s * 0.98, 2.2), (0.06, 0.48, 2.0), 0.01, 2)
            fx = x - sd * 0.032
            for zc in (1.45, 1.75):
                box(g, "cab_gray", (fx, s * 1.0, zc), (0.006, 0.30, 0.24), 0.004, 1)
                for k in range(9):
                    box(g, "desk_dark", (fx - sd * 0.002, s * 1.0, zc - 0.10 + k * 0.025), (0.004, 0.26, 0.008))
            box(g, "steel", (fx, s * 0.98, 2.45), (0.008, 0.30, 0.42), 0.006, 2)
            box(g, "white", (fx - sd * 0.004, s * 0.98, 2.45), (0.004, 0.26, 0.38))
            for k in range(5):
                box(g, "red" if k % 2 else "gloss_black", (fx - sd * 0.007, s * 0.98 + (k - 2) * 0.035, 2.45 + (k % 3 - 1) * 0.06), (0.002, 0.02, 0.2))
            tube(g, "pole", [(fx - sd * 0.0, s * 0.76, 1.55), (fx - sd * 0.07, s * 0.76, 1.60), (fx - sd * 0.07, s * 0.76, 2.55), (fx, s * 0.76, 2.60)], 0.016, 14)
        box(g, "liner", (x, 0, 3.31), (0.06, 1.48, 0.22), 0.01, 2)
        box(g, "steel", (x + sd * 0.2, 0, FLOOR + 0.004), (0.4, 1.48, 0.012))
    end_wall(-XB + 0.03, -1)
    if not cab: end_wall(XB - 0.03, 1)

def seat_bank(g, sgn, a, b, white_first=False, white_last=False):
    n = int(round((b - a) / 0.515))
    wall = LIN_I
    box(g, "liner", ((a + b) / 2, sgn * (wall - 0.02), FLOOR + 0.06), (b - a + 0.02, 0.04, 0.12), 0.01, 2)   # zocalo
    for k in range(n):
        x0 = a + k * 0.515 + 0.006; x1 = x0 + 0.503; xc = (x0 + x1) / 2
        m = "seat_white" if ((k == 0 and white_first) or (k == n - 1 and white_last)) else "seat"
        seat_shell(g, m, sgn, x0, x1, wall)
        dm = "seat_dark" if m == "seat" else "liner"
        cyl(g, dm, (xc, sgn * (wall - 0.30), FLOOR + 0.4565), (xc, sgn * (wall - 0.30), FLOOR + 0.4595), 0.15, seg=48)
        nb = Vector((0, -sgn * 0.993, 0.117)); pb = Vector((xc, sgn * (wall - 0.083), FLOOR + 0.72))
        cyl(g, dm, pb, pb + nb * 0.003, 0.14, seg=48)
        if k % 2 == 0:
            tube(g, "steel", [(x0 + 0.02, sgn * (wall - 0.01), FLOOR + 0.25), (x0 + 0.02, sgn * (wall - 0.22), FLOOR + 0.40), (x0 + 0.02, sgn * (wall - 0.42), FLOOR + 0.425)], 0.016, 12)
    for xe in (a - 0.01, b + 0.01):
        tube(g, "steel", [(xe, sgn * 0.79, FLOOR + 0.57), (xe, sgn * (wall - 0.01), FLOOR + 0.57)], 0.014, 12)
        pts = [(xe, sgn * 0.78, FLOOR), (xe, sgn * 0.78, 2.45)]
        for k in range(1, 19):
            ph = math.radians(90 * k / 18)
            pts.append((xe, sgn * (0.78 + 0.40 * (1 - math.cos(ph))), 2.45 + 0.40 * math.sin(ph)))
        tube(g, "pole", pts, 0.019, 20)
        cyl(g, "steel", (xe, sgn * 0.78, FLOOR), (xe, sgn * 0.78, FLOOR + 0.02), 0.04, seg=24)

def handles_rails(g, xa, xb):
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
    tri = tri_loop(); ZR = 2.92
    for sgn in (-1, 1):
        tube(g, "pole", [(xa, sgn * 0.78, ZR), (xb, sgn * 0.78, ZR)], 0.019, 24)
        x = xa + 0.6
        while x < xb - 0.3:
            tube(g, "pole", [(x, sgn * 0.78, ZR), (x, sgn * 0.78, 3.40)], 0.014, 12)
            x += 1.8
        x = xa + 0.4
        while x < xb - 0.3:
            if all(abs(x - d) > DW / 2 + 0.1 for d in DOORS):
                tube(g, "pole", [(x, sgn * 0.78, ZR), (x, sgn * 0.78, ZR - 0.09)], 0.009, 10)
                tube(g, "handle", [(x, sgn * 0.78 + px, ZR - 0.09 + pz) for px, pz in tri], 0.011, 12, closed=True)
            x += 0.55
    for d in DOORS:
        if not (xa < d < xb): continue
        tube(g, "pole", [(d, 0.0, FLOOR), (d, 0.0, 3.40)], 0.021, 28)
        cyl(g, "steel", (d, 0, FLOOR), (d, 0, FLOOR + 0.02), 0.045, seg=28)
        tube(g, "pole", [(d, -0.78, ZR), (d, 0.78, ZR)], 0.019, 24)
        for sgn in (-1, 1):
            for s2 in (-1, 1):
                xx = d + s2 * (DW / 2 + 0.09)
                tube(g, "pole", [(xx, sgn * LIN_I, 1.50), (xx, sgn * (LIN_I - 0.07), 1.55), (xx, sgn * (LIN_I - 0.07), 2.85), (xx, sgn * LIN_I, 2.90)], 0.016, 16)
            # mapa de linea LED sobre la puerta
            box(g, "white", (d, sgn * (LIN_I - 0.01), 3.18), (1.0, 0.02, 0.12), 0.01, 2)
            for k in range(16):
                cyl(g, "amber" if k % 5 else "taillight", (d - 0.45 + k * 0.06, sgn * (LIN_I - 0.022), 3.18),
                    (d - 0.45 + k * 0.06, sgn * (LIN_I - 0.03), 3.18), 0.01, seg=16)
            box(g, "red", (d, sgn * (LIN_I - 0.022), 3.18), (0.92, 0.004, 0.012))

def cab_interior(g):
    """cabina vista desde el conductor (+X): espejo en Y del armado"""
    sub = Geo(); _cab_raw(sub)
    for mat, (v, f) in sub.d.items():
        g.add(mat, [(p[0], -p[1], p[2]) for p in v], [fc[::-1] for fc in f])

def _cab_raw(g):
    """cabina NS-16 segun fotos: pupitre gris azulado de ancho completo, tablero inclinado con
    pantalla izq., panel de instrumentos, DMI central, pantalla tactil der.; manipulador a la derecha"""
    px = CAB_P
    # mampara con puerta de ventana alta redondeada
    for sd, w in ((-1, 0.70), (1, 0.70)):
        box(g, "cab_gray", (px, sd * (LIN_I - w / 2), 2.31), (0.05, w, 2.22), 0.01, 2)
    box(g, "cab_gray", (px + 0.02, 0, 2.21), (0.04, 0.98, 2.0), 0.015, 3)
    wr = rrect(0.30, 0.95, 0.12, 8, 0.0, 2.45)
    g.add("glass", [(px + 0.045, u, v) for u, v in wr], [tuple(range(len(wr)))])
    tube(g, "rubber", [(px + 0.045, u, v) for u, v in wr], 0.016, 10, closed=True)
    box(g, "cab_gray", (px, 0, 3.33), (0.05, 1.0, 0.18), 0.01, 2)
    box(g, "chrome", (px + 0.06, 0.38, 2.1), (0.03, 0.03, 0.16), 0.01, 2)
    # techo y paredes de cabina
    box(g, "cab_gray", ((px + 8.6) / 2, 0, 3.37), (8.6 - px, 2.4, 0.04), 0.01, 2)
    box(g, "ceiling", ((px + 8.0) / 2, 0, 3.345), (0.5, 0.5, 0.01), 0.004, 2)
    for sd in (-1, 1):
        box(g, "cab_gray", ((px + XB) / 2, sd * (LIN_I - 0.01), 2.3), (XB - px - 0.1, 0.02, 2.1), 0.004, 1)
    # caja de cortina enrollable sobre la luna
    cyl(g, "cab_gray", (8.52, -1.05, 3.43), (8.52, 1.05, 3.43), 0.055, seg=32)
    # ---- pupitre: tres bloques (izq, hueco de rodillas al centro, der)
    def block(y0, y1, xf):
        prof = [(xf, 2.07), (xf + 0.02, 2.05), (8.74, 2.05), (8.76, 2.10), (8.76, 2.52), (8.72, 2.56), (8.60, 2.56),
                (8.585, 2.53), (8.40, 2.17), (xf + 0.02, 2.17), (xf, 2.15)]
        loft(g, "desk", [[(x, y0, z) for x, z in prof], [(x, y1, z) for x, z in prof]], close=True, caps=True)
    block(-1.18, -0.36, 8.05); block(0.36, 1.18, 8.05); block(-0.36, 0.36, 8.30)
    for y0, y1 in ((-1.16, -0.38), (0.38, 1.16)):                       # muebles bajos
        yc, w = (y0 + y1) / 2, y1 - y0
        box(g, "cab_gray", (8.42, yc, (FLOOR + 2.05) / 2), (0.66, w, 2.05 - FLOOR), 0.01, 2)
        for k in (0, 1):
            box(g, "groove", (8.088, yc - w / 4 + k * w / 2, 1.62), (0.004, w / 2 - 0.04, 0.70), 0.002, 1)
        box(g, "groove", (8.088, yc, 1.25), (0.004, w - 0.04, 0.008))
    box(g, "desk_dark", (8.62, 0, (FLOOR + 2.05) / 2), (0.24, 0.72, 2.05 - FLOOR), 0.01, 2)   # fondo del hueco
    M = Matrix.Translation((8.40, 0, FLOOR + 0.12)) @ Matrix.Rotation(math.radians(30), 4, 'Y')
    box(g, "desk_dark", (0, 0, 0), (0.30, 0.70, 0.02), 0.006, 1, M=M)      # reposapies
    tube(g, "chrome", [(8.36, -0.33, 2.03), (8.27, -0.33, 1.99), (8.27, 0.33, 1.99), (8.36, 0.33, 2.03)], 0.016, 14)
    # ---- tablero inclinado
    B = Vector((8.40, 0, 2.17)); T = Vector((8.585, 0, 2.53)); d = (T - B).normalized()
    n = Vector((-d.z, 0, d.x))
    def F(u, y, out=0.0):
        p = B + d * u + n * out + Vector((0, y, 0))
        return Matrix(((n.x, 0, d.x, p.x), (n.y, 1, d.y, p.y), (n.z, 0, d.z, p.z), (0, 0, 0, 1)))
    def disc(mat, u, y, r, h=0.012, out=0.0, seg=28):
        cyl(g, mat, (out, 0, 0), (out + h, 0, 0), r, seg=seg, M=F(u, y))
    UM = 0.20
    # pantalla izquierda
    box(g, "gloss_black", (0.01, 0, 0), (0.02, 0.40, 0.31), 0.012, 2, M=F(UM, -0.90))
    box(g, "screen_dim", (0.021, 0, 0), (0.003, 0.33, 0.24), M=F(UM, -0.90))
    # panel de instrumentos (gris)
    PY = -0.36
    box(g, "panel", (0.006, 0, 0), (0.012, 0.62, 0.35), 0.006, 2, M=F(UM, PY))
    for k, (dy, mt) in enumerate(((-0.25, "gloss_black"), (-0.19, "white"), (-0.13, "white"), (-0.07, "gloss_black"))):
        disc("chrome", UM + 0.12, PY + dy, 0.026, 0.006, 0.012)
        disc(mt, UM + 0.12, PY + dy, 0.020, 0.03, 0.018)
        box(g, "black" if mt == "white" else "white", (0.05, 0, 0), (0.004, 0.008, 0.03), M=F(UM + 0.12, PY + dy))
    disc("cab_gray", UM + 0.12, PY + 0.0, 0.03, 0.01, 0.012)                   # parlante
    for k in range(7):
        a = 2 * math.pi * k / 7
        disc("black", UM + 0.12 + 0.014 * math.sin(a), PY + 0.014 * math.cos(a), 0.004, 0.003, 0.022, seg=8)
    disc("black", UM + 0.12, PY, 0.004, 0.003, 0.022, seg=8)
    for dy in (0.065, 0.125):
        disc("chrome", UM + 0.12, PY + dy, 0.026, 0.008, 0.012); disc("btn_blue", UM + 0.12, PY + dy, 0.02, 0.012, 0.016)
    box(g, "white", (0.016, 0, 0), (0.008, 0.07, 0.07), 0.003, 1, M=F(UM + 0.12, PY + 0.225))        # voltimetro
    box(g, "black", (0.021, 0.008, 0.008), (0.002, 0.003, 0.045), M=F(UM + 0.12, PY + 0.225) @ Matrix.Rotation(math.radians(30), 4, 'X'))
    box(g, "gloss_black", (0.02, 0, 0), (0.03, 0.15, 0.07), 0.008, 2, M=F(UM - 0.02, PY - 0.19))    # radio
    box(g, "screen_dim", (0.036, -0.03, 0.01), (0.002, 0.05, 0.03), M=F(UM - 0.02, PY - 0.19))
    for i in range(3):
        for j in range(3):
            disc("cab_gray", UM - 0.035 + i * 0.014, PY - 0.15 + j * 0.016, 0.004, 0.004, 0.035, seg=8)
    box(g, "gloss_black", (0.012, 0, 0), (0.016, 0.14, 0.14), 0.01, 2, M=F(UM - 0.05, PY + 0.03))     # velocimetro
    disc("white", UM - 0.05, PY + 0.03, 0.058, 0.004, 0.02, seg=48)
    for k in range(11):
        a = math.radians(-135 + k * 27)
        box(g, "black", (0.0255, 0.048 * math.sin(a), 0.048 * math.cos(a)), (0.002, 0.003, 0.01), M=F(UM - 0.05, PY + 0.03) @ Matrix.Translation((0, 0, 0)))
    box(g, "black", (0.026, 0.0, 0.0), (0.002, 0.004, 0.05), M=F(UM - 0.05, PY + 0.03) @ Matrix.Rotation(math.radians(-40), 4, 'X'))
    disc("black", UM - 0.05, PY + 0.03, 0.012, 0.01, 0.024)
    for dy, mt in ((0.125, "btn_red"), (0.18, "btn_yellow")):
        disc("chrome", UM + 0.03, PY + dy, 0.026, 0.008, 0.012); disc(mt, UM + 0.03, PY + dy, 0.02, 0.012, 0.016)
    disc("chrome", UM - 0.08, PY + 0.20, 0.05, 0.01, 0.012, seg=48)             # manometro
    disc("gloss_black", UM - 0.08, PY + 0.20, 0.043, 0.004, 0.022, seg=48)
    box(g, "white", (0.027, 0.0, 0.0), (0.002, 0.003, 0.04), M=F(UM - 0.08, PY + 0.20) @ Matrix.Rotation(math.radians(55), 4, 'X'))
    box(g, "white", (0.014, 0, 0), (0.004, 0.08, 0.03), 0.002, 1, M=F(UM - 0.14, PY - 0.22))         # numero de tren
    # DMI central con teclas en el marco
    DY = 0.19
    box(g, "gloss_black", (0.015, 0, 0), (0.03, 0.42, 0.36), 0.015, 3, M=F(UM, DY))
    box(g, "dmi", (0.031, 0, 0), (0.003, 0.27, 0.22), M=F(UM, DY))
    for r in range(4):
        for c in range(7):
            mt = "ui_green" if (r + c) % 4 else "btn_yellow"
            box(g, mt, (0.0335, -0.11 + c * 0.037, 0.05 - r * 0.035), (0.002, 0.026, 0.02), M=F(UM, DY))
    box(g, "ui_white", (0.0335, 0, 0.09), (0.002, 0.24, 0.012), M=F(UM, DY))
    for c in range(11):
        for uu in (0.155, -0.155):
            box(g, "desk_dark", (0.032, -0.18 + c * 0.036, uu), (0.006, 0.022, 0.02), 0.003, 1, M=F(UM, DY))
            box(g, "white", (0.0352, -0.18 + c * 0.036, uu), (0.001, 0.016, 0.014), M=F(UM, DY))
    for sd in (-1, 1):
        for r in range(6):
            box(g, "desk_dark", (0.032, sd * 0.185, 0.10 - r * 0.04), (0.006, 0.022, 0.022), 0.003, 1, M=F(UM, DY))
    # pantalla tactil derecha (inclinada)
    box(g, "gloss_black", (0.012, 0, 0), (0.022, 0.42, 0.30), 0.012, 2, M=F(UM, 0.80) @ Matrix.Rotation(math.radians(-8), 4, 'Z'))
    box(g, "screen_dim", (0.024, 0, 0), (0.003, 0.34, 0.22), M=F(UM, 0.80) @ Matrix.Rotation(math.radians(-8), 4, 'Z'))
    for r in range(2):
        for c in range(3):
            box(g, "panel", (0.026, -0.11 + c * 0.11, 0.05 - r * 0.08), (0.002, 0.09, 0.065), M=F(UM, 0.80) @ Matrix.Rotation(math.radians(-8), 4, 'Z'))
    # ---- pupitre bajo: izquierda
    Z = 2.17
    for yy in (-1.02, -0.64):
        box(g, "cab_gray", (8.24, yy, Z + 0.004), (0.15, 0.15, 0.008), 0.004, 1)
        cyl(g, "gloss_black", (8.24, yy, Z), (8.24, yy, Z + 0.05), 0.03, seg=24)
        box(g, "gloss_black", (8.22, yy, Z + 0.07), (0.13, 0.03, 0.035), 0.012, 3)
        cyl(g, "chrome", (8.17, yy, Z + 0.07), (8.15, yy, Z + 0.07), 0.018, seg=16)
    for k, mt in enumerate(("white", "btn_yellow", "btn_green")):
        cyl(g, "chrome", (8.30, -0.92 + k * 0.08, Z), (8.30, -0.92 + k * 0.08, Z + 0.008), 0.024, seg=24)
        cyl(g, mt, (8.30, -0.92 + k * 0.08, Z + 0.008), (8.30, -0.92 + k * 0.08, Z + 0.02), 0.018, seg=24)
    cyl(g, "chrome", (8.13, -0.80, Z), (8.13, -0.80, Z + 0.025), 0.045, seg=40)                   # seta de emergencia
    revolve(g, "btn_red", [(0.0, 0.0), (0.052, 0.0), (0.055, 0.012), (0.045, 0.028), (0.025, 0.036), (0.0, 0.038)], 40,
            M=Matrix.Translation((8.13, -0.80, Z + 0.025)))
    box(g, "cab_gray", (8.12, -1.02, Z + 0.012), (0.08, 0.08, 0.025), 0.006, 2)
    cyl(g, "btn_green", (8.12, -1.02, Z + 0.025), (8.12, -1.02, Z + 0.04), 0.022, seg=24)
    # centro: botonera, conmutadores, microfono de mano y de cuello de ganso
    for k, mt in enumerate(("white", "btn_yellow", "gloss_black", "btn_green", "btn_yellow", "white", "btn_green", "btn_red")):
        y = -0.31 + k * 0.088
        cyl(g, "chrome", (8.35, y, Z), (8.35, y, Z + 0.006), 0.02, seg=20)
        cyl(g, mt, (8.35, y, Z + 0.006), (8.35, y, Z + 0.016), 0.015, seg=20)
    for y in (-0.12, 0.24):
        box(g, "gloss_black", (8.33, y, Z + 0.012), (0.06, 0.04, 0.02), 0.006, 2)
        box(g, "chrome", (8.33, y, Z + 0.04), (0.01, 0.01, 0.04), 0.003, 1)
    box(g, "gloss_black", (8.20, -0.95, Z + 0.03), (0.05, 0.10, 0.04), 0.012, 3)
    tube(g, "gloss_black", [(8.36, 0.02, Z), (8.36, 0.02, Z + 0.18), (8.38, 0.02, Z + 0.34), (8.42, 0.0, Z + 0.40)], 0.006, 8)
    cyl(g, "gloss_black", (8.42, 0.0, Z + 0.40), (8.45, -0.01, Z + 0.43), 0.012, seg=16)
    cyl(g, "chrome", (8.36, 0.02, Z), (8.36, 0.02, Z + 0.01), 0.025, seg=24)
    box(g, "gloss_black", (8.37, -0.20, Z + 0.02), (0.06, 0.09, 0.035), 0.012, 3)              # microfono de mano
    tube(g, "gloss_black", [(8.37, -0.24, Z + 0.02)] + [(8.37 + 0.02 * math.sin(k), -0.26 - k * 0.005, Z + 0.01 + 0.012 * math.cos(k)) for k in range(1, 14)], 0.004, 6)
    # derecha: manipulador de traccion/freno y intercomunicador
    box(g, "panel", (8.22, 0.62, Z + 0.002), (0.30, 0.30, 0.006), 0.006, 1)
    box(g, "desk_dark", (8.22, 0.62, Z + 0.006), (0.20, 0.03, 0.004))
    box(g, "gloss_black", (8.20, 0.62, Z + 0.06), (0.10, 0.11, 0.10), 0.03, 4)
    box(g, "gloss_black", (8.25, 0.62, Z + 0.10), (0.06, 0.08, 0.05), 0.02, 3)
    box(g, "panel", (8.20, 0.98, Z + 0.002), (0.26, 0.26, 0.006), 0.006, 1)
    cyl(g, "cab_gray", (8.24, 0.94, Z), (8.24, 0.94, Z + 0.02), 0.03, seg=24)
    for k in range(5):
        cyl(g, "black", (8.24 + 0.012 * math.cos(k), 0.94 + 0.012 * math.sin(k), Z + 0.02), (8.24 + 0.012 * math.cos(k), 0.94 + 0.012 * math.sin(k), Z + 0.022), 0.003, seg=6)
    for (xx, yy) in ((8.14, 1.04), (8.26, 1.06)):
        box(g, "cab_gray", (xx, yy, Z + 0.012), (0.07, 0.07, 0.02), 0.006, 2)
        cyl(g, "btn_green", (xx, yy, Z + 0.02), (xx, yy, Z + 0.035), 0.02, seg=24)
    # asiento del conductor
    sx = 7.72
    cyl(g, "iron", (sx, 0.05, FLOOR), (sx, 0.05, FLOOR + 0.40), 0.05, seg=24)
    cyl(g, "iron", (sx, 0.05, FLOOR), (sx, 0.05, FLOOR + 0.03), 0.28, seg=48)
    box(g, "seat_base", (sx, 0.05, FLOOR + 0.46), (0.48, 0.50, 0.10), 0.045, 4)
    M = Matrix.Translation((sx - 0.24, 0.05, FLOOR + 0.83)) @ Matrix.Rotation(math.radians(10), 4, 'Y')
    box(g, "seat_base", (0, 0, 0), (0.10, 0.46, 0.66), 0.045, 4, M=M)
    box(g, "seat_base", (sx - 0.27, 0.05, FLOOR + 1.24), (0.08, 0.26, 0.16), 0.035, 3)
    for s2 in (-1, 1):
        box(g, "seat_base", (sx, 0.05 + s2 * 0.29, FLOOR + 0.66), (0.36, 0.05, 0.05), 0.015, 2)
    cyl(g, "taillight", (7.4, -1.05, FLOOR + 0.1), (7.4, -1.05, FLOOR + 0.58), 0.07, seg=24)

# ================================================================= BOGIE NEUMATICO
def bogie(g, xb):
    for ax in (-AXLE, AXLE):
        x = xb + ax
        cyl(g, "iron", (x, -1.06, ZA), (x, 1.06, ZA), 0.075, seg=32)
        box(g, "iron", (x, 0, ZA), (0.30, 0.38, 0.40), 0.06, 3)
        for sg in (-1, 1):
            M = Matrix.Translation((x, sg * 1.06, ZA)) @ rot_x(-90 * sg)
            revolve(g, "tire", tire_profile(RT, 0.30, 0.29, (-0.075, 0.0, 0.075)), 80, M=M)
            hub(g, M)
            prof = [(0.10, 0.0), (0.20, 0.0), (0.20, 0.03), (0.36, 0.03), (0.36, 0.0), (0.42, 0.005), (0.452, 0.015),
                    (0.452, 0.025), (0.42, 0.045), (0.415, 0.11), (0.36, 0.11), (0.36, 0.06), (0.20, 0.06), (0.20, 0.10), (0.10, 0.10)]
            revolve(g, "wheel", prof, 72, M=Matrix.Translation((x, sg * 0.66, ZA)) @ rot_x(-90 * sg))
            bx = x + (0.5 if ax > 0 else -0.5)
            box(g, "iron", (bx, sg * 0.71, ZA), (0.10, 0.14, 0.26), 0.02, 2)
            cyl(g, "iron", (bx + (0.08 if ax > 0 else -0.08), sg * 0.71, ZA), (bx + (0.22 if ax > 0 else -0.22), sg * 0.71, ZA), 0.05, seg=20)
    for sg in (-1, 1):
        box(g, "iron", (xb, sg * 0.86, 0.66), (2.6, 0.13, 0.22), 0.04, 3)            # largueros
        for k in range(8):
            box(g, "iron", (xb - 1.05 + k * 0.3, sg * 0.86, 0.79), (0.03, 0.13, 0.05), 0.008, 1)
        for ex in (-1, 1):
            box(g, "iron", (xb + ex * 1.45, sg * 0.98, 0.46), (0.36, 0.30, 0.14), 0.035, 3)   # brazos rueda guia
            gx = xb + ex * 1.62
            revolve(g, "tire", tire_profile(0.19, 0.12, 0.10, (0.0,)), 56, M=Matrix.Translation((gx, sg * 1.08, 0.30)))
            revolve(g, "steel", [(0.03, -0.07), (0.10, -0.07), (0.10, 0.07), (0.085, 0.08), (0.05, 0.08), (0.03, 0.075)], 40,
                    M=Matrix.Translation((gx, sg * 1.08, 0.30)))
            cyl(g, "iron", (gx, sg * 1.08, 0.30), (gx, sg * 1.08, 0.50), 0.035, seg=20)
            box(g, "iron", (gx, sg * 1.08, 0.50), (0.14, 0.14, 0.06), 0.02, 2)
            box(g, "iron", (xb + ex * 0.40, sg * 1.18, 0.36), (0.30, 0.06, 0.10), 0.015, 2)   # zapata captadora
            cyl(g, "white", (xb + ex * 0.40, sg * 1.10, 0.42), (xb + ex * 0.40, sg * 1.10, 0.56), 0.035, seg=16)
            coil(g, (xb + ex * 0.30, sg * 0.86, 0.77), 0.085, 0.016, 0.24, 6)
            cyl(g, "iron", (xb + ex * 0.30, sg * 0.86, 0.765), (xb + ex * 0.30, sg * 0.86, 0.785), 0.11, seg=28)
            cyl(g, "iron", (xb + ex * 0.30, sg * 0.86, 1.005), (xb + ex * 0.30, sg * 0.86, 1.025), 0.11, seg=28)
        cyl(g, "motor", (xb, sg * 0.98, 0.66), (xb, sg * 0.98, 1.02), 0.035, seg=20)
        cyl(g, "chrome", (xb, sg * 0.98, 0.86), (xb, sg * 0.98, 1.04), 0.022, seg=16)
        tube(g, "iron", [(xb, sg * 0.30, 0.98), (xb + 0.55, sg * 0.30, 0.70)], 0.03, 12)
    tube(g, "iron", [(xb - 1.75, -0.98, 0.40), (xb - 1.75, 0.98, 0.40)], 0.05, 16)
    tube(g, "iron", [(xb + 1.75, -0.98, 0.40), (xb + 1.75, 0.98, 0.40)], 0.05, 16)
    box(g, "iron", (xb, 0, 0.66), (0.40, 1.85, 0.26), 0.05, 3)
    box(g, "iron", (xb, 0, 1.03), (0.55, 2.2, 0.10), 0.04, 3)
    cyl(g, "steel", (xb, 0, 1.08), (xb, 0, 1.12), 0.26, seg=48)
    tube(g, "motor", [(xb - 0.15, -0.8, 0.92), (xb + 0.15, 0.8, 0.90)], 0.03, 12)
    for mx in (-0.52, 0.52):
        cyl(g, "motor", (xb + mx, -0.34, 0.50), (xb + mx, 0.34, 0.50), 0.19, seg=56)
        for k in range(14):
            a = math.radians(k * 360 / 14)
            cyl(g, "motor", (xb + mx + 0.19 * math.cos(a), -0.30, 0.50 + 0.19 * math.sin(a)),
                (xb + mx + 0.19 * math.cos(a), 0.30, 0.50 + 0.19 * math.sin(a)), 0.012, seg=8)
        cyl(g, "iron", (xb + mx, -0.38, 0.50), (xb + mx, 0.38, 0.50), 0.12, seg=40)
    tube(g, "rubber", [(xb, 0.4, 1.10), (xb + 0.2, 0.8, 0.95), (xb + 0.6, 1.0, 0.7)], 0.02, 10)

def underframe(g):
    box(g, "skirt", (0, 0, 1.13), (2 * XB, 2.45, 0.05), 0.01, 1)
    for k, (x, w) in enumerate(((-3.2, 1.3), (-1.6, 1.0), (0.0, 1.5), (1.7, 1.1), (3.3, 1.2))):
        for sg in (-1, 1):
            box(g, "iron", (x, sg * 0.62, 0.86), (w, 0.82, 0.48), 0.03, 2)
            for j in range(int(w / 0.12)):
                box(g, "skirt", (x - w / 2 + 0.08 + j * 0.12, sg * 1.035, 0.86), (0.05, 0.01, 0.36), 0.003, 1)
    for sg in (-1, 1):
        tube(g, "rubber", [(-XB + 0.5, sg * 0.15, 1.08), (-4, sg * 0.2, 1.05), (4, sg * 0.2, 1.05), (XB - 0.5, sg * 0.15, 1.08)], 0.025, 12)

def build_car(kind, dest=("501", "Plaza de Maipú"), num="141"):
    g = Geo(); texts = []
    cab = kind == "cab"
    for sgn in (-1, 1):
        side_wall(g, sgn, cab)
    roof(g, -XB, XB)
    interior(g, cab)
    underframe(g)
    for b in BOGIES: bogie(g, b)
    if cab:
        cab_interior(g)
        build_nose(g, texts, dest, num)
    return g, (-XB, XB, cab), texts

# ================================================================= FUELLE
def bellows(g, xa, xb):
    nr, npnts = 64, 48
    rings = []
    def ring_at(x, s):
        r = []
        for i in range(npnts):
            th = 2 * math.pi * i / npnts; c, sn = math.cos(th), math.sin(th)
            r.append((x, 1.0 * s * math.copysign(abs(c) ** 0.45, c), 2.21 + 1.11 * s * math.copysign(abs(sn) ** 0.45, sn)))
        return r
    for k in range(nr):
        t = k / (nr - 1)
        rip = abs(((t * 8) % 1) - 0.5) * 2
        taper = min(1.0, t * 10, (1 - t) * 10)
        rings.append(ring_at(xa + (xb - xa) * t, 1.0 + 0.05 * rip * taper))
    loft(g, "rubber", rings, close=True)
    for x, d in ((xa, 1), (xb, -1)):
        loft(g, "steel", [ring_at(x, 1.0), ring_at(x + d * 0.03, 1.03)], close=True)
    box(g, "steel", ((xa + xb) / 2, 0, FLOOR - 0.01), (xb - xa + 0.1, 1.44, 0.02), 0.004, 1)

# ================================================================= ESCENA
def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    make_materials()
    root = bpy.data.collections.new("NS16_Metro_Santiago"); bpy.context.scene.collection.children.link(root)
    kinds = ["cab"] + ["mid"] * N_MID + ["cab"]
    names = ["S"] + ["N", "NP", "R", "N", "N"][:N_MID] + ["S"]
    cursor = 0.0; total = 0; ends = []
    for i, k in enumerate(kinds):
        dest, num = (("501", "Vicente Valdés"), "142") if i == 0 else (("501", "Plaza de Maipú"), "141")
        g, (xa, xb, cab), texts = build_car(k, dest, num)
        F = xb + 1.05 if cab else xb
        if i == 0:
            X0 = cursor + F; M = Matrix.Translation((X0, 0, 0)) @ Matrix.Rotation(math.pi, 4, 'Z')
            span = (cursor, cursor + F + XB)
        else:
            X0 = cursor + XB; M = Matrix.Translation((X0, 0, 0))
            span = (cursor, cursor + XB + F)
        c = bpy.data.collections.new(f"Coche_{i + 1}_{names[i]}_{'cabina' if cab else 'intermedio'}")
        root.children.link(c)
        emit(g, f"C{i + 1}", c, M)
        for k_, (txt, T, size, mat) in enumerate(texts):
            add_text(f"C{i + 1}_txt{k_}", c, txt, M @ T, size, mat)
        # letrero lateral de destino (texto)
        for sg in (-1, 1):
            R = Matrix.Rotation(math.radians(90), 4, 'X') @ Matrix.Identity(4)
            Rz = Matrix.Rotation(math.pi if sg > 0 else 0, 4, 'Z')
            T = Matrix.Translation((0, sg * (HW + 0.026), 3.19)) @ Rz @ R
            add_text(f"C{i + 1}_lat{sg}", c, "Plaza de Maipú", M @ T, 0.085, "amber")
        total += g.tris(); ends.append(span)
        cursor = span[1] + GAP
        print(f"coche {i + 1} ({names[i]}): {g.tris():,} triangulos", flush=True)
    gb = Geo()
    cb = bpy.data.collections.new("Fuelles"); root.children.link(cb)
    for (a0, a1), (b0, b1) in zip(ends[:-1], ends[1:]):
        bellows(gb, a1, b0)
    emit(gb, "Fuelle", cb); total += gb.tris()
    print(f"TOTAL ~{total:,} triangulos")
    return ends[0][0], ends[-1][1]

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
    revolve(g, "hubmetal", prof, 64, M=M)
    for k in range(bolts):
        a = 2 * math.pi * k / bolts
        cyl(g, "chrome", (0.17 * math.cos(a), 0.17 * math.sin(a), 0.09), (0.17 * math.cos(a), 0.17 * math.sin(a), 0.115), 0.016, seg=6, M=M)
    cyl(g, "chrome", (0, 0, 0.14), (0, 0, 0.17), 0.07, 0.05, seg=32, M=M)

def coil(g, c, r, wire, h, turns, mat="iron"):
    N = int(turns * 26)
    pts = [(c[0] + r * math.cos(2 * math.pi * turns * i / N), c[1] + r * math.sin(2 * math.pi * turns * i / N), c[2] + h * i / N) for i in range(N + 1)]
    tube(g, mat, pts, wire, 10)


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
