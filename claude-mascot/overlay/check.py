#!/usr/bin/env python3
"""Check do renderizador: toda pose tem que caber na grade e usar so a paleta.

Uma pose com uma linha de tamanho errado nao quebra nada visivelmente — ela so
desloca meio corpo do mascote. E o modo de falha mais provavel deste projeto,
entao e o que o check cobre. Rode: python3 check.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import frames  # noqa: E402
import mascot  # noqa: E402
from poses import GRID, POSES, PROPS, SYMBOLS  # noqa: E402

PALETTE = set(".OKWGPBYARN")


def main():
    errors = []

    for label, art, w, h in (
        ("POSES", POSES, GRID["w"], GRID["h"]),
        ("PROPS", PROPS, GRID["pw"], GRID["ph"]),
        ("SYMBOLS", SYMBOLS, GRID["sw"], GRID["sh"]),
    ):
        assert art, "nenhuma pose encontrada em %s" % label
        for name, block in art.items():
            rows = block.strip("\n").split("\n")
            if len(rows) != h:
                errors.append("%s.%s: %d linhas, esperado %d" % (label, name, len(rows), h))
            for n, row in enumerate(rows):
                if len(row) != w:
                    errors.append("%s.%s linha %d: %d colunas, esperado %d"
                                  % (label, name, n, len(row), w))
                bad = set(row) - PALETTE
                if bad:
                    errors.append("%s.%s linha %d: caractere fora da paleta %s"
                                  % (label, name, n, sorted(bad)))
        print("%s: %d poses verificadas" % (label, len(art)))

    # A paleta do desenho tem que cobrir todo caractere que a arte usa: um
    # caractere sem cor nao quebra, so abre um buraco no meio do mascote.
    for ch in PALETTE:
        if ch not in mascot.PAL:
            errors.append("mascot.PAL nao tem cor para o caractere %r" % ch)

    # As sequencias so podem citar poses, simbolos e adereços que existem, em
    # TODAS as variacoes — inclusive as que o sorteio quase nunca escolhe.
    seen = 0
    for state, variants in (("ask", frames.ASK_VARIANTS), ("done", frames.DONE_VARIANTS)):
        for i in range(len(variants)):
            intro, loop, out = frames.sequence(state, i)
            for f in intro + loop + out:
                seen += 1
                if f["p"] not in POSES:
                    errors.append("%s[%d] usa pose inexistente: %s" % (state, i, f["p"]))
                if f.get("sym") and f["sym"] not in SYMBOLS:
                    errors.append("%s[%d] usa simbolo inexistente: %s" % (state, i, f["sym"]))
                if f.get("prop") and f["prop"] not in PROPS:
                    errors.append("%s[%d] usa adereco inexistente: %s" % (state, i, f["prop"]))
    print("SEQUENCIAS: %d quadros verificados" % seen)

    if errors:
        print("\nFALHOU:")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    print("ok")


if __name__ == "__main__":
    main()
