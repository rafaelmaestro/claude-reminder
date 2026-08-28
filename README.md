<h1 align="center">claude-reminder</h1>

<p align="center">
  <b>O mascote do Claude aparece, se mexe e faz barulho quando o Claude precisa de você.</b><br>
  Clique nele e você volta direto pro terminal.
</p>

<p align="center">
  <img src="docs/animacoes.gif" alt="As dez animações do mascote" width="100%">
</p>

<p align="center">
  <sub>X11 · Claude Code · zero dependência nova</sub>
</p>

---

## O problema

Você manda o Claude Code trabalhar, troca de janela e vai fazer outra coisa. O
Claude para no meio pedindo permissão pra rodar um comando — e fica esperando.
Em silêncio. Você só descobre dez minutos depois.

O sino do terminal não diz **o que** aconteceu nem **em qual monitor**. A
notificação do GNOME some sozinha. Numa área de trabalho de vários monitores,
o terminal é fácil demais de perder de vista.

## A solução

Um bichinho de 70 pixels entra andando no canto inferior direito do monitor
que está em foco, toca um som e fica pulando até você responder. Clicou nele,
o terminal volta pra frente e ele sai andando.

```
        ?                              v
     \ (o o) /                      (^ - ^)
       |   |     pedindo              |   |     terminou
       n   n     permissão            n   n     tchauzinho
```

---

## Instalação

Dentro do Claude Code:

```
/plugin marketplace add rafaelmaestro/claude-reminder
/plugin install claude-mascot@claude-reminder
```

Reinicie a sessão. Pronto — não tem passo dois.

### Requisitos

Tudo isso já vem no Ubuntu com GNOME. Se estiver faltando algo:

```bash
sudo apt install python3-gi gir1.2-webkit2-4.1 xdotool pipewire-bin \
                 sound-theme-freedesktop
```

| precisa de | por quê |
|---|---|
| **X11** | posicionar janela, always-on-top e recorte de clique |
| `python3-gi` (GTK 3.0 + WebKit2 4.1) | desenhar e animar o mascote |
| `xdotool` | achar o monitor em foco e devolver o foco ao terminal |
| `pw-play` (PipeWire) | tocar o som |
| `sound-theme-freedesktop` | os arquivos de som |

> **Wayland não funciona.** No Wayland um aplicativo comum não pode se
> posicionar sozinho na tela. Se você não tem `DISPLAY` — sessão por SSH,
> headless — o plugin simplesmente não faz nada, sem erro nenhum.

---

## O que dispara o quê

| hook do Claude Code | o que acontece |
|---|---|
| `Notification` | pedido de permissão → mascote entra e insiste |
| `PreToolUse` · `AskUserQuestion` | Claude fez uma pergunta → mesma coisa |
| `PostToolUse` | você aprovou e a ferramenta rodou → mascote sai |
| `Stop` | Claude terminou → comemoração e tchauzinho |
| `SessionStart` | grava qual janela é o seu terminal (pro clique funcionar) |

Nenhum hook lê, altera ou atrasa decisão de ferramenta. Todos saem
imediatamente com código 0 e deixam a animação rodando em outro processo.

---

## As animações

O pedido de atenção **sorteia uma das sete** a cada vez. O mesmo aviso repetido
vinte vezes por dia deixa de ser notado — variando, continua funcionando.

| pedindo permissão | o que faz |
|---|---|
| **?** | pula alto, aterrissa e acena com os dois braços alternados |
| **lâmpada** | teve uma ideia e quer contar; a lâmpada acende e apaga |
| **fone** | esperando você, balançando de um lado pro outro |
| **capacete** | parado no meio do serviço, martelando |
| **café** | esperando sua resposta sem pressa |
| **impaciente** | sobrancelha grossa, batendo o pé |
| **passarinho** | veio acompanhado te avisar |

| tarefa concluída | o que faz |
|---|---|
| **check** | o ✓ verde se desenha, aceno e piscadinha |
| **coração** | de nada |
| **faíscas** | comemoração com varinha |

A conclusão roda **uma vez** e vai embora sozinha. O pedido fica em loop até
você responder (ou até o tempo limite).

---

## Configuração

Opcional. Copie `claude-mascot/config.example.json` para
`~/.config/claude-mascot/config.json`:

| chave | padrão | o que faz |
|---|---|---|
| `enabled` | `true` | desliga tudo sem desinstalar |
| `states.ask` | `true` | mascote no pedido de permissão |
| `states.done` | `true` | mascote no fim da tarefa |
| `mute` | `false` | mantém a animação, corta o som |
| `volume` | `1.0` | 0 a 1 |
| `ask_timeout` | `60` | segundos até ele desistir sozinho |
| `cell` | `7` | pixels por célula — **o tamanho do boneco** |
| `sounds.ask` / `sounds.done` | sons do sistema | caminho de outro arquivo |

Arquivo ausente ou com JSON inválido: usa os padrões e segue funcionando.

**Achou pequeno?** `"cell": 10`. **Achou intrusivo?** `"cell": 5` e
`"mute": true`.

---

## Editando as animações

As poses são blocos de texto, um caractere por pixel. Mexer é trocar letra:

```
.  vazio    O  laranja   K  preto    W  branco
G  verde    P  roxo      B  azul     Y  amarelo
A  cinza    R  vermelho
```

```js
front_happy: `
...............
...............
..OOOOOOOOOOO..
..OOOOOOOOOOO..
..OOOOOOOOOOO..
..OOKOOOOOKOO..
.OOKKKOOOKKKOO.
.OOOOOOOOOOOOO.
..OOOOOOOOOOO..
..OOOOOOOOOOO..
..O.O.....O.O..
..O.O.....O.O..
`,
```

Depois de mexer, rode o check — uma linha com uma coluna a mais não quebra
nada visivelmente, só desloca meio corpo do mascote:

```bash
python3 claude-mascot/overlay/check.py
```

Pra ver sem esperar o Claude Code:

```bash
python3 claude-mascot/overlay/mascot.py --state ask               # sorteia
python3 claude-mascot/overlay/mascot.py --state ask --variant 3   # força uma
python3 claude-mascot/overlay/mascot.py --state done --variant 1
```

Adereços (`PROPS` em `poses.js`) são uma camada por cima do corpo — uma
variação nova não exige redesenhar as poses.

---

## Como funciona

```
hook ──▶ mascot.sh ──▶ (setsid) mascot.py ──▶ WebKit ──▶ mascot.html
  │       sai com 0      janela GTK              pixel art em
  │       na hora        transparente            frames discretos
  │
  └── nunca bloqueia a sessão do Claude Code
```

Um processo por evento — sem daemon, sem IPC, sem processo órfão.

Três detalhes que fazem diferença:

- **A janela nunca pega foco.** Se pegasse, comeria as teclas que você está
  digitando como resposta pro Claude.
- **Só o boneco é clicável.** O resto da janela é atravessado pelo clique
  (extensão X11 SHAPE), e o recorte acompanha o sprite a cada frame.
- **Pixel art não interpola.** Todo movimento é em células inteiras, em passos
  discretos. Rotação suave a 60fps borra o pixel e mata o charme.

O desenho completo, com as alternativas descartadas, está em
[`openspec/changes/add-mascot-overlay/design.md`](openspec/changes/add-mascot-overlay/design.md).

---

## Limitações conhecidas

- X11 apenas. Wayland, macOS e Windows não.
- Um mascote por vez na máquina — várias sessões do Claude Code disputam o
  mesmo canto, e o evento mais recente vence.
- O clique depende da janela do terminal registrada no `SessionStart`. Se ela
  não existir mais, o clique só dispensa o mascote em vez de trocar de janela.

## Créditos

Mascote inspirado no bichinho pixel art do Claude Code. Os frames são
redesenhados na grade, não extraídos de arte de terceiros.
