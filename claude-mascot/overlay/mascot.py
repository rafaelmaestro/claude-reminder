#!/usr/bin/env python3
"""Overlay do mascote do Claude.

Um processo por evento (design D3): abre a janela, anima, morre. Sem daemon,
sem IPC, sem orfao. A animacao em si mora em mascot.html; aqui fica so o que
precisa falar com o X11.
"""
import argparse
import json
import os
import signal
import subprocess
import sys
from urllib.parse import urlencode

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, GLib, Gtk, WebKit2  # noqa: E402
import cairo  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(
    os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "claude-mascot"
)
CONFIG = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
    "claude-mascot",
    "config.json",
)

# Tamanho da faixa em celulas. A faixa e maior que o mascote porque ele entra e
# sai andando dentro dela — mover a janela GTK a cada frame engasga no X11.
COLS, ROWS = 43, 24
MARGIN = 24  # folga ate a borda do monitor
HIT_PAD = 8  # alvo pequeno em movimento precisa de folga de clique

DEFAULTS = {
    "enabled": True,
    "states": {"ask": True, "done": True},
    "mute": False,
    "volume": 1.0,
    "ask_timeout": 60,
    "cell": 7,
    "sounds": {},
}

# window-question.oga e symlink de dialog-warning.oga: um blip surdo que passa
# despercebido. message-new-instant tem ataque e brilho — e o que faz virar a
# cabeca. Trocavel pelo config.
SOUNDS = {
    "ask": "/usr/share/sounds/freedesktop/stereo/message-new-instant.oga",
    "done": "/usr/share/sounds/freedesktop/stereo/complete.oga",
}


def load_config():
    cfg = json.loads(json.dumps(DEFAULTS))
    try:
        with open(CONFIG) as fh:
            user = json.load(fh)
        if isinstance(user, dict):
            states = user.pop("states", None)
            sounds = user.pop("sounds", None)
            cfg.update({k: v for k, v in user.items() if k in cfg})
            if isinstance(states, dict):
                cfg["states"].update(states)
            if isinstance(sounds, dict):
                cfg["sounds"].update(sounds)
    except Exception:
        pass  # ausente, ilegivel ou invalido: valores padrao (spec)
    return cfg


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


def active_monitor_geometry(display):
    """Monitor que contem a janela ativa AGORA — nao o canto do desktop virtual.

    Num desktop de 5360px, o canto inferior direito do desktop pode estar a tres
    mil pixels de onde o usuario esta olhando (design D6).
    """
    try:
        out = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowgeometry", "--shell"],
            capture_output=True,
            text=True,
            timeout=1,
        ).stdout
        vals = dict(
            line.split("=", 1) for line in out.strip().splitlines() if "=" in line
        )
        cx = int(vals["X"]) + int(vals["WIDTH"]) // 2
        cy = int(vals["Y"]) + int(vals["HEIGHT"]) // 2
        monitor = display.get_monitor_at_point(cx, cy)
        if monitor is not None:
            return monitor.get_geometry()
    except Exception:
        pass
    monitor = display.get_primary_monitor() or display.get_monitor(0)
    return monitor.get_geometry()


def focus_terminal(session):
    """Ativa a janela do terminal registrada no SessionStart.

    Fallback obrigatorio (design D8): se o ID nao vale mais, nao ativa nada. Um
    clique que joga o usuario na janela errada e pior que um clique inerte.
    """
    path = os.path.join(CACHE, "session-%s.win" % session)
    try:
        with open(path) as fh:
            wid = fh.read().strip()
    except OSError:
        return
    if not wid:
        return
    try:
        probe = subprocess.run(
            ["xdotool", "getwindowname", wid], capture_output=True, timeout=1
        )
        if probe.returncode != 0:
            return
        subprocess.run(
            ["xdotool", "windowactivate", wid], capture_output=True, timeout=1
        )
    except Exception:
        pass


class Overlay:
    def __init__(self, state, session, cfg, variant=None, bg=None):
        self.state = state
        self.session = session
        self.cfg = cfg
        self.cell = max(3, int(cfg["cell"]))
        self.w = COLS * self.cell
        self.h = ROWS * self.cell
        self.hit = None
        self.exiting = False

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
        # A WebView tem tamanho minimo proprio; sem isto a janela nasce mais
        # alta que a faixa e o mascote fica deslocado da borda do monitor.
        self.win.set_size_request(self.w, self.h)
        self.win.connect("destroy", Gtk.main_quit)

        screen = self.win.get_screen()
        visual = screen.get_rgba_visual()
        if visual is None:
            sys.exit(0)  # sem compositor nao ha transparencia: sai calado
        self.win.set_visual(visual)

        ucm = WebKit2.UserContentManager()
        ucm.register_script_message_handler("mascot")
        ucm.connect("script-message-received::mascot", self.on_message)
        self.view = WebKit2.WebView.new_with_user_content_manager(ucm)
        self.view.set_background_color(Gdk.RGBA(0, 0, 0, 0))
        self.view.set_size_request(self.w, self.h)
        self.win.add(self.view)

        params = {"cell": self.cell, "cols": COLS, "rows": ROWS, "state": state}
        if bg:
            params["bg"] = bg             # fundo opaco: so para gravar o GIF
        if variant is not None:
            params["variant"] = variant   # so para iterar a arte; o uso normal sorteia
        params = urlencode(params)
        self.view.load_uri("file://%s/mascot.html?%s" % (HERE, params))

        geo = active_monitor_geometry(screen.get_display())
        self.win.move(
            geo.x + geo.width - self.w - MARGIN,
            geo.y + geo.height - self.h - MARGIN,
        )

        self.win.realize()
        self.set_hitbox(None)  # nasce inteira click-through
        self.win.show_all()

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

    def on_message(self, _ucm, result):
        try:
            try:
                raw = result.get_js_value().to_string()
            except AttributeError:  # WebKit2 mais antigo
                raw = result.get_value().to_string()
            msg = json.loads(raw)
        except Exception:
            return

        kind = msg.get("t")
        if kind == "hit":
            rect = (msg["x"] - HIT_PAD, msg["y"] - HIT_PAD,
                    msg["w"] + 2 * HIT_PAD, msg["h"] + 2 * HIT_PAD)
            if rect != self.hit:
                self.set_hitbox(rect)
        elif kind == "click":
            self.exiting = True
            focus_terminal(self.session)
        elif kind == "done":
            Gtk.main_quit()

    def js(self, code):
        try:
            self.view.run_javascript(code, None, None, None)
        except Exception:
            try:
                self.view.evaluate_javascript(code, -1, None, None, None, None, None)
            except Exception:
                pass

    def begin_exit(self):
        if self.exiting:
            return False
        self.exiting = True
        self.js("window.mascotExit && window.mascotExit()")
        GLib.timeout_add(3000, Gtk.main_quit)  # rede de seguranca
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

    os.makedirs(CACHE, exist_ok=True)
    with open(os.path.join(CACHE, "overlay.pid"), "w") as fh:
        fh.write(str(os.getpid()))

    overlay = Overlay(args.state, args.session, cfg, args.variant, args.bg)
    play_sound(args.state, cfg)

    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, overlay.begin_exit)
    if args.state == "ask" and cfg["ask_timeout"] > 0:
        GLib.timeout_add_seconds(int(cfg["ask_timeout"]), overlay.begin_exit)

    Gtk.main()


if __name__ == "__main__":
    main()
