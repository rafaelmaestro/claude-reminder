#!/usr/bin/env python3
"""Backend de janela do Windows: janela em camadas via user32, desenho em cairo.

O irmao deste arquivo e o mascot.py, que faz o mesmo com GTK no X11 e no
Wayland. Os dois compartilham painter.py (o desenho), frames.py (a coreografia)
e config.py — aqui so mora o que e Win32.

Por que nao GTK tambem no Windows: PyGObject no Windows exige MSYS2, uns 300MB
de dependencia para quem so quer um bonequinho. user32 via ctypes ja vem com o
Python, e cairo desenha igual nos dois lados.

Como a janela funciona:

    WS_EX_LAYERED     alfa por pixel, alimentado por UpdateLayeredWindow
    WS_EX_TOPMOST     fica por cima
    WS_EX_NOACTIVATE  nunca rouba o foco do teclado
    WS_EX_TOOLWINDOW  fora da barra de tarefas e do Alt+Tab
    WM_NCHITTEST      devolve HTTRANSPARENT fora do sprite: o clique atravessa

Esse WM_NCHITTEST e o equivalente exato do recorte de entrada do X11 — e por
isso que a janela inteira nao engole clique no canto da tela.
"""
import argparse
import ctypes
import os
import sys
from ctypes import wintypes

import cairo

import config
import frames
import painter
import wm

COLS, ROWS = frames.COLS, frames.ROWS
MARGIN = 24
HIT_PAD = 8

WS_EX_LAYERED, WS_EX_TOOLWINDOW = 0x00080000, 0x00000080
WS_EX_TOPMOST, WS_EX_NOACTIVATE = 0x00000008, 0x08000000
WS_POPUP = 0x80000000
ULW_ALPHA, AC_SRC_OVER, AC_SRC_ALPHA = 0x02, 0x00, 0x01
HTTRANSPARENT, HTCLIENT = -1, 1
WM_DESTROY, WM_CLOSE, WM_NCHITTEST = 0x0002, 0x0010, 0x0084
WM_LBUTTONDOWN, WM_TIMER = 0x0201, 0x0113
SWP_NOACTIVATE, SWP_NOSIZE, SWP_NOMOVE = 0x0010, 0x0001, 0x0002
HWND_TOPMOST = -1

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
user32.SetProcessDPIAware()


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_byte), ("BlendFlags", ctypes.c_byte),
                ("SourceConstantAlpha", ctypes.c_byte), ("AlphaFormat", ctypes.c_byte)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long, wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASS(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


def play_sound(state, cfg):
    """winsound so toca WAV, e os .oga do freedesktop nao existem aqui. Sem um
    caminho no config, usa o som de sistema — melhor que silencio."""
    if cfg["mute"]:
        return
    try:
        import winsound
        path = cfg["sounds"].get(state)
        if path and os.path.exists(path):
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            winsound.MessageBeep(0x30 if state == "ask" else 0x40)
    except Exception:
        pass  # sem audio a animacao continua (spec)


class Overlay:
    def __init__(self, state, session, cfg, variant=None, bg=None):
        self.state, self.session, self.cfg = state, session, cfg
        self.cell = max(3, int(cfg["cell"]))
        self.w, self.h = COLS * self.cell, ROWS * self.cell
        self.painter = painter.Painter(self.cell, None)
        self.frame = None
        self.hit = None
        self.leaving = False

        self.seq = frames.sequence(state, variant)
        self.phase, self.i = "intro", 0

        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.w, self.h)
        self.cr = cairo.Context(self.surface)
        self._proc = WNDPROC(self.wndproc)   # a referencia precisa sobreviver
        self.hwnd = self._create_window()
        self._make_dib()

    def _create_window(self):
        cls = WNDCLASS()
        cls.lpfnWndProc = self._proc
        cls.hInstance = ctypes.windll.kernel32.GetModuleHandleW(None)
        cls.lpszClassName = "ClaudeMascotOverlay"
        user32.RegisterClassW(ctypes.byref(cls))

        mx, my, mw, mh = wm.win32_monitor_rect()
        x = mx + mw - self.w - MARGIN
        y = my + mh - self.h - MARGIN
        hwnd = user32.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_TOPMOST | WS_EX_NOACTIVATE,
            "ClaudeMascotOverlay", "claude-mascot", WS_POPUP,
            x, y, self.w, self.h, None, None, cls.hInstance, None)
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        user32.ShowWindow(hwnd, 8)   # SW_SHOWNA: mostra sem ativar
        return hwnd

    def _make_dib(self):
        hdr = BITMAPINFOHEADER()
        hdr.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        hdr.biWidth = self.w
        hdr.biHeight = -self.h        # negativo: origem no topo, como o cairo
        hdr.biPlanes = 1
        hdr.biBitCount = 32
        hdr.biCompression = 0
        self.screen_dc = user32.GetDC(None)
        self.mem_dc = gdi32.CreateCompatibleDC(self.screen_dc)
        self.bits = ctypes.c_void_p()
        self.bitmap = gdi32.CreateDIBSection(self.mem_dc, ctypes.byref(hdr), 0,
                                             ctypes.byref(self.bits), None, 0)
        gdi32.SelectObject(self.mem_dc, self.bitmap)

    def present(self):
        """cairo ARGB32 ja e BGRA pre-multiplicado em little-endian, que e
        exatamente o que UpdateLayeredWindow espera: da para copiar direto."""
        self.painter.draw(self.cr, self.frame)
        self.surface.flush()
        ctypes.memmove(self.bits, self.surface.get_data(), self.w * self.h * 4)

        size = wintypes.SIZE(self.w, self.h)
        src = wintypes.POINT(0, 0)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        user32.UpdateLayeredWindow(self.hwnd, self.screen_dc, None,
                                   ctypes.byref(size), self.mem_dc,
                                   ctypes.byref(src), 0, ctypes.byref(blend),
                                   ULW_ALPHA)

    def wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_NCHITTEST:
            # O recorte de clique acompanha o sprite: fora dele, o clique
            # atravessa para a janela de tras.
            if not self.hit:
                return HTTRANSPARENT
            sx, sy = ctypes.c_short(lparam & 0xFFFF).value, ctypes.c_short(lparam >> 16).value
            pt = wintypes.POINT(sx, sy)
            user32.ScreenToClient(hwnd, ctypes.byref(pt))
            x, y, w, h = self.hit
            inside = x <= pt.x <= x + w and y <= pt.y <= y + h
            return HTCLIENT if inside else HTTRANSPARENT
        if msg == WM_LBUTTONDOWN:
            self.on_click()
            return 0
        if msg == WM_TIMER:
            self.tick()
            return 0
        if msg == WM_CLOSE:          # taskkill sem /F chega assim
            self.begin_exit()
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def tick(self):
        f = None
        if self.phase == "intro":
            if self.i < len(self.seq["intro"]):
                f = self.seq["intro"][self.i]; self.i += 1
            else:
                self.phase, self.i = "loop", 0
        if f is None and self.phase == "loop":
            if not self.seq["loop"]:
                self.phase, self.i = "exit", 0
            else:
                f = self.seq["loop"][self.i % len(self.seq["loop"])]; self.i += 1
        if f is None and self.phase == "exit":
            if self.i < len(self.seq["exit"]):
                f = self.seq["exit"][self.i]; self.i += 1
            else:
                user32.DestroyWindow(self.hwnd)
                return
        self.frame = f
        self.hit = (f["x"] * self.cell - HIT_PAD, f["y"] * self.cell - HIT_PAD,
                    painter.W * self.cell + 2 * HIT_PAD,
                    painter.H * self.cell + 2 * HIT_PAD)
        self.present()
        user32.SetTimer(self.hwnd, 1, int(f.get("ms", 100)), None)

    def on_click(self):
        if self.leaving:
            return
        self.leaving = True
        token = ""
        try:
            with open(os.path.join(config.CACHE, "session-%s.win" % self.session)) as fh:
                token = fh.read()
        except OSError:
            pass
        wm.focus_window(token)
        self.begin_exit()

    def begin_exit(self):
        if self.phase != "exit":
            self.phase, self.i = "exit", 0

    def run(self):
        self.tick()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="ask", choices=["ask", "done"])
    ap.add_argument("--session", default="default")
    ap.add_argument("--variant", type=int, default=None)
    ap.add_argument("--bg", default=None)
    ap.add_argument("--shot", default=None,
                    help="renderiza um quadro em PNG e sai (usado pela CI)")
    args = ap.parse_args()

    cfg = config.load_config()
    if not cfg["enabled"] or not cfg["states"].get(args.state, True):
        return 0

    if args.shot:   # modo sem janela: so prova que o desenho funciona aqui
        cell = max(3, int(cfg["cell"]))
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, COLS * cell, ROWS * cell)
        seq = frames.sequence(args.state, args.variant)
        pt = painter.Painter(cell, (0.106, 0.106, 0.133))
        pt.draw(cairo.Context(surf), (seq["loop"] or seq["intro"])[-1])
        surf.write_to_png(args.shot)
        return 0

    os.makedirs(config.CACHE, exist_ok=True)
    with open(os.path.join(config.CACHE, "overlay.pid"), "w") as fh:
        fh.write(str(os.getpid()))

    overlay = Overlay(args.state, args.session, cfg, args.variant, args.bg)
    play_sound(args.state, cfg)
    if args.state == "ask" and cfg["ask_timeout"] > 0:
        user32.SetTimer(overlay.hwnd, 2, int(cfg["ask_timeout"]) * 1000, None)
    overlay.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
