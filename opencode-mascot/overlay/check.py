#!/usr/bin/env python3
"""Check do renderizador: toda pose tem que caber na grade e usar so a paleta.

Uma pose com uma linha de tamanho errado nao quebra nada visivelmente — ela so
desloca meio corpo do mascote. E o modo de falha mais provavel deste projeto,
entao e o que o check cobre. Rode: python3 check.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PALETTE = set(".OKWGPBYARN")


def blocks(src, section):
    """Extrai os blocos `nome: \\`...\\`` de dentro de um const do poses.js."""
    start = src.index("const %s" % section)
    depth, i = 0, src.index("{", start)
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                body = src[i : j + 1]
                break
    return re.findall(r"(\w+)\s*:\s*`\n(.*?)`", body, re.S)


def main():
    src = open(os.path.join(HERE, "poses.js")).read()
    dims = dict(re.findall(r"(\w+):\s*(\d+)", src[src.index("const GRID") : src.index("const POSES")]))
    errors = []

    for section, w, h in (("POSES", int(dims["w"]), int(dims["h"])),
                          ("PROPS", int(dims["pw"]), int(dims["ph"])),
                          ("SYMBOLS", int(dims["sw"]), int(dims["sh"]))):
        found = blocks(src, section)
        assert found, "nenhuma pose encontrada em %s" % section
        for name, body in found:
            rows = body.split("\n")[:-1] if body.endswith("\n") else body.split("\n")
            if len(rows) != h:
                errors.append("%s.%s: %d linhas, esperado %d" % (section, name, len(rows), h))
            for n, row in enumerate(rows):
                if len(row) != w:
                    errors.append("%s.%s linha %d: %d colunas, esperado %d"
                                  % (section, name, n, len(row), w))
                bad = set(row) - PALETTE
                if bad:
                    errors.append("%s.%s linha %d: caractere fora da paleta %s"
                                  % (section, name, n, sorted(bad)))
        print("%s: %d poses verificadas" % (section, len(found)))

    # As sequencias so podem citar poses e simbolos que existem.
    html = open(os.path.join(HERE, "mascot.html")).read()
    known_p = {n for n, _ in blocks(src, "POSES")}
    known_s = {n for n, _ in blocks(src, "SYMBOLS")}
    known_r = {n for n, _ in blocks(src, "PROPS")}
    for ref in set(re.findall(r"\bp:\s*'(\w+)'", html)):
        if ref not in known_p:
            errors.append("mascot.html usa pose inexistente: %s" % ref)
    for ref in set(re.findall(r"sym:\s*'(\w+)'", html)):
        if ref not in known_s:
            errors.append("mascot.html usa simbolo inexistente: %s" % ref)
    for ref in set(re.findall(r"prop:\s*'(\w+)'", html)):
        if ref not in known_r:
            errors.append("mascot.html usa adereco inexistente: %s" % ref)

    if errors:
        print("\nFALHOU:")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    print("ok")


if __name__ == "__main__":
    main()
