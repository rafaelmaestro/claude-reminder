#!/usr/bin/env bash
# Despachante unico de todos os hooks do plugin.
#
# Regra que manda aqui: este script NAO pode demorar. Ele nunca espera a
# animacao, nunca le a decisao de ferramenta e sempre sai com 0 — qualquer
# outra coisa vira atraso ou erro na sessao do Claude Code.

# Sem ambiente grafico nenhum (SSH, headless) o plugin nao existe. Qual dos dois
# servidores usar e decisao do overlay/wm.py, que ve o GDK_BACKEND tambem.
[ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ] || exit 0

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="${XDG_CACHE_HOME:-$HOME/.cache}/claude-mascot"
mkdir -p "$STATE" 2>/dev/null || exit 0
PIDFILE="$STATE/overlay.pid"
STATEFILE="$STATE/overlay.state"
TSFILE="$STATE/overlay.ts"

CMD="${1:-}"; shift 2>/dev/null || true

# O JSON do hook chega em stdin. So precisamos do session_id, e so em alguns
# comandos — ler sempre custaria um processo python por chamada de ferramenta.
read_session() {
  python3 -c 'import json,sys
try:
    import re
    sid = str(json.load(sys.stdin).get("session_id") or "default")
    print(re.sub(r"[^A-Za-z0-9_-]", "", sid) or "default")
except Exception: print("default")' 2>/dev/null || echo default
}

alive() {
  [ -f "$PIDFILE" ] || return 1
  kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null
}

kill_overlay() {
  if alive; then
    # SIGTERM: o overlay responde com a animacao de saida (ver mascot.py).
    kill -TERM "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null
  fi
  rm -f "$PIDFILE" 2>/dev/null
}

case "$CMD" in
  session-start)
    sid="$(read_session)"
    # Neste instante o usuario acabou de rodar `claude`: a janela em foco e o
    # terminal da sessao. E a unica hora em que da pra saber isso com certeza.
    # Quem pergunta ao X11 ou ao compositor e o wm.py — o hook nao sabe a
    # diferenca, e assim nao precisa de jq para ler o JSON do hyprctl.
    python3 "$ROOT/overlay/wm.py" record "$STATE/session-$sid.win" 2>/dev/null
    ;;

  show)
    state="${1:-ask}"
    sid="$(read_session)"
    now="$(date +%s%3N 2>/dev/null || echo 0)"
    last="$(cat "$TSFILE" 2>/dev/null || echo 0)"
    prev="$(cat "$STATEFILE" 2>/dev/null || echo)"

    # ponytail: dedupe por janela de tempo em vez de IPC. Notification e
    # PreToolUse:AskUserQuestion disparam para o mesmo pedido com milissegundos
    # de diferenca; sem isso sairiam dois mascotes e dois sons.
    if [ "$state" = "ask" ] && [ "$prev" = "ask" ] && [ $((now - last)) -lt 1500 ]; then
      exit 0
    fi

    kill_overlay
    printf '%s' "$state" > "$STATEFILE"
    printf '%s' "$now" > "$TSFILE"
    setsid python3 "$ROOT/overlay/mascot.py" --state "$state" --session "$sid" \
      >/dev/null 2>&1 < /dev/null &
    ;;

  dismiss)
    # So dispensa pedido de atencao; nunca corta a animacao de conclusao.
    [ "$(cat "$STATEFILE" 2>/dev/null)" = "ask" ] && kill_overlay
    ;;
esac

exit 0
