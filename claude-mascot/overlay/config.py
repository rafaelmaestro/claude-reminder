#!/usr/bin/env python3
"""Configuracao e caminhos de estado, compartilhados pelos backends de janela."""
import json
import os

CACHE = os.path.join(
    os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache"),
    "claude-mascot",
)
CONFIG = os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config"),
    "claude-mascot",
    "config.json",
)

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
