#!/usr/bin/env python3
"""Overlay do mascote do Claude.

Um processo por evento (design D3): abre a janela, anima, morre. Sem daemon,
sem IPC, sem orfao. A arte mora em poses.py, a coreografia em frames.py, e a
conversa com o X11 ou com o compositor Wayland mora em wm.py; aqui fica o meio
de campo: a janela, o desenho e o clique.

O desenho e cairo puro. Ja foi uma WebView, e ela deixava rastro: a WebKitGTK
2.52 nao limpa a superficie quando o fundo da pagina e transparente — ela
compoe cada quadro por cima do anterior, entao todo pixel por onde o mascote
passou ficava na tela. Nao ha ajuste de pagina, de GTK nem de compositor que
resolva; desenhar direto resolve, e ainda tira uma dependencia.
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402
import cairo  # noqa: E402

import frames  # noqa: E402
import wm  # noqa: E402
from poses import GRID, POSES, PROPS, SYMBOLS  # noqa: E402
from painter import PAL, GROUND, SHADOW, Painter, rows  # noqa: E402,F401
from config import CACHE, CONFIG, DEFAULTS, SOUNDS, load_config  # noqa: E402,F401

# No Wayland a janela nao escolhe onde nasce — o compositor escolhe. O
# wlr-layer-shell devolve essa escolha para o cliente, e o gtk-layer-shell e o
# binding dele. Sem a typelib, o backend Wayland simplesmente nao existe.
try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell  # noqa: E402
except (ValueError, ImportError):
    GtkLayerShell = None

HERE = os.path.dirname(os.path.abspath(__file__))

# Tamanho da faixa em celulas. A faixa e maior que o mascote porque ele entra e
# sai andando dentro dela — mover a janela GTK a cada frame engasga no X11.
COLS, ROWS = frames.COLS, frames.ROWS
MARGIN = 24  # folga ate a borda do monitor
HIT_PAD = 8  # alvo pequeno em movimento precisa de folga de clique

W, H = GRID["w"], GRID["h"]
SW, SH = GRID["sw"], GRID["sh"]
PW, PH, POFF = GRID["pw"], GRID["ph"], GRID["poff"]

def play_sound(state, cfg):
    if cfg["mute"]:
        return
    path = cfg["sounds"].get(state) or SOUNDS.get(state)
    if not path or not os.path.exists(path):
        return
    try:
        subprocess.Popen(
            ["pw-play", "--volume", str(cfg["volume"]), path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass  # sem audio a animacao continua (spec)


def focus_terminal(session):
    """Ativa a janela do terminal registrada no SessionStart."""
    # o id vira nome de arquivo: so caracteres de id, nunca separador de caminho
    safe = re.sub(r"[^A-Za-z0-9_-]", "", session) or "default"
    try:
        with open(os.path.join(CACHE, "session-%s.win" % safe)) as fh:
            wm.focus_window(fh.read())
    except OSError:
        pass  # sessao sem janela registrada: o clique so dispensa o mascote


class Overlay:
    def __init__(self, state, session, cfg, variant=None, bg=None):
        self.state = state
        self.session = session
        self.cfg = cfg
        self.cell = max(3, int(cfg["cell"]))
        self.w = COLS * self.cell
        self.h = ROWS * self.cell
        self.bg = parse_color(bg)  # fundo opaco: so para gravar o GIF
        self.painter = Painter(self.cell, self.bg)
        self.hit = None
        self.exiting = False
        self.frame = None

        self.intro, self.loop, self.out = frames.sequence(state, variant)
        self.phase, self.index, self.timer = "intro", 0, None

        self.win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.win.set_decorated(False)
        self.win.set_resizable(False)
        self.win.set_skip_taskbar_hint(True)
        self.win.set_skip_pager_hint(True)
        self.win.set_keep_above(True)
        # Nao negociavel: se a janela pegar foco, ela come as teclas que o
        # usuario esta digitando como resposta ao Claude.
        self.win.set_accept_focus(False)
        self.win.set_focus_on_map(False)
        self.win.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
        self.win.set_app_paintable(True)
        self.win.set_title("claude-mascot")
        self.win.set_default_size(self.w, self.h)
        self.win.set_size_request(self.w, self.h)
        self.win.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.win.connect("button-press-event", self.on_click)
        self.win.connect("draw", self.on_draw)
        self.win.connect("destroy", Gtk.main_quit)

        screen = self.win.get_screen()
        visual = screen.get_rgba_visual()
        if visual is None:
            sys.exit(0)  # sem compositor nao ha transparencia: sai calado
        self.win.set_visual(visual)

        display = screen.get_display()
        if wm.backend() == "x11":
            monitor = wm.active_monitor(display) or wm.fallback_monitor(display)
            geo = monitor.get_geometry()
            self.win.move(
                geo.x + geo.width - self.w - MARGIN,
                geo.y + geo.height - self.h - MARGIN,
            )
        else:
            self.anchor_wayland(display)

        self.win.realize()
        self.set_hitbox(None)  # nasce inteira click-through
        self.win.show_all()

    def anchor_wayland(self, display):
        """Ancora a faixa no canto inferior direito do monitor em foco.

        No Wayland `win.move()` nao faz nada: a janela pede a posicao ao
        compositor via wlr-layer-shell. As garantias do X11 viram propriedades
        da camada — OVERLAY substitui o keep-above, KeyboardMode.NONE substitui
        o accept-focus, e zona exclusiva 0 impede que a faixa empurre as outras
        janelas para o lado como uma barra faria.
        """
        GtkLayerShell.init_for_window(self.win)
        GtkLayerShell.set_namespace(self.win, "claude-mascot")
        GtkLayerShell.set_layer(self.win, GtkLayerShell.Layer.OVERLAY)
        for edge in (GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.RIGHT):
            GtkLayerShell.set_anchor(self.win, edge, True)
            GtkLayerShell.set_margin(self.win, edge, MARGIN)
        GtkLayerShell.set_keyboard_mode(self.win, GtkLayerShell.KeyboardMode.NONE)
        GtkLayerShell.set_exclusive_zone(self.win, 0)
        monitor = wm.active_monitor(display)
        if monitor is not None:
            # Sem isto quem escolhe o monitor e o compositor, e ele nao tem como
            # saber qual janela pediu atencao: o palpite dele e o output em foco,
            # que nem sempre e o do terminal do Claude Code (design D6).
            GtkLayerShell.set_monitor(self.win, monitor)

    # --- desenho -------------------------------------------------------------

    def on_draw(self, _widget, cr):
        self.painter.draw(cr, self.frame)
        return False

    def set_hitbox(self, rect):
        """Recorta a area clicavel. Falhou? Fecha — melhor sumir do que virar um
        retangulo invisivel que engole cliques no canto da tela (spec)."""
        try:
            if rect is None:
                region = cairo.Region()
            else:
                x, y, w, h = rect
                x = max(0, min(self.w, x))
                y = max(0, min(self.h, y))
                w = max(0, min(self.w - x, w))
                h = max(0, min(self.h - y, h))
                region = cairo.Region(cairo.RectangleInt(int(x), int(y), int(w), int(h)))
            self.win.input_shape_combine_region(region)
            self.hit = rect
        except Exception:
            Gtk.main_quit()

    # --- motor ---------------------------------------------------------------

    def tick(self):
        self.timer = None
        if self.phase == "intro":
            if self.index < len(self.intro):
                f = self.intro[self.index]
                self.index += 1
            else:
                self.phase, self.index = "loop", 0
                return self.tick()
        elif self.phase == "loop":
            if not self.loop:
                self.phase, self.index = "exit", 0
                return self.tick()
            f = self.loop[self.index % len(self.loop)]
            self.index += 1
        else:
            if self.index < len(self.out):
                f = self.out[self.index]
                self.index += 1
            else:
                Gtk.main_quit()
                return False

        self.frame = f
        self.win.queue_draw()

        # O recorte de clique acompanha o sprite: alvo pequeno que anda e
        # dificil de acertar, e um recorte parado deixa o clique caindo no vazio.
        rect = (f["x"] * self.cell - HIT_PAD, f["y"] * self.cell - HIT_PAD,
                W * self.cell + 2 * HIT_PAD, H * self.cell + 2 * HIT_PAD)
        if rect != self.hit:
            self.set_hitbox(rect)

        self.timer = GLib.timeout_add(f.get("ms", 100), self.tick)
        return False

    def on_click(self, _widget, _event):
        # O recorte de entrada ja garante que so chega clique em cima do sprite.
        if self.exiting:
            return True
        focus_terminal(self.session)
        self.begin_exit()
        return True

    def begin_exit(self):
        if self.exiting:
            return False
        self.exiting = True
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = None
        self.phase, self.index = "exit", 0
        self.tick()
        return False


def parse_color(value):
    """#rrggbb -> (r, g, b) em 0..1, ou None."""
    if not value:
        return None
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", value.strip())
    if not m:
        return None
    raw = m.group(1)
    return tuple(int(raw[i:i + 2], 16) / 255 for i in (0, 2, 4))


def supported():
    """Da para posicionar a janela aqui?

    No Wayland, nao basta o compositor existir: ele precisa implementar o
    wlr-layer-shell. O Mutter (GNOME) nao implementa, e sem ele a janela
    nasceria no meio da tela roubando o foco — pior que nao aparecer.
    """
    kind = wm.backend()
    if kind == "x11":
        return True
    if kind in ("hyprland", "wayland"):
        try:
            return GtkLayerShell is not None and GtkLayerShell.is_supported()
        except Exception:
            return False
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="ask", choices=["ask", "done"])
    ap.add_argument("--session", default="default")
    ap.add_argument("--variant", type=int, default=None,
                    help="forca uma variacao do pedido de atencao (padrao: sorteia)")
    ap.add_argument("--bg", default=None,
                    help="fundo opaco para gravacao (ex: #1b1b22); padrao: transparente")
    args = ap.parse_args()

    cfg = load_config()
    if not cfg["enabled"] or not cfg["states"].get(args.state, True):
        return
    if not supported():
        return  # ambiente sem onde desenhar: sai calado, como sem DISPLAY (spec)

    os.makedirs(CACHE, exist_ok=True)
    with open(os.path.join(CACHE, "overlay.pid"), "w") as fh:
        fh.write(str(os.getpid()))

    overlay = Overlay(args.state, args.session, cfg, args.variant, args.bg)
    play_sound(args.state, cfg)

    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, overlay.begin_exit)
    if args.state == "ask" and cfg["ask_timeout"] > 0:
        GLib.timeout_add_seconds(int(cfg["ask_timeout"]), overlay.begin_exit)

    overlay.tick()
    Gtk.main()


if __name__ == "__main__":
    main()
