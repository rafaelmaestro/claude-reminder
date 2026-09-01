#!/usr/bin/env python3
"""Camada de janelas: tudo que depende de X11 ou de Wayland mora aqui.

O resto do plugin so fala com estas funcoes. Um compositor novo vira um ramo
neste arquivo, nao um `if` espalhado entre o hook e o overlay.

Tres backends:

    x11       xdotool faz tudo (posicao, monitor em foco, ativar janela)
    hyprland  hyprctl responde quem esta em foco; a posicao vem do layer-shell
    wayland   generico: layer-shell posiciona, o resto degrada em silencio

Tambem roda como CLI, para o hook em bash nao depender de jq:

    python3 wm.py record <arquivo>   # grava a janela em foco agora
"""
import json
import os
import subprocess
import sys

HYPR_ENV = "HYPRLAND_INSTANCE_SIGNATURE"


def backend():
    """Qual backend usar — a mesma escolha que o GTK vai fazer ao abrir a janela.

    Num compositor Wayland o DISPLAY continua definido (Xwayland), entao a
    presenca de DISPLAY nao prova X11: quem decide e o WAYLAND_DISPLAY, com o
    GDK_BACKEND por cima quando o usuario forcou um dos dois.
    """
    forced = os.environ.get("GDK_BACKEND", "").split(",")[0].strip()
    if forced == "x11":
        return "x11" if os.environ.get("DISPLAY") else ""
    if os.environ.get("WAYLAND_DISPLAY") and forced in ("", "wayland"):
        return "hyprland" if os.environ.get(HYPR_ENV) else "wayland"
    if forced == "wayland":
        return ""
    return "x11" if os.environ.get("DISPLAY") else ""


def _out(cmd, timeout=1):
    """stdout do comando, ou None se ele falhou, sumiu ou travou."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None
    return proc.stdout if proc.returncode == 0 else None


def _hypr(*args):
    raw = _out(["hyprctl", "-j"] + list(args))
    try:
        return json.loads(raw)
    except Exception:
        return None


# --- janela do terminal ------------------------------------------------------
# O token guardado no SessionStart carrega o backend junto ("hypr:0x55f...",
# "x11:69206019"). Sem isso, trocar de sessao X11 para Wayland faria o clique
# ativar um id de outro mundo.


def active_window():
    kind = backend()
    if kind == "hyprland":
        addr = (_hypr("activewindow") or {}).get("address") or ""
        return "hypr:" + addr if addr.startswith("0x") else ""
    if kind == "x11":
        wid = (_out(["xdotool", "getactivewindow"]) or "").strip()
        return "x11:" + wid if wid.isdigit() else ""
    return ""


def focus_window(token):
    """Ativa a janela do token. Se ela nao existe mais, nao ativa nada.

    Fallback obrigatorio (design D8): um clique que joga o usuario na janela
    errada e pior que um clique inerte.
    """
    token = (token or "").strip()
    if not token:
        return False
    kind, _, ident = token.partition(":")
    if not ident:  # arquivo de sessao antigo: id nu do X11
        kind, ident = "x11", token

    if kind == "hypr" and backend() == "hyprland":
        clients = _hypr("clients") or []
        if not any(c.get("address") == ident for c in clients):
            return False
        return _out(["hyprctl", "dispatch", "focuswindow", "address:" + ident]) is not None
    if kind == "x11" and backend() == "x11":
        if _out(["xdotool", "getwindowname", ident]) is None:
            return False
        return _out(["xdotool", "windowactivate", ident]) is not None
    return False


# --- monitor em foco ---------------------------------------------------------


def _monitor_at(display, x, y):
    """Gdk.Monitor pelo canto superior esquerdo do layout.

    Comparar coordenada e o unico criterio que serve nos dois backends: no
    Wayland o `model` do GDK e o modelo do painel ("F24G3xTF"), nao o conector
    que o compositor usa ("DP-1").
    """
    for i in range(display.get_n_monitors()):
        monitor = display.get_monitor(i)
        geo = monitor.get_geometry()
        if geo.x == x and geo.y == y:
            return monitor
    return display.get_monitor_at_point(x, y)


def active_monitor(display):
    """Monitor onde o usuario esta olhando AGORA, ou None se nao der para saber.

    Num desktop de 5360px, o canto inferior direito do desktop virtual pode
    estar a tres mil pixels de onde o usuario esta olhando (design D6).
    """
    kind = backend()
    if kind == "hyprland":
        for mon in _hypr("monitors") or []:
            if mon.get("focused"):
                try:
                    return _monitor_at(display, int(mon["x"]), int(mon["y"]))
                except Exception:
                    return None
        return None
    if kind == "x11":
        out = _out(["xdotool", "getactivewindow", "getwindowgeometry", "--shell"])
        try:
            vals = dict(l.split("=", 1) for l in out.strip().splitlines() if "=" in l)
            cx = int(vals["X"]) + int(vals["WIDTH"]) // 2
            cy = int(vals["Y"]) + int(vals["HEIGHT"]) // 2
            return display.get_monitor_at_point(cx, cy)
        except Exception:
            return None
    return None  # wayland generico: sem protocolo padrao para "quem esta em foco"


def fallback_monitor(display):
    return display.get_primary_monitor() or display.get_monitor(0)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "record":
        token = active_window()
        if token:
            with open(sys.argv[2], "w") as fh:
                fh.write(token)
        return 0
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
