#!/usr/bin/env bash
# Mesmas verificacoes do job linux da CI, rodando na sua maquina.
#
# Existe porque a Actions do repositorio esta bloqueada por um flag de billing
# na conta. Enquanto isso nao destrava, este script e a guarda contra quebrar o
# X11 e o Wayland. Quando a CI voltar, ele continua util: e o mesmo comando,
# antes de abrir o PR.
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.."
fail=0
run() {
  printf '  %-52s' "$1"; shift
  if out="$("$@" 2>&1)"; then echo "ok"; else echo "FALHOU"; echo "$out" | sed 's/^/      /'; fail=1; fi
}
echo "verificacoes do plugin"
run "poses, adereços, simbolos e sequencias"  python3 claude-mascot/overlay/check.py
run "contrato do hook (implementacao atual)"  python3 claude-mascot/tests/test_hook.py
run "contrato do hook (bash legado)"          python3 claude-mascot/tests/test_hook.py bash %ROOT%/hooks/mascot.sh
run "manifesto do plugin"                     python3 -c "import json;json.load(open('claude-mascot/.claude-plugin/plugin.json'))"
run "manifesto do marketplace"                python3 -c "import json;json.load(open('.claude-plugin/marketplace.json'))"
run "hooks.json"                              python3 -c "import json;json.load(open('claude-mascot/hooks/hooks.json'))"
run "tudo compila"                            python3 -m compileall -q claude-mascot
[ "$fail" = 0 ] && echo "tudo ok" || echo "FALHOU — nao suba assim"
exit "$fail"
