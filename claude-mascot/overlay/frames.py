#!/usr/bin/env python3
"""Coreografia do mascote: monta a lista de quadros de um evento.

Um quadro e um dicionario com a pose, onde ela cai na grade e quanto tempo
fica na tela. Quem desenha e o mascot.py; aqui so se decide o que aparece e
por quanto tempo.

    intro  entra andando e se apresenta (roda uma vez)
    loop   insiste ate o usuario responder (so o pedido de atencao tem)
    exit   sai andando (roda uma vez, e o processo morre)
"""
import random

from poses import GRID

W, H = GRID["w"], GRID["h"]
PW, POFF = GRID["pw"], GRID["poff"]

COLS, ROWS = 43, 24          # tamanho da faixa em celulas (ver mascot.py)

# Sobra a direita suficiente para a camada de adereco (mais larga que o corpo)
REST_X = COLS - PW - 1
BASE_Y = 10                  # linha em que ele fica de pe
GROUND_Y = BASE_Y + H        # a sombra do chao nao sobe junto no pulo

# Poses de perfil: usadas na entrada e na saida andando.
SIDE = ("side_a", "side_b")


def frame(pose, **extra):
    f = {"p": pose, "x": REST_X, "y": BASE_Y, "ground": "wide", "ms": 120}
    f.update(extra)
    return f


def walk_in():
    out, i = [], 0
    for x in range(COLS, REST_X, -2):
        out.append(frame(SIDE[i % 2], x=x, ground="wide", ms=85))
        i += 1
    return out


def walk_out():
    out, i = [], 0
    for x in range(REST_X, COLS + 1, 2):
        out.append(frame(SIDE[i % 2], x=x, ground="wide", ms=85, flip=True))
        i += 1
    return out


def wave(times, sym, ms=140):
    out = []
    for _ in range(times):
        out.append(frame("front_up_happy", y=BASE_Y - 1, sym=sym, symDy=-1,
                         ground="narrow", ms=ms))
        out.append(frame("front_happy", sym=sym, ms=ms))
    return out


# Poses que mexem os bracos. Variacao que segura objeto na mao nao pode usar
# nenhuma delas — o braco sobe e o objeto fica flutuando onde estava.
# front_squash tambem esta fora de qualquer variacao com adereco: ela desloca
# o corpo dentro da grade, e o adereco, que e desenhado em linhas fixas,
# descola do corpo.


def apply_prop(frames, prop):
    """Espalha o adereco por TODOS os quadros da sequencia, escolhendo a versao
    de frente ou de perfil conforme a pose. E o que impede o objeto de piscar
    entre a caminhada e a pose de frente."""
    if not prop:
        return frames
    out = []
    for f in frames:
        if f.get("prop"):
            out.append(f)
            continue
        c = dict(f)
        c["prop"] = prop["side"] if f["p"] in SIDE else prop["front"]
        out.append(c)
    return out


def exit_frames(variant):
    if variant.get("prop"):
        return [frame("front_wide", ms=120), frame("front", ms=90)]
    return [frame("front_squash", ms=130), frame("front", ms=90)]


# Variacoes do pedido de atencao. Uma e sorteada por evento — o mesmo aviso
# repetido vinte vezes por dia vira ruido; variando, continua sendo notado.
ASK_VARIANTS = [
    {   # pulo: sem nenhum icone, so o bicho pulando alto e acenando. A
        # expressao fica parada e ha uma unica piscada por ciclo — trocar a
        # forma dos olhos a cada quadro fazia ele parecer que piscava sem parar.
        "intro": [frame("front", ms=140), frame("front", ms=160)],
        "loop": [
            frame("front_up", y=BASE_Y - 2, ground="narrow", ms=100),
            frame("front_up", y=BASE_Y - 4, ground="narrow", ms=100),
            frame("front_up", y=BASE_Y - 2, ground="narrow", ms=90),
            frame("front_squash", ms=110),
            frame("front", ms=300),
            frame("front_wave_a", x=REST_X - 1, ms=120),
            frame("front_wave_b", x=REST_X + 1, ms=120),
            frame("front_wave_a", x=REST_X - 1, ms=120),
            frame("front_wave_b", x=REST_X + 1, ms=120),
            frame("front", ms=340),
            frame("front_blink", ms=100),
            frame("front", ms=460),
        ],
    },
    {   # lampada: teve uma ideia e quer contar. Quem acende e apaga e a
        # lampada; o rosto fica parado, com uma piscada por ciclo.
        "intro": [frame("front", ms=130), frame("front_wide", sym="bulb_on", ms=190)],
        "loop": [
            frame("front_up", y=BASE_Y - 2, sym="bulb_on", symDy=-1,
                  ground="narrow", ms=120),
            frame("front", sym="bulb_on", ms=280),
            frame("front", sym="bulb_off", ms=130),
            frame("front", sym="bulb_on", ms=300),
            frame("front_up", y=BASE_Y - 3, sym="bulb_on", symDy=-2,
                  ground="narrow", ms=110),
            frame("front", sym="bulb_on", ms=260),
            frame("front_blink", sym="bulb_off", ms=100),
            frame("front", sym="bulb_on", ms=380),
        ],
    },
    {   # fone de ouvido: vestido, entao os bracos podem se mexer a vontade. O
        # sorriso e segurado por um quadro longo em vez de alternar a cada quadro.
        "prop": {"front": "headphones", "side": "headphones_side"},
        "intro": [frame("front", ms=160)],
        "loop": [
            frame("front", x=REST_X - 1, ms=200),
            frame("front", x=REST_X + 1, ms=200),
            frame("front_happy", ms=320),
            frame("front", x=REST_X - 1, ms=200),
            frame("front", x=REST_X + 1, ms=200),
            frame("front_up", y=BASE_Y - 2, ground="narrow", ms=130),
            frame("front", ms=300),
            frame("front_blink", ms=100),
            frame("front", ms=360),
        ],
    },
    {   # capacete e martelo: o martelo fica firme na mao. Anima-lo em dois
        # quadros trocava a cabeca de cima para baixo do punho, o que nao le
        # como martelada e sim como a cabeca teleportando.
        "prop": {"front": "work_a", "side": "work_side"},
        "intro": [frame("front", ms=160)],
        "loop": [
            frame("front", ms=280),
            frame("front", x=REST_X - 1, ms=170),
            frame("front", x=REST_X + 1, ms=170),
            frame("front", y=BASE_Y - 2, ground="narrow", ms=120),
            frame("front", ms=300),
            frame("front_blink", ms=100),
            frame("front", ms=380),
        ],
    },
    {   # cafe: o braco que segura a xicara NAO se mexe em nenhum quadro.
        # O que anima e o vapor (mug_a / mug_b), o rosto e o pulo do corpo inteiro.
        "prop": {"front": "mug_a", "side": "mug_side"},
        "intro": [frame("front", ms=160)],
        "loop": [
            frame("front", prop="mug_a", ms=150),
            frame("front_blink", prop="mug_b", ms=110),
            frame("front_happy", prop="mug_a", ms=140),
            frame("front", x=REST_X - 1, prop="mug_b", ms=140),
            frame("front", y=BASE_Y - 2, prop="mug_a", ground="narrow", ms=120),
            frame("front", prop="mug_b", ms=190),
        ],
    },
    {   # oculos escuros: sao adereco, entao acompanham toda pose e toda
        # caminhada. Como pose do corpo sumiam na piscada e o rosto piscava.
        "prop": {"front": "shades", "side": "shades_side"},
        "intro": [frame("front", ms=160)],
        "loop": [
            frame("front", ms=170),
            frame("front", x=REST_X - 1, ms=120),
            frame("front", x=REST_X + 1, ms=120),
            frame("front", x=REST_X - 1, ms=120),
            frame("front_wide", ms=160),
            frame("front_blink", ms=100),
            frame("front", ms=200),
        ],
    },
]

# A conclusao tambem varia — so que sem loop: roda uma vez e vai embora.
# Ela e mais demorada que o pedido de proposito: e a unica chance de ser
# vista, entao precisa dar tempo de o olho chegar nela.
DONE_VARIANTS = [
    {   # placa com o check: erguida acima da cabeca pelos dois bracos. Como ela
        # esta nas maos, nenhum quadro muda a pose do braco — o que anima sao os
        # olhos, o balanco e o pulo, que levam a placa junto.
        "prop": {"front": "sign", "side": "sign"},
        "intro": [
            frame("front_up", ms=200),
            frame("front_up_happy", ms=240),
            frame("front_up_happy", y=BASE_Y - 2, ground="narrow", ms=150),
            frame("front_up_happy", ms=180),
            frame("front_up_happy", x=REST_X - 1, ms=170),
            frame("front_up_happy", x=REST_X + 1, ms=170),
            frame("front_up_blink", ms=120),
            frame("front_up_happy", y=BASE_Y - 2, ground="narrow", ms=150),
            frame("front_up_happy", ms=200),
            frame("front_up_wink", ms=340),
            frame("front_up_happy", ms=200),
            frame("front_up_blink", ms=120),
            frame("front_up_happy", ms=300),
        ],
    },
    {   # coracao: de nada
        "intro": [
            frame("front", ms=150),
            frame("front_wide", sym="heart", ms=200),
            frame("front_happy", sym="heart", ms=280),
        ] + wave(5, "heart") + [
            frame("front_wink", sym="heart", ms=340),
            frame("front_happy", sym="heart", ms=200),
            frame("front_blink", sym="heart", ms=120),
            frame("front_happy", sym="heart", ms=320),
        ],
    },
    {   # bau de tesouro: chega carregando o bau, poe no chao, abre e o ouro
        # brilha. Sem pulo em nenhum quadro — o bau ficaria flutuando junto.
        "prop": {"front": "chest_closed", "side": "chest_closed"},
        "intro": [
            frame("front", ms=200),
            frame("front_wide", prop="chest_closed", ms=320),
            frame("front_wide", prop="chest_open", ms=240),
            frame("front_up_happy", prop="chest_shine", ms=200),
            frame("front_happy", prop="chest_open", ms=170),
            frame("front_up_happy", prop="chest_shine", ms=200),
            frame("front_happy", prop="chest_open", ms=170),
            frame("front_up_happy", prop="chest_shine", ms=200),
            frame("front_happy", prop="chest_open", ms=170),
            frame("front_up_happy", prop="chest_shine", ms=200),
            frame("front_wink", prop="chest_shine", ms=340),
            frame("front_happy", prop="chest_open", ms=200),
            frame("front_blink", prop="chest_shine", ms=120),
            frame("front_happy", prop="chest_open", ms=320),
        ],
    },
    {   # fogos de artificio: sem objeto na mao, entao e a unica conclusao em que
        # os bracos sobem e descem a vontade. Os estouros trocam de cor e de
        # posicao a cada quadro, o que mascara o pulo levar o adereco junto.
        "prop": {"front": "fw_a", "side": "fw_a"},
        "intro": [
            frame("front", ms=150),
            frame("front_wide", prop="fw_a", ms=190),
            frame("front_up_happy", y=BASE_Y - 1, prop="fw_b", ground="narrow", ms=160),
            frame("front_happy", prop="fw_c", ms=150),
            frame("front_up_happy", y=BASE_Y - 2, prop="fw_a", ground="narrow", ms=160),
            frame("front_happy", prop="fw_b", ms=150),
            frame("front_up_happy", y=BASE_Y - 1, prop="fw_c", ground="narrow", ms=160),
            frame("front_happy", prop="fw_a", ms=150),
            frame("front_up_happy", y=BASE_Y - 2, prop="fw_b", ground="narrow", ms=160),
            frame("front_happy", prop="fw_c", ms=150),
            frame("front_wink", prop="fw_a", ms=340),
            frame("front_happy", prop="fw_b", ms=200),
            frame("front_blink", prop="fw_c", ms=120),
            frame("front_happy", prop="fw_a", ms=300),
        ],
    },
]


def pick(variants, forced=None):
    if forced is None:
        return random.choice(variants)
    return variants[forced % len(variants)]


def sequence(state, forced=None):
    """Devolve (intro, loop, exit) do evento."""
    if state == "done":
        v = pick(DONE_VARIANTS, forced)
        loop = []                      # conclusao nao insiste: roda uma vez e sai
        out = walk_out()
    else:
        v = pick(ASK_VARIANTS, forced)
        loop = v["loop"]
        out = exit_frames(v) + walk_out()

    prop = v.get("prop")
    intro = walk_in() + [frame("side_a", ms=80)] + v["intro"]
    return (apply_prop(intro, prop), apply_prop(loop, prop), apply_prop(out, prop))
