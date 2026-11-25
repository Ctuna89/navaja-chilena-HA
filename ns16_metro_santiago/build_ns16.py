"""Tren Metro de Santiago NS-16 (Alstom) - modelo procedural para Blender (bpy).

Uso:  python3 build_ns16.py [salida.blend]
Genera: cabina de conduccion + interior de pasajeros + bogies, 5 coches.
Sin vias ni anden. Fondo de estudio neutro.
"""
import bpy, bmesh, math, sys, os, random
from mathutils import Vector, Matrix

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "ns16_metro_santiago.blend")
N_MID = 3                 # coches intermedios (total = 2 cabeceros + N_MID)
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
        mix = nt.nodes.new("ShaderNodeMixShader"); mix.inputs[0].default_value = 0.16
        tr.inputs["Color"].default_value = (0.55, 0.62, 0.65, 1)
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
    mk("red", (0.70, 0.02, 0.03), 0.0, 0.22, coat=0.8)
    mk("black", (0.012, 0.012, 0.015), 0.3, 0.25)
    mk("skirt", (0.035, 0.035, 0.04), 0.2, 0.5)
    mk("glass", (1, 1, 1), glass=True)
    mk("steel", (0.8, 0.8, 0.82), 1.0, 0.2)
    mk("rubber", (0.015, 0.015, 0.016), 0, 0.85)
    mk("seat", (0.72, 0.025, 0.035), 0, 0.2, coat=0.9)  # asiento rojo moldeado
    mk("seat_dark", (0.55, 0.02, 0.03), 0, 0.25, coat=0.8)
    mk("seat_white", (0.9, 0.9, 0.9), 0, 0.25, coat=0.6)
    mk("seat_base", (0.1, 0.1, 0.11), 0.2, 0.5)
    mk("floor", (0.33, 0.34, 0.35), 0, 0.8)
    mk("groove", (0.25, 0.26, 0.27), 0, 0.9)
    mk("ceiling", (0.93, 0.93, 0.91), 0, 0.5)
    mk("light", (1, 1, 1), emit=(1.0, 0.97, 0.9), strength=4.0)
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

# ----------------------------------------------------------------- nariz de cabina
# NS-16 real: frente casi plano, marco rojo envolvente, mascara negra, parabrisas grande
def a_of_z(z):
    if z <= 1.28: return 0.55 + 0.25 * ((1.28 - z) / 0.73) ** 1.5
    if z <= 3.02: return 0.55 - 0.37 * (z - 1.28) / 1.74
    return 0.18 * max(0.0, 1 - (z - 3.02) / (TOP - 3.02)) ** 0.6

def b_of_z(z):
    if z <= 3.1: return HW if z >= FLOOR else HW - 0.06
    return HW * math.sqrt(max(0.0, 1 - ((z - 3.1) / RH) ** 2))

NE = 2 / 4.0
def nose_P(z, th, d, x0):
    a = max(a_of_z(z) - d, 0); b = max(b_of_z(z) - d, 0)
    return (x0 + a * abs(math.cos(th)) ** NE,
            b * math.copysign(abs(math.sin(th)) ** NE, math.sin(th)), z)

def mask_half(z):
    return 1.28 if z >= 1.75 else 1.28 - 0.5 * ((1.75 - z) / 0.45) ** 2

def nose_at(y, z, x0):
    b = b_of_z(z); s = min(abs(y) / b, 0.999) ** (1 / NE)
    th = math.asin(s) * (1 if y >= 0 else -1)
    p = Vector(nose_P(z, th, 0, x0)); e = 1e-3
    dz = Vector(nose_P(z + e, th, 0, x0)) - p
    dt = Vector(nose_P(z, th + e, 0, x0)) - p
    n = dt.cross(dz).normalized()
    if n.x < 0: n = -n
    return p, n

def build_nose(g, x0, texts, NZ=64, NT=96):
    zs_o = [0.55 + (TOP - 0.55) * (1 - (1 - i / NZ) ** 2) for i in range(NZ + 1)]
    ths = [-math.pi / 2 + math.pi * j / NT for j in range(NT + 1)]
    def outer_mat(zc, yc):
        ay = abs(yc)
        if zc < 0.95: return "skirt"
        if zc < 1.30: return "red"
        if zc <= 3.04:
            if ay <= mask_half(zc):
                if 1.80 <= zc <= 2.52 and ay <= 1.14: return "glass"
                return "black"
            return "red"
        return "roof"
    for i in range(NZ):
        z0, z1 = zs_o[i], zs_o[i + 1]; zc = (z0 + z1) / 2
        for j in range(NT):
            thc = (ths[j] + ths[j + 1]) / 2
            yc = nose_P(zc, thc, 0, x0)[1]
            m = outer_mat(zc, yc)
            q = [nose_P(z0, ths[j], 0, x0), nose_P(z0, ths[j + 1], 0, x0),
                 nose_P(z1, ths[j + 1], 0, x0), nose_P(z1, ths[j], 0, x0)]
            g.add(m, q, [(0, 1, 2, 3)])
            if m != "glass" and z0 >= FLOOR - 0.02:
                qi = [nose_P(z0, ths[j], 0.09, x0), nose_P(z0, ths[j + 1], 0.09, x0),
                      nose_P(z1, ths[j + 1], 0.09, x0), nose_P(z1, ths[j], 0.09, x0)]
                g.add("desk", qi[::-1], [(0, 1, 2, 3)])
    # grupos opticos (blanco exterior, rojo, ambar)
    for sg in (-1, 1):
        p, n = nose_at(sg * 0.93, 1.42, x0)
        oriented_box(g, "black", p + n * 0.004, n, (0.02, 0.62, 0.13), 0.01, 2)
        for yy, mt, r in ((1.12, "headlight", 0.032), (0.95, "taillight", 0.03), (0.79, "amber", 0.027)):
            p, n = nose_at(sg * yy, 1.42, x0)
            cyl(g, mt, p - n * 0.01, p + n * 0.016, r, seg=40)
        p, n = nose_at(sg * 0.9, 0.8, x0)
        oriented_box(g, "red", p - n * 0.05, n, (0.34, 0.70, 0.30), 0.05, 3)   # topes
    # rejilla / capot bajo el parabrisas
    p, n = nose_at(0, 1.58, x0)
    oriented_box(g, "black", p + n * 0.004, n, (0.012, 0.70, 0.13), 0.04, 3)
    # logo Metro: ovalo rojo con tres rombos
    p, n = nose_at(0, 1.38, x0)
    up = Vector((0, 0, 1)); t = up.cross(n).normalized(); w = n.cross(t).normalized()
    ML = Matrix(((n.x, t.x, w.x, p.x), (n.y, t.y, w.y, p.y), (n.z, t.z, w.z, p.z), (0, 0, 0, 1)))
    def ell(rx, ry, x, N=48): return [(x, rx * math.cos(2 * math.pi * k / N), ry * math.sin(2 * math.pi * k / N)) for k in range(N)]
    loft(g, "red", [ell(0.17, 0.115, 0.0), ell(0.17, 0.115, 0.012)], close=True, caps=True, M=ML)
    loft(g, "black", [ell(0.15, 0.095, 0.012), ell(0.15, 0.095, 0.016)], close=True, caps=True, M=ML)
    for k in (-1, 0, 1):
        box(g, "red", (0.02, k * 0.08, 0), (0.006, 0.062, 0.062), 0.0, 1,
            M=ML @ Matrix.Rotation(math.radians(45), 4, 'X') @ Matrix.Identity(4))
    # placa de numero y display de destino
    p, n = nose_at(0, 1.74, x0)
    oriented_box(g, "red", p + n * 0.005, n, (0.015, 0.42, 0.21), 0.012, 2)
    p, n = nose_at(0, 2.70, x0)
    oriented_box(g, "screen2", p + n * 0.004, n, (0.014, 2.0, 0.26), 0.01, 2)
    # camara en capot y limpiaparabrisas
    p, n = nose_at(0, 3.30, x0)
    oriented_box(g, "black", p + n * 0.02, n, (0.12, 0.36, 0.13), 0.02, 3)
    for sg in (-1, 1):
        p, n = nose_at(sg * 0.2, 2.1, x0)
        M = Matrix.Translation(p + n * 0.02) @ Matrix.Rotation(math.radians(sg * 25), 4, 'X')
        box(g, "black", (0, 0, 0.0), (0.012, 0.012, 0.62), 0.003, 1, M=M)
    # acoplador
    cyl(g, "iron", (x0 + 0.55, 0, 0.70), (x0 + 0.95, 0, 0.70), 0.14, 0.10, seg=48)
    box(g, "iron", (x0 + 0.52, 0, 0.70), (0.28, 0.32, 0.26), 0.04, 2)
    # textos (se convierten a malla al final)
    slope = math.radians(-12)
    for txt, z, size, mat in (("Plaza de Maipú", 2.71, 0.17, "amber"), ("141", 1.74, 0.20, "white")):
        p, n = nose_at(0, z, x0)
        R = Matrix.Rotation(slope, 4, 'Y') @ Matrix.Rotation(math.radians(90), 4, 'Z') @ Matrix.Rotation(math.radians(90), 4, 'X')
        T = Matrix.Translation(p + n * 0.016) @ R
        texts.append((txt, T, size, mat))
    # piso de cabina
    pts = [nose_P(1.05, th, 0.09, x0) for th in ths]
    ring0 = [(x, y, FLOOR - 0.05) for x, y, _ in pts]
    ring1 = [(x, y, FLOOR) for x, y, _ in pts]
    loft(g, "floor", [ring0, ring1], close=True, caps=True)

# ----------------------------------------------------------------- coche
def spans_to_windows(spans, cabwin=None):
    wins = []
    for a, b in spans:
        L = b - a - 0.3
        if L < 0.6: continue
        n = max(1, round(L / 1.9))
        w = (L - (n - 1) * 0.22) / n
        for k in range(n):
            x0 = a + 0.15 + k * (w + 0.22)
            wins.append((x0, x0 + w, "window"))
    return wins

WZ0, WZ1 = 1.50, 2.62

def side_pieces(g, sgn, openings, xa, xb):
    z0, z1 = FLOOR, 3.1
    def solid(a, b, za, zb):
        if b - a < 1e-3 or zb - za < 1e-3: return
        box(g, "body", ((a + b) / 2, sgn * 1.47, (za + zb) / 2), (b - a, 0.06, zb - za), 0.012, 2)
        box(g, "liner", ((a + b) / 2, sgn * 1.42, (za + zb) / 2), (b - a, 0.04, zb - za), 0.008, 1)
    cur = xa
    for a, b, kind in sorted(openings):
        solid(cur, a, z0, z1)
        if kind == "door":
            solid(a, b, 2.95, z1)
        else:
            solid(a, b, z0, WZ0); solid(a, b, WZ1, z1)
            zc = (WZ0 + WZ1) / 2
            box(g, "glass", ((a + b) / 2, sgn * 1.47, zc), (b - a, 0.012, WZ1 - WZ0))
            for zz in (WZ0, WZ1):          # marco negro de goma
                box(g, "black", ((a + b) / 2, sgn * 1.495, zz), (b - a + 0.06, 0.03, 0.07), 0.012, 2)
            for xx in (a, b):
                box(g, "black", (xx, sgn * 1.495, zc), (0.07, 0.03, WZ1 - WZ0 + 0.07), 0.012, 2)
        cur = b
    solid(cur, xb, z0, z1)

def red_band(g, sgn, spans):
    """franja roja escalonada del NS-16 sobre acero inox"""
    for a, b in spans:
        if b - a < 0.8: continue
        steps = [(a, b - 1.4, 1.22, 1.40), (b - 1.4, b - 1.05, 1.22, 1.62), (b - 1.05, b - 0.7, 1.22, 1.85),
                 (b - 0.7, b, 1.22, 2.05)]
        for x0, x1, z0, z1 in steps:
            if x1 > x0 + 0.01:
                box(g, "red", ((x0 + x1) / 2, sgn * 1.505, (z0 + z1) / 2), (x1 - x0, 0.006, z1 - z0), 0.002, 1)

def door_leaves(g, sgn, xd, is_open, w=1.3):
    lw = w / 2 - 0.01
    for k, d in enumerate((-1, 1)):
        xc = xd + d * (lw / 2 + 0.005)
        if is_open: xc = xd + d * (w / 2 + lw / 2 - 0.06)
        y = sgn * (1.53 if is_open else 1.475)
        zb, zt = FLOOR + 0.02, 2.93
        wz0, wz1 = 1.42, 2.78
        box(g, "body", (xc, y, (zb + wz0) / 2), (lw, 0.04, wz0 - zb), 0.01, 2)
        box(g, "body", (xc, y, (zt + wz1) / 2), (lw, 0.04, zt - wz1), 0.01, 2)
        for s2 in (-1, 1):
            box(g, "body", (xc + s2 * (lw / 2 - 0.07), y, (wz0 + wz1) / 2), (0.14, 0.04, wz1 - wz0), 0.01, 2)
        zc = (wz0 + wz1) / 2
        box(g, "glass", (xc, y, zc), (lw - 0.14, 0.012, wz1 - wz0))
        # marco negro de la ventana de la hoja
        for zz in (wz0, wz1):
            box(g, "black", (xc, y + sgn * 0.022, zz), (lw - 0.1, 0.012, 0.035), 0.006, 2)
        for s2 in (-1, 1):
            box(g, "black", (xc + s2 * (lw / 2 - 0.07), y + sgn * 0.022, zc), (0.035, 0.012, wz1 - wz0 + 0.03), 0.006, 2)
        box(g, "rubber", (xc + d * -lw / 2, y, 1.99), (0.025, 0.05, 1.9), 0.006, 1)
    for s2 in (-1, 1):
        box(g, "black", (xd + s2 * (w / 2 + 0.03), sgn * 1.5, 2.0), (0.05, 0.03, 1.95), 0.008, 2)
    box(g, "black", (xd, sgn * 1.5, 3.0), (w + 0.12, 0.03, 0.08), 0.008, 2)
    box(g, "steel", (xd, sgn * 1.43, FLOOR + 0.005), (w, 0.12, 0.012))

def seat_bank(g, sgn, a, b, white_idx=()):
    n = int((b - a) // 0.52)
    if n < 1: return
    off = (b - a - n * 0.52) / 2
    wall = sgn * 1.40
    # panel blanco de pared bajo el asiento + tubo frontal de acero
    box(g, "liner", ((a + b) / 2, wall - sgn * 0.05, FLOOR + 0.22), (n * 0.52 + 0.04, 0.08, 0.44), 0.015, 2)
    tube(g, "steel", [(a + off, wall - sgn * 0.44, FLOOR + 0.36), (b - off, wall - sgn * 0.44, FLOOR + 0.36)], 0.016, 16)
    for xe in (a + off, b - off):
        tube(g, "steel", [(xe, wall - sgn * 0.44, FLOOR + 0.36), (xe, wall - sgn * 0.3, FLOOR + 0.40), (xe, wall - sgn * 0.08, FLOOR + 0.42)], 0.016, 14)
    for k in range(n):
        xc = a + off + 0.26 + k * 0.52
        m = "seat_white" if (k + int(abs(a) * 3)) % 7 == 0 and False else "seat"
        # concha del asiento
        Mp = Matrix.Translation((xc, wall - sgn * 0.24, FLOOR + 0.44)) @ Matrix.Rotation(math.radians(-sgn * -3), 4, 'X')
        box(g, m, (0, 0, 0), (0.50, 0.46, 0.07), 0.032, 5, M=Mp)
        cyl(g, "seat_dark", (xc, wall - sgn * 0.24, FLOOR + 0.478), (xc, wall - sgn * 0.24, FLOOR + 0.482), 0.165, seg=48)
        # respaldo curvo
        Mb = Matrix.Translation((xc, wall - sgn * 0.06, FLOOR + 0.78)) @ Matrix.Rotation(math.radians(-sgn * 9), 4, 'X')
        box(g, m, (0, 0, 0), (0.50, 0.075, 0.62), 0.04, 5, M=Mb)
        cyl(g, "seat_dark", (xc, wall - sgn * 0.098, FLOOR + 0.80), (xc, wall - sgn * 0.102, FLOOR + 0.80), 0.17, seg=48,
            M=Matrix.Translation((0, 0, 0)))
    for xe in (a + 0.02, b - 0.02):
        box(g, "glass", (xe, sgn * 1.02, FLOOR + 0.92), (0.015, 0.78, 0.9))
        tube(g, "steel", [(xe, sgn * 0.62, FLOOR), (xe, sgn * 0.62, FLOOR + 1.3), (xe, sgn * 0.75, FLOOR + 1.46),
                          (xe, sgn * 1.38, FLOOR + 1.46)], 0.02, 16)

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
        tube(g, "pole", [(xd, 0.0, FLOOR), (xd, 0.0, 2.95)], 0.021, 28)
        for sgn in (-1, 1):
            for s2 in (-1, 1):
                # pasamanos curvo de puerta (arco desde piso hasta pared)
                R = 0.55; y0 = 0.80
                pts = [(xd + s2 * 0.74, sgn * y0, FLOOR), (xd + s2 * 0.74, sgn * y0, 1.95)]
                for k in range(1, 17):
                    ph = math.radians(90 * k / 16)
                    pts.append((xd + s2 * 0.74, sgn * (y0 + R * (1 - math.cos(ph))), 1.95 + R * math.sin(ph)))
                tube(g, "pole", pts, 0.019, 20)
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
                box(g, "skirt", ((a2 + b2) / 2, sgn * 1.47, 0.82), (b2 - a2, 0.04, 0.3), 0.02, 2)
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

def bogie(g, xb):
    ys = (-1, 1)
    for ax in (-1.25, 1.25):
        x = xb + ax
        cyl(g, "steel", (x, -1.0, 0.425), (x, 1.0, 0.425), 0.09, seg=40)
        for sg in ys:
            # rueda (perfil r,a ; a desde la cara interior)
            prof = [(0.10, 0.0), (0.20, 0.0), (0.20, 0.03), (0.37, 0.03), (0.37, 0.0), (0.43, 0.005),
                    (0.465, 0.015), (0.465, 0.025), (0.43, 0.045), (0.425, 0.14), (0.37, 0.14),
                    (0.37, 0.06), (0.20, 0.06), (0.20, 0.13), (0.10, 0.13)]
            prof = [(r, a + 0.0) for r, a in prof]
            Mw = Matrix.Translation((x, sg * 0.665, 0.425)) @ rot_x(-90 * sg)
            revolve(g, "wheel", prof, 128, M=Mw)
            # disco de freno
            Md = Matrix.Translation((x, sg * 0.42, 0.425)) @ rot_x(-90 * sg)
            revolve(g, "steel", [(0.12, 0), (0.30, 0), (0.30, 0.035), (0.12, 0.035)], 96, M=Md)
            box(g, "iron", (x, sg * 0.42, 0.74), (0.16, 0.09, 0.1), 0.015, 2)
            # caja de grasa + resorte primario helicoidal
            box(g, "iron", (x, sg * 0.90, 0.44), (0.24, 0.2, 0.22), 0.03, 2)
            helix = [(x + 0.075 * math.cos(2 * math.pi * 4.5 * t), sg * 0.90 + 0.075 * math.sin(2 * math.pi * 4.5 * t),
                      0.55 + 0.14 * t) for t in [i / 100 for i in range(101)]]
            tube(g, "steel", helix, 0.0085, 10)
            cyl(g, "iron", (x, sg * 0.90, 0.54), (x, sg * 0.90, 0.56), 0.1, seg=32)
        # engranaje caja reductora
        box(g, "iron", (x, 0.0, 0.43), (0.3, 0.3, 0.36), 0.05, 3)
    # chasis
    for sg in ys:
        box(g, "iron", (xb, sg * 0.90, 0.77), (3.0, 0.16, 0.19), 0.035, 3)
        for k in range(10):   # nervaduras
            box(g, "iron", (xb - 1.35 + k * 0.3, sg * 0.90, 0.88), (0.04, 0.16, 0.05), 0.006, 1)
        # amortiguador secundario aire (fuelle)
        prof = [(0.0, 0.0), (0.16, 0.0), (0.19, 0.02), (0.15, 0.04), (0.19, 0.06), (0.15, 0.08), (0.19, 0.10),
                (0.17, 0.115), (0.0, 0.115)]
        # perfil abierto -> se cierra con eje; usamos revolve con radio minimo
        prof = [(max(r, 0.001), a) for r, a in prof]
        revolve(g, "rubber", prof, 64, M=Matrix.Translation((xb, sg * 0.88, 0.865)))
        # amortiguadores verticales
        for ax in (-1.25, 1.25):
            cyl(g, "iron", (xb + ax * 0.7, sg * 0.99, 0.65), (xb + ax * 0.7, sg * 0.99, 0.97), 0.03, seg=20)
    for cx in (-0.62, 0.62):
        cyl(g, "iron", (xb + cx, -0.92, 0.76), (xb + cx, 0.92, 0.76), 0.085, seg=40)
    # motores de traccion
    for mx in (-0.72, 0.72):
        cyl(g, "motor", (xb + mx, -0.34, 0.50), (xb + mx, 0.34, 0.50), 0.205, seg=64)
        for k in range(12):
            a = math.radians(k * 30)
            cyl(g, "motor", (xb + mx + 0.205 * math.cos(a), -0.3, 0.50 + 0.205 * math.sin(a)),
                (xb + mx + 0.205 * math.cos(a), 0.3, 0.50 + 0.205 * math.sin(a)), 0.012, seg=10)
        # cardan al eje
        tube(g, "iron", [(xb + mx, 0.2, 0.5), (xb + mx * 1.3 + (0.5 if mx > 0 else -0.5) * 0.2, 0.2, 0.46),
                         (xb + (1.25 if mx > 0 else -1.25), 0.2, 0.44)], 0.04, 14)
    # zapata captadora de corriente (tercer riel)
    box(g, "iron", (xb + 1.45, 1.15, 0.52), (0.35, 0.08, 0.1), 0.02, 2)
    box(g, "steel", (xb + 1.45, 1.38, 0.5), (0.4, 0.2, 0.025), 0.006, 1)
    # cables a la caja
    tube(g, "rubber", [(xb, 0.4, 0.95), (xb + 0.2, 0.7, 0.85), (xb + 0.9, 1.0, 0.7)], 0.02, 10)

def build_car(kind):
    g = Geo(); texts = []
    cab = kind == "cab"
    xa, xb = -8.0, (7.0 if cab else 8.0)
    if cab:
        doors = [-5.4, -0.2]
        spans = [(xa, -6.05), (-4.75, -0.85), (0.45, 3.45)]
        openings = [(d - 0.65, d + 0.65, "door") for d in doors]
        openings += spans_to_windows(spans)
        openings += [(5.15, 6.05, "door")]
    else:
        doors = [-5.4, 0.0, 5.4]
        spans = [(xa, -6.05), (-4.75, -0.65), (0.65, 4.75), (6.05, xb)]
        openings = [(d - 0.65, d + 0.65, "door") for d in doors]
        openings += spans_to_windows(spans)
    for sgn in (-1, 1):
        side_pieces(g, sgn, openings, xa, xb)
        red_band(g, sgn, spans)
        for d in doors:
            door_leaves(g, sgn, d, is_open=(sgn == 1))
    if cab:
        for sgn in (-1, 1):   # puerta lateral de cabina (cerrada)
            xc = 5.6
            box(g, "body", (xc, sgn * 1.475, 2.02), (0.86, 0.04, 1.85), 0.01, 2)
            box(g, "glass", (xc, sgn * 1.5, 2.35), (0.30, 0.012, 0.95))
            for zz in (1.87, 2.83):
                box(g, "black", (xc, sgn * 1.51, zz), (0.36, 0.014, 0.04), 0.006, 1)
            for xx in (xc - 0.17, xc + 0.17):
                box(g, "black", (xx, sgn * 1.51, 2.35), (0.04, 0.014, 1.0), 0.006, 1)
    # ----- techo
    N = 44
    pts = [(HW * math.cos(math.pi * k / N), 3.1 + RH * math.sin(math.pi * k / N)) for k in range(N + 1)] + \
          [(HW * 0.943 * math.cos(math.pi * k / N), 3.1 + (RH - 0.04) * math.sin(math.pi * k / N)) for k in range(N, -1, -1)]
    loft(g, "roof", [[(xa, y, z) for y, z in pts], [(xb, y, z) for y, z in pts]], close=True, caps=True)
    # ----- piso
    box(g, "floor", ((xa + xb) / 2, 0, FLOOR - 0.025), (xb - xa, 2.9, 0.05), 0.005, 1)
    for k in range(24):
        box(g, "groove", ((xa + xb) / 2, -1.3 + k * 0.113, FLOOR + 0.002), (xb - xa - 0.2, 0.01, 0.005))
    # ----- interior
    for a_, b_ in spans:
        for sgn in (-1, 1):
            seat_bank(g, sgn, a_ + 0.12, b_ - 0.12)
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
        box(g, "liner", (px, 0.9, 2.07), (0.08, 1.2, 2.05), 0.01, 2)
        box(g, "liner", (px, -1.05, 2.07), (0.08, 0.7, 2.05), 0.01, 2)
        box(g, "liner", (px, -0.15, 2.65), (0.08, 0.9, 0.9), 0.01, 2)
        box(g, "glass", (px, -0.15, 2.0), (0.01, 0.62, 0.85))
        box(g, "ceiling", ((px + 7.4) / 2, 0, 3.03), (7.4 - px, 2.8, 0.04), 0.01, 2)
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
        build_nose(g, xb, texts)
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
        g, (xa, xb, cab), texts = build_car(k)
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
