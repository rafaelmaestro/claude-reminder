#!/usr/bin/env python3
"""Desenho do mascote em cairo, sem nada de janela.

Estava dentro do mascot.py, acoplado ao Overlay do GTK. Saiu daqui porque o
backend de janela do Windows precisa exatamente do mesmo desenho: duplicar
seria garantir que os dois divergissem na primeira mudanca de arte.

Nao importa gi, nao importa wm: so cairo e a arte. Recebe um contexto cairo
pronto — de um Gtk.DrawingArea no Linux, de uma ImageSurface no Windows.
"""
import cairo

import frames
from poses import GRID, POSES, PROPS, SYMBOLS

W, H = GRID["w"], GRID["h"]
SW, SH = GRID["sw"], GRID["sh"]
PW, PH, POFF = GRID["pw"], GRID["ph"], GRID["poff"]

# Um caractere por celula (design D5). None e vazio.
PAL = {
    ".": None,
    "O": (0xD9, 0x77, 0x57),  # corpo
    "K": (0x19, 0x19, 0x19),  # olhos
    "W": (0xFF, 0xFF, 0xFF),
    "G": (0x2B, 0xA8, 0x4A),  # check
    "P": (0x6B, 0x4F, 0xD8),  # interrogacao
    "B": (0x1F, 0x4E, 0x8C),  # fone
    "Y": (0xF0, 0xB2, 0x3C),  # capacete, lampada
    "A": (0x9A, 0x9A, 0x9A),  # metal
    "R": (0xE0, 0x31, 0x31),  # coracao
    "N": (0x8A, 0x5A, 0x3B),  # madeira do bau
}

SHADOW = (0, 0, 0, 0.35)   # sombra dura, sem desfoque: idioma pixel art
GROUND = (0, 0, 0, 0.22)   # a marca no chao, que nao sobe junto no pulo


def rows(block):
    return block.strip("\n").split("\n")


class Painter:
    """Pinta um quadro da coreografia num contexto cairo qualquer."""

    def __init__(self, cell, bg=None):
        self.cell = cell
        self.shadow = max(2, round(cell * 0.45))
        self.bg = bg  # fundo opaco: so para gravar o GIF

    def draw(self, cr, frame):
        # Uma faixa limpa por quadro. Este zero e o conserto do rastro: com
        # OPERATOR_SOURCE o alfa e escrito, nao misturado — pintar transparente
        # por cima com o operador padrao nao apagaria nada.
        cr.set_operator(cairo.OPERATOR_SOURCE)
        if self.bg:
            cr.set_source_rgb(*self.bg)
        else:
            cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        f = frame
        if f is None:
            return

        if f.get("ground"):
            wide = f["ground"] == "wide"
            cr.set_source_rgba(*GROUND)
            cr.rectangle((f["x"] + (2 if wide else 4)) * self.cell,
                         frames.GROUND_Y * self.cell,
                         (11 if wide else 7) * self.cell, self.cell)
            cr.fill()

        # Ordem de empilhamento: simbolo atras do corpo, adereco na frente dele.
        if f.get("sym"):
            self.blit(cr, SYMBOLS[f["sym"]], SW, SH,
                      f["x"] + 4 + f.get("symDx", 0),
                      f["y"] - 5 + f.get("symDy", 0))
        self.blit(cr, POSES[f["p"]], W, H, f["x"], f["y"], f.get("flip"))
        # Adereco anda colado no corpo: mesma coluna, POFF linhas acima. Nunca
        # espelha — inverter jogaria a varinha dentro do corpo.
        if f.get("prop"):
            self.blit(cr, PROPS[f["prop"]], PW, PH, f["x"], f["y"] - POFF)

    def blit(self, cr, block, w, h, ox, oy, flip=False):
        """Desenha um bloco de arte: a silhueta deslocada e, por cima, as cores.

        Duas passadas porque a sombra e da silhueta inteira — desenhar sombra e
        cor celula a celula deixaria a sombra de uma celula por cima da cor da
        vizinha.
        """
        art = rows(block)
        cell = self.cell
        shade = self.shadow

        cr.set_source_rgba(*SHADOW)
        for y in range(h):
            row = art[y] if y < len(art) else ""
            for x in range(w):
                sx = w - 1 - x if flip else x
                if sx < len(row) and PAL.get(row[sx]):
                    cr.rectangle((ox + x) * cell + shade,
                                 (oy + y) * cell + shade, cell, cell)
        cr.fill()

        for y in range(h):
            row = art[y] if y < len(art) else ""
            for x in range(w):
                sx = w - 1 - x if flip else x
                ink = PAL.get(row[sx]) if sx < len(row) else None
                if not ink:
                    continue
                cr.set_source_rgb(ink[0] / 255, ink[1] / 255, ink[2] / 255)
                cr.rectangle((ox + x) * cell, (oy + y) * cell, cell, cell)
                cr.fill()
