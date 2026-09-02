#!/usr/bin/env python3
"""Despachante unico de todos os hooks do plugin.

Regra que manda aqui: este script NAO pode demorar. Ele nunca espera a
animacao, nunca le a decisao de ferramenta e sempre sai com 0 — qualquer outra
coisa vira atraso ou erro na sessao do Claude Code.

Era um script bash. Virou Python pelo mesmo motivo que o resto do plugin ja e:
o Windows nao tem bash. O comportamento em X11 e Wayland e o mesmo de antes,
verificado por tests/test_hook.py, que foi escrito contra a versao em bash
ANTES desta existir.
"""
import json
import os
import signal
import subprocess
import sys
import time

WINDOWS = os.name == "nt"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(
    os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache"),
    "claude-mascot",
)
PIDFILE = os.path.join(STATE, "overlay.pid")
STATEFILE = os.path.join(STATE, "overlay.state")
TSFILE = os.path.join(STATE, "overlay.ts")

DEDUPE_MS = 1500


def has_display():
    """Sem ambiente grafico nenhum (SSH, headless) o plugin nao existe. Qual dos
    dois servidores usar e decisao do overlay/wm.py, que ve o GDK_BACKEND tambem.
    No Windows nao ha variavel equivalente: a sessao grafica sempre existe."""
    return WINDOWS or bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def read_session():
    """O JSON do hook chega em stdin. So precisamos do session_id, e ele vira
    nome de arquivo: filtra para caracteres de id, nunca separador de caminho."""
    try:
        sid = str(json.load(sys.stdin).get("session_id") or "default")
    except Exception:
        return "default"
    keep = [c for c in sid if c.isalnum() or c in "_-"]
    return "".join(keep) or "default"


def read(path, default=None):
    try:
        with open(path) as fh:
            return fh.read()
    except OSError:
        return default


def write(path, text):
    try:
        with open(path, "w") as fh:
            fh.write(text)
    except OSError:
        pass


def alive(pid):
    try:
        if WINDOWS:
            out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid],
                                 capture_output=True, text=True, timeout=5).stdout
            return str(pid) in out
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def kill_overlay():
    pid = read(PIDFILE)
    try:
        pid = int((pid or "").strip())
    except ValueError:
        pid = 0
    if pid and alive(pid):
        try:
            if WINDOWS:
                subprocess.run(["taskkill", "/PID", str(pid)],
                               capture_output=True, timeout=5)
            else:
                # SIGTERM: o overlay responde com a animacao de saida.
                os.kill(pid, signal.SIGTERM)
        except Exception:
            pass
    try:
        os.remove(PIDFILE)
    except OSError:
        pass


def spawn_overlay(state, sid):
    """Desacopla o overlay: o hook nao pode ficar preso ate a animacao acabar."""
    cmd = [sys.executable, os.path.join(ROOT, "overlay", "mascot.py"),
           "--state", state, "--session", sid]
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
              "stdin": subprocess.DEVNULL, "cwd": ROOT}
    if WINDOWS:
        kwargs["creationflags"] = (getattr(subprocess, "DETACHED_PROCESS", 0x8)
                                   | getattr(subprocess, "CREATE_NO_WINDOW", 0x8000000))
    else:
        kwargs["start_new_session"] = True   # equivale ao setsid de antes
    try:
        subprocess.Popen(cmd, **kwargs)
    except Exception:
        pass


def main(argv):
    if not has_display():
        return 0
    try:
        os.makedirs(STATE, exist_ok=True)
    except OSError:
        return 0

    cmd = argv[0] if argv else ""

    if cmd == "session-start":
        sid = read_session()
        # Neste instante o usuario acabou de rodar `claude`: a janela em foco e o
        # terminal da sessao. E a unica hora em que da pra saber isso com certeza.
        # Quem pergunta ao servidor grafico e o wm.py — o hook nao sabe a diferenca.
        try:
            subprocess.run([sys.executable, os.path.join(ROOT, "overlay", "wm.py"),
                            "record", os.path.join(STATE, "session-%s.win" % sid)],
                           capture_output=True, timeout=5)
        except Exception:
            pass

    elif cmd == "show":
        state = argv[1] if len(argv) > 1 else "ask"
        sid = read_session()
        now = int(time.time() * 1000)
        try:
            last = int((read(TSFILE, "0") or "0").strip() or 0)
        except ValueError:
            last = 0
        prev = (read(STATEFILE, "") or "").strip()

        # dedupe por janela de tempo em vez de IPC. PermissionRequest,
        # Notification e PreToolUse:AskUserQuestion disparam para o mesmo pedido
        # com milissegundos de diferenca; sem isso sairiam varios mascotes.
        if state == "ask" and prev == "ask" and now - last < DEDUPE_MS:
            return 0

        kill_overlay()
        write(STATEFILE, state)
        write(TSFILE, str(now))
        spawn_overlay(state, sid)

    elif cmd == "dismiss":
        # So dispensa pedido de atencao; nunca corta a animacao de conclusao.
        if (read(STATEFILE, "") or "").strip() == "ask":
            kill_overlay()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception:
        sys.exit(0)   # o hook nunca pode falhar a sessao
