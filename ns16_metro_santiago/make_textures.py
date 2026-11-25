"""Genera texturas de senaletica interior del NS-16 (mapa L5, panel de emergencia, afiches genericos)."""
import os
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "textures")
os.makedirs(OUT, exist_ok=True)
FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"; FR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
f = lambda p, s: ImageFont.truetype(p, s)
L5 = ["Plaza de Maipú", "Santiago Bueras", "Del Sol", "Monte Tabor", "Las Parcelas", "Laguna Sur", "Barrancas",
      "Pudahuel", "San Pablo", "Lo Prado", "Blanqueado", "Gruta de Lourdes", "Quinta Normal", "Cumming", "Santa Ana",
      "Plaza de Armas", "Bellas Artes", "Baquedano", "Parque Bustamante", "Santa Isabel", "Irarrázaval", "Ñuble",
      "Rodrigo de Araya", "Carlos Valdovinos", "Camino Agrícola", "San Joaquín", "Pedrero", "Mirador",
      "Bellavista de La Florida", "Vicente Valdés"]
GREEN = (0, 150, 70)

def mapa():
    W, H = 3200, 280
    im = Image.new("RGB", (W, H), (245, 245, 243)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 260, H], fill=GREEN)
    d.text((130, 95), "5", font=f(FB, 120), fill="white", anchor="mm")
    d.text((130, 200), "Línea 5", font=f(FB, 36), fill="white", anchor="mm")
    x0, x1, yl = 330, W - 300, 200
    d.rectangle([x0, yl - 9, x1, yl + 9], fill=GREEN)
    n = len(L5)
    for i, st in enumerate(L5):
        x = x0 + (x1 - x0) * i / (n - 1)
        big = i in (0, n - 1, 14, 15, 17)
        r = 17 if big else 12
        d.ellipse([x - r, yl - r, x + r, yl + r], fill="white", outline=(30, 30, 30), width=4)
        d.ellipse([x - 6, yl - 6, x + 6, yl + 6], fill=(255, 160, 20))          # LED
        txt = Image.new("RGBA", (330, 40), (0, 0, 0, 0)); td = ImageDraw.Draw(txt)
        td.text((0, 20), st, font=f(FB if big else FR, 24), fill=(25, 25, 25), anchor="lm")
        txt = txt.rotate(38, expand=True, resample=Image.BICUBIC)
        im.paste(txt, (int(x - 8), int(yl - 30 - txt.size[1])), txt)
    for x, lbl, col in ((x0 + (x1 - x0) * 14 / 29, "L3", (110, 60, 20)), (x0 + (x1 - x0) * 15 / 29, "L3", (110, 60, 20)),
                        (x0 + (x1 - x0) * 17 / 29, "L1", (220, 20, 20)), (x0 + (x1 - x0) * 12 / 29, "", None)):
        if col:
            d.rounded_rectangle([x - 26, yl + 30, x + 26, yl + 66], 8, fill=col); d.text((x, yl + 48), lbl, font=f(FB, 22), fill="white", anchor="mm")
    im.save(os.path.join(OUT, "mapa_L5.png"))

def emergencia():
    W, H = 2400, 280
    im = Image.new("RGB", (W, H), (240, 240, 238)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 345, H], fill=(25, 25, 25)); d.text((24, 110), "Emergencia", font=f(FB, 42), fill="white"); d.text((30, 170), "Emergency", font=f(FR, 28), fill="white")
    cols = [("Importante", "Important", (70, 90, 200)), ("Seguridad", "Safety and Security", (25, 25, 25)),
            ("Evacuación", "Evacuation", (20, 150, 90)), ("Humo o Fuego", "Smoke or Fire", (220, 30, 50))]
    x = 370
    for t, e, c in cols:
        d.text((x, 30), t, font=f(FB, 34), fill=c); d.text((x, 72), e, font=f(FR, 20), fill=c)
        for k in range(2):
            bx = x + k * 120
            d.rectangle([bx, 115, bx + 100, 215], outline=(25, 25, 25), width=5)
            d.ellipse([bx + 35, 130, bx + 65, 160], fill=(25, 25, 25)); d.rectangle([bx + 30, 165, bx + 70, 205], fill=(25, 25, 25))
            d.text((bx, 228), "· · · · · ·", font=f(FR, 16), fill=(90, 90, 90))
        x += 300
    d.rectangle([x, 0, x + 250, H], fill=(25, 25, 25)); d.text((x + 30, 110), "Contacto", font=f(FB, 40), fill="white"); d.text((x + 30, 160), "Contact", font=f(FR, 24), fill="white")
    x += 290
    d.text((x, 40), "Información", font=f(FB, 34), fill=(25, 25, 25)); d.text((x, 80), "Information", font=f(FR, 20), fill=(25, 25, 25))
    d.rectangle([x, 115, x + 100, 215], outline=(25, 25, 25), width=5); d.ellipse([x + 30, 130, x + 70, 170], fill=(25, 25, 25))
    d.text((x + 115, 150), "600 600", font=f(FB, 24), fill=(25, 25, 25)); d.text((x + 115, 182), "9292", font=f(FB, 24), fill=(25, 25, 25))
    x = W - 300
    d.rectangle([x, 0, W, H], fill=(25, 25, 25)); d.text((x + 30, 70), "Nº Carro", font=f(FB, 44), fill="white"); d.text((x + 30, 125), "Car Nº", font=f(FR, 26), fill="white"); d.text((x + 30, 165), "1631", font=f(FB, 44), fill="white")
    im.save(os.path.join(OUT, "info_emergencia.png"))

def afiche(name, bg, fg, title, sub):
    W, H = 1800, 280
    im = Image.new("RGB", (W, H), bg); d = ImageDraw.Draw(im)
    for k in range(6):
        d.ellipse([W - 520 + k * 60, -120 + k * 40, W - 120 + k * 60, 280 + k * 40], outline=fg, width=6)
    d.text((60, 70), title, font=f(FB, 62), fill=fg); d.text((64, 170), sub, font=f(FR, 34), fill=fg)
    im.save(os.path.join(OUT, name))

mapa(); emergencia()
afiche("afiche_1.png", (230, 40, 40), (255, 255, 255), "Respeta los asientos preferentes", "Personas mayores, embarazadas y con movilidad reducida")
afiche("afiche_2.png", (20, 60, 120), (255, 255, 255), "Deja salir antes de entrar", "Así viajamos todos mejor")
afiche("afiche_3.png", (250, 200, 40), (30, 30, 30), "Cuida tu tren", "Hecho en Chile · Talleres Neptuno")
print(sorted(os.listdir(OUT)))
