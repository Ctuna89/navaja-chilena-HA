"""Renderiza vistas del .blend. Uso: python3 render_ns16.py [res_pct] [muestras] [vista ...]"""
import bpy, math, sys, os
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
BLEND = os.path.join(HERE, "ns16_metro_santiago.blend")
args = sys.argv[1:]
pct = int(args[0]) if args else 100
samples = int(args[1]) if len(args) > 1 else 48
only = args[2:]

bpy.ops.wm.open_mainfile(filepath=BLEND)
sc = bpy.context.scene
sc.cycles.samples = samples
sc.render.resolution_percentage = pct
sc.cycles.device = 'CPU'
sc.cycles.use_denoising = True

def X0(i): return bpy.data.objects[f"C{i}_body"].matrix_world.translation.x
NC = len([o for o in bpy.data.objects if o.name.startswith("C") and o.name.endswith("_body")])
xs = [X0(i) for i in range(1, NC + 1)]
cx = (xs[0] + xs[-1]) / 2

# luces interiores suaves
def alight(name, loc, size, energy):
    d = bpy.data.lights.new(name, 'AREA'); d.energy = energy; d.size = size; d.shape = 'RECTANGLE'; d.size_y = 0.4
    d.color = (1.0, 0.96, 0.88)
    o = bpy.data.objects.new(name, d); o.location = loc; o.rotation_euler = (0, 0, 0)
    sc.collection.objects.link(o)
for i in range(1, NC + 1):
    for dx in (-5, 0, 5) if i not in (1, NC) else (-5, -1):
        sign = -1 if i == 1 else 1
        alight(f"int{i}_{dx}", (xs[i - 1] + sign * dx, 0, 2.93), 2.5, 60)
alight("cabina", (xs[-1] + 5.0, 0, 2.93), 1.5, 50)

def make_cam(name, loc, target, lens=35, ortho=None, rot=None):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.clip_start = 0.05; cd.clip_end = 600
    if ortho: cd.type = 'ORTHO'; cd.ortho_scale = ortho
    ob = bpy.data.objects.new(name, cd); sc.collection.objects.link(ob)
    ob.location = loc
    if rot is not None: ob.rotation_euler = rot
    else:
        d = Vector(target) - Vector(loc)
        ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return ob

xf = xs[-1]          # centro del coche cabecero
xn = xf + 7.8       # punta de la nariz
sc.view_settings.look = 'None'
sc.view_settings.exposure = -0.8
bpy.data.worlds['Studio'].node_tree.nodes['Background'].inputs[1].default_value = 0.45
for l in bpy.data.lights:
    if l.name in ('Key','Fill','Top'): l.energy *= 0.5
views = {
    "01_exterior_cabina_3cuartos": make_cam("v1", (xn + 7.0, 6.0, 1.7), (xn - 1.0, 0.0, 1.9), 40),
    "02_lateral_tren_completo": make_cam("v2", (cx, 80, 2.2), None, 35, ortho=135, rot=(math.radians(90), 0, math.radians(180))),
    "03_cabina_conductor": make_cam("v3", (xf + 3.9, -0.45, 2.15), (xf + 7.4, 0.0, 1.9), 22),
    "04_interior_pasajeros": make_cam("v4", (xs[2] - 7.4, 0.15, 1.95), (xs[2] + 2.0, 0.0, 1.9), 18),
    "05_bogie": make_cam("v5", (xs[2] + 8.6, 3.6, 0.55), (xs[2] + 5.9, 0.6, 0.55), 35),
    "07_frontal": make_cam("v7", (xn + 8.0, 0.0, 1.9), (xn, 0.0, 2.0), 40),
    "08_frontal_bajo": make_cam("v8", (xn + 5.5, 4.2, 0.9), (xn - 2.5, 0.0, 1.55), 28),
    "06_aerea_frontal": make_cam("v6", (xn + 18, -13, 9), (xn - 8, 0.0, 1.8), 40),
}
os.makedirs(os.path.join(HERE, "renders"), exist_ok=True)
for name, cam in views.items():
    if only and not any(o in name for o in only): continue
    sc.camera = cam
    sc.render.filepath = os.path.join(HERE, "renders", name + ".png")
    print("render", name, flush=True)
    bpy.ops.render.render(write_still=True)
# guarda el .blend con camaras y luces finales
bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=True)
