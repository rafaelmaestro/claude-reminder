#!/usr/bin/env python3
"""Contrato do despachante de hooks, fixado antes de qualquer reescrita.

Roda contra qualquer implementacao (mascot.sh hoje, mascot.py depois): passa o
comando base em argv, ou deixa vazio para testar a que o hooks.json aponta.

O overlay e o wm sao substituidos por stubs, entao nenhum teste abre janela,
toca som ou toca no seu ~/.cache. O que se verifica e o comportamento
observavel do hook: o que ele grava, o que ele mata, o que ele dispara e com
quais argumentos.

    python3 claude-mascot/tests/test_hook.py
    python3 claude-mascot/tests/test_hook.py bash %ROOT%/hooks/mascot.sh
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)

STUB_OVERLAY = '''#!/usr/bin/env python3
import os, sys, time
cache = os.path.join(os.environ["XDG_CACHE_HOME"], "claude-mascot")
os.makedirs(cache, exist_ok=True)
open(os.path.join(cache, "overlay.pid"), "w").write(str(os.getpid()))
with open(os.path.join(cache, "spawn.log"), "a") as fh:
    fh.write(" ".join(sys.argv[1:]) + "\\n")
time.sleep(30)
'''

STUB_WM = '''#!/usr/bin/env python3
import os, sys
if len(sys.argv) > 2 and sys.argv[1] == "record":
    open(sys.argv[2], "w").write("x11:12345")
    with open(os.path.join(os.environ["XDG_CACHE_HOME"], "claude-mascot", "wm.log"), "a") as fh:
        fh.write(" ".join(sys.argv[1:]) + "\\n")
'''


class Sandbox:
    """Copia do plugin com overlay e wm trocados por stubs, cache proprio."""

    def __init__(self, base_cmd):
        self.dir = tempfile.mkdtemp(prefix="mascot-test-")
        self.root = os.path.join(self.dir, "plugin")
        shutil.copytree(PLUGIN, self.root,
                        ignore=shutil.ignore_patterns("tests", "__pycache__"))
        # os dois pontos de entrada do overlay: o hook escolhe por plataforma
        for name, body in (("mascot.py", STUB_OVERLAY),
                           ("mascot_win32.py", STUB_OVERLAY),
                           ("wm.py", STUB_WM)):
            p = os.path.join(self.root, "overlay", name)
            open(p, "w").write(body)
            os.chmod(p, 0o755)
        self.cache = os.path.join(self.dir, "cache")
        os.makedirs(os.path.join(self.cache, "claude-mascot"))
        self.base_cmd = [a.replace("%ROOT%", self.root) for a in base_cmd]

    def state_dir(self):
        return os.path.join(self.cache, "claude-mascot")

    def read(self, name):
        p = os.path.join(self.state_dir(), name)
        return open(p).read() if os.path.exists(p) else None

    def run(self, *args, session="s1", stdin=None, display=":1", wayland=None):
        env = dict(os.environ)
        env["XDG_CACHE_HOME"] = self.cache
        env.pop("DISPLAY", None)
        env.pop("WAYLAND_DISPLAY", None)
        if display:
            env["DISPLAY"] = display
        if wayland:
            env["WAYLAND_DISPLAY"] = wayland
        payload = stdin if stdin is not None else json.dumps({"session_id": session})
        t0 = time.time()
        p = subprocess.run(self.base_cmd + list(args), input=payload, text=True,
                           capture_output=True, env=env, timeout=20)
        return p.returncode, time.time() - t0

    def spawns(self):
        return (self.read("spawn.log") or "").strip().splitlines()

    def wait_spawns(self, n, timeout=3.0):
        """O hook devolve na hora e o overlay sobe em outro processo: sem esperar,
        o teste leria o log antes de ele existir."""
        end = time.time() + timeout
        while time.time() < end:
            if len(self.spawns()) >= n:
                break
            time.sleep(0.05)
        return self.spawns()

    def overlay_alive(self):
        pid = self.read("overlay.pid")
        if not pid:
            return False
        try:
            if os.name == "nt":
                out = subprocess.run(["tasklist", "/FI", "PID eq %s" % pid.strip()],
                                     capture_output=True, text=True, timeout=10).stdout
                return pid.strip() in out
            os.kill(int(pid), 0)
            return True
        except Exception:
            return False

    def cleanup(self):
        pid = self.read("overlay.pid")
        if pid:
            try:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/F", "/PID", pid.strip()],
                                   capture_output=True, timeout=10)
                else:
                    os.kill(int(pid), 9)
            except Exception:
                pass
        shutil.rmtree(self.dir, ignore_errors=True)


def main():
    base = sys.argv[1:] or [sys.executable, "%ROOT%/hooks/hook.py"]
    fails = []

    def check(name, cond, detail=""):
        print("  %-58s %s" % (name, "ok" if cond else "FALHOU"))
        if not cond:
            fails.append("%s %s" % (name, detail))

    # --- guarda de ambiente grafico ---------------------------------------
    sb = Sandbox(base)
    rc, _ = sb.run("show", "ask", display=None, wayland=None)
    check("sem DISPLAY e sem WAYLAND_DISPLAY: sai 0", rc == 0, "rc=%s" % rc)
    check("sem ambiente grafico: nao dispara overlay", sb.read("spawn.log") is None)
    sb.cleanup()

    sb = Sandbox(base)
    rc, _ = sb.run("show", "ask", display=None, wayland="wayland-0")
    check("so WAYLAND_DISPLAY: dispara", len(sb.wait_spawns(1)) == 1)
    sb.cleanup()

    # --- session-start -----------------------------------------------------
    sb = Sandbox(base)
    sb.run("session-start", session="abc-123")
    check("session-start grava a janela via wm record",
          sb.read("session-abc-123.win") == "x11:12345")
    sb.run("session-start", stdin='{"session_id":"../../etc/passwd"}')
    check("session_id com travessia e sanitizado",
          sb.read("session-etcpasswd.win") is not None
          and not os.path.exists(os.path.join(sb.state_dir(), "..", "etc")))
    sb.run("session-start", stdin="nao e json")
    check("stdin invalido cai em 'default'", sb.read("session-default.win") is not None)
    sb.cleanup()

    # --- show --------------------------------------------------------------
    sb = Sandbox(base)
    rc, dt = sb.run("show", "ask", session="s1")
    check("show ask: sai 0", rc == 0)
    check("show ask: retorna sem esperar a animacao", dt < 2.0, "%.1fs" % dt)
    check("show ask: grava estado 'ask'", sb.read("overlay.state") == "ask")
    spawns = sb.wait_spawns(1)
    check("show ask: passa --state ask --session s1",
          spawns == ["--state ask --session s1"], repr(spawns))
    check("show ask: overlay fica vivo", sb.overlay_alive())

    sb.run("show", "ask", session="s1")
    time.sleep(0.6)
    check("dois 'show ask' seguidos: deduplicado (1 spawn)", len(sb.spawns()) == 1)

    time.sleep(1.2)
    sb.run("show", "ask", session="s1")
    check("'show ask' apos 1,5s: dispara de novo", len(sb.wait_spawns(2)) == 2)
    sb.cleanup()

    # --- done nao e deduplicado, e sempre substitui -------------------------
    sb = Sandbox(base)
    sb.run("show", "ask")
    sb.wait_spawns(1)
    first = sb.read("overlay.pid")
    sb.run("show", "done")
    check("show done: nao e bloqueado pelo dedupe de ask", len(sb.wait_spawns(2)) == 2)
    check("show done: grava estado 'done'", sb.read("overlay.state") == "done")
    check("show done: substitui o overlay anterior", sb.read("overlay.pid") != first)
    sb.cleanup()

    # --- dismiss -----------------------------------------------------------
    sb = Sandbox(base)
    sb.run("show", "ask")
    sb.wait_spawns(1)
    sb.run("dismiss")
    time.sleep(0.4)
    check("dismiss com estado 'ask': encerra o overlay", not sb.overlay_alive())
    sb.cleanup()

    sb = Sandbox(base)
    sb.run("show", "done")
    sb.wait_spawns(1)
    sb.run("dismiss")
    time.sleep(0.4)
    check("dismiss com estado 'done': NAO encerra", sb.overlay_alive())
    sb.cleanup()

    # --- nunca falha -------------------------------------------------------
    sb = Sandbox(base)
    codes = [sb.run("comando-inexistente")[0], sb.run()[0], sb.run("dismiss")[0]]
    check("comando desconhecido, vazio ou sem estado: sempre 0", codes == [0, 0, 0], str(codes))
    sb.cleanup()

    print()
    if fails:
        print("FALHOU (%d):" % len(fails))
        for f in fails:
            print("  -", f)
        return 1
    print("contrato do hook: tudo ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
