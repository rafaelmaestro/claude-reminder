<h1 align="center">claude-reminder</h1>

<p align="center">
  <b>O mascote do Claude aparece, se mexe e faz barulho quando o Claude precisa de você.</b><br>
  Clique nele e você volta direto pro terminal.
</p>

<p align="center">
  <img src="docs/animacoes.gif" alt="As dez animações do mascote" width="100%">
</p>

<p align="center">
  <sub>X11 · Wayland · Claude Code · OpenCode · zero dependência nova<br><sup>Windows: experimental, ainda não validado por ninguém — veja abaixo</sup></sub>
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

---

## Instalação

### Claude Code

```
/plugin marketplace add rafaelmaestro/claude-reminder
/plugin install claude-mascot@claude-reminder
```

Reinicie a sessão. Pronto — não tem passo dois.

### OpenCode

No `opencode.json` (global `~/.config/opencode/opencode.json` ou do projeto).
O mesmo pacote serve os dois runtimes — o módulo exporta a função de plugin
da v1 (`OpencodeMascot`, objeto de hooks) e o `Plugin.define` da v2 (default):

```jsonc
// opencode2 — chave `plugins` (plural)
{
  "$schema": "https://opencode.ai/config.json",
  "plugins": ["github:rafaelmaestro/claude-reminder"]
}
// opencode v1 — chave `plugin` (singular)
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": ["github:rafaelmaestro/claude-reminder"]
}
```

Detalhes que quebram a instalação silenciosamente (o mascote nunca aparece e
o TUI não mostra erro — só o log do serviço):

- **Sem `?path=`**: o instalador do opencode2 baixa via npm, que sempre lê o
  `package.json` da **raiz** do repo e ignora `?path=...` (isso é sintaxe do
  Bun, não do npm). A raiz do repo tem um `package.json` (`opencode-mascot`)
  que reexporta `./opencode-mascot/src/index.ts`. Usar
  `github:...?path=opencode-mascot` falha com `NpmInstallFailedError`.
- **Uma chave por runtime**: `plugin` (v1) e `plugins` (v2) com a mesma
  entrada fazem o opencode2 tentar instalar duas vezes. Use só a chave do
  seu runtime.
- **Eventos diferentes**: na v1 os eventos vêm em `properties` (sem
  `permission.asked` — o aviso de permissão chega pelo hook `permission.ask`)
  e a sessão criada traz o id em `properties.info.id`; na v2 vêm em `data`.
  O plugin trata os dois formatos.

Ou copie o plugin para o diretório auto-carregado:

```bash
mkdir -p .opencode/plugins
cp -r opencode-mascot .opencode/plugins/opencode-mascot
```

Reinicie o serviço (`opencode2 service restart`) ou reabra o TUI. Mesma animação e sons, mas com a paleta da marca OpenCode (grafite `#4B4646`/`#211E1E` + `#CFCECD`/`#F1ECEC` em vez do laranja do Claude) e config em `~/.config/opencode-mascot/config.json` — distinto do `claude-mascot`.

### Requisitos

Quase tudo já vem no Ubuntu. Se estiver faltando algo:

```bash
sudo apt install python3-gi pipewire-bin sound-theme-freedesktop
sudo apt install xdotool                        # se você usa X11
sudo apt install gir1.2-gtklayershell-0.1       # se você usa Wayland
```

| precisa de | por quê |
| --- | --- |
| `python3-gi` (GTK 3.0 + cairo) | desenhar e animar o mascote |
| `pw-play` (PipeWire) | tocar o som |
| `sound-theme-freedesktop` | os arquivos de som |
| **no X11:** `xdotool` | posicionar a janela, achar o monitor em foco, devolver o foco ao terminal |
| **no Wayland:** `gtk-layer-shell` | posicionar a janela e mantê-la por cima |
| **no Wayland:** `hyprctl` (só no Hyprland) | achar o monitor em foco e devolver o foco ao terminal |
| **no Windows:** `pycairo` | desenhar (a janela usa `user32` via `ctypes`, que já vem no Python) |

O plugin escolhe sozinho entre os dois: quem manda é o `WAYLAND_DISPLAY` (com
`GDK_BACKEND` por cima, se você forçou). Num compositor Wayland o `DISPLAY`
continua existindo por causa do Xwayland, então ele não serve para decidir.

**Wayland precisa do `wlr-layer-shell`** — o protocolo que deixa um cliente
escolher o canto da tela onde nasce. Hyprland, Sway, Niri, Wayfire e o KDE
Plasma implementam. O GNOME (Mutter) não implementa: lá o plugin sai calado em
vez de abrir uma janela no meio da tela roubando o seu foco.

Sem nenhum servidor gráfico — sessão por SSH, headless — o plugin simplesmente
não faz nada, sem erro nenhum.

### Windows: experimental

Existe um backend de janela para Windows (`overlay/mascot_win32.py`): janela em
camadas via `user32` com `ctypes`, alimentada pelo mesmo cairo que desenha no
Linux. Ele compartilha `painter.py` e `frames.py` com o backend GTK, então a
arte e a coreografia são as mesmas.

**Ninguém validou isso numa máquina Windows de verdade ainda.** O que a CI
prova em cada push, num runner `windows-latest`:

- as 19 regras do despachante de hooks passam
- o mascote é desenhado (os PNGs saem como artefato do build)
- a janela em camadas abre e a tela é capturada

O que a CI **não** prova, e é justamente o que decide se presta:

- se o clique atravessa fora do sprite (`WM_NCHITTEST` devolvendo `HTTRANSPARENT`)
- se a janela rouba o foco enquanto você digita (`WS_EX_NOACTIVATE`)
- se o `hooks.json` funciona: ele chama `python3`, que no Windows normalmente se
  chama `python` — isso quase certamente ainda precisa de ajuste
- se o som sai (`winsound` só toca WAV; os `.oga` do freedesktop não existem lá)

Se você usa Windows e quer ajudar, tem uma issue aberta pedindo exatamente isso.

---

## O que dispara o quê

| hook do Claude Code | o que acontece |
| --- | --- |
| `Notification` | pedido de permissão → mascote entra e insiste |
| `PreToolUse` · `AskUserQuestion` | Claude fez uma pergunta → mesma coisa |
| `PostToolUse` | você aprovou e a ferramenta rodou → mascote sai |
| `Stop` | Claude terminou → comemoração e tchauzinho |
| `SessionStart` | grava qual janela é o seu terminal (pro clique funcionar) |

| evento do OpenCode | o que acontece |
| --- | --- |
| `permission.asked` / `permission hook ask` | precisa de permissão → mascote **grafite** entra e insiste |
| `permission.replied` / `session.status busy` / `tool.execute.after` | aprovou e rodou → mascote sai |
| `session.idle` | terminou → comemoração grafite e tchauzinho |
| `session.created` | grava janela do terminal |

Nenhum hook lê, altera ou atrasa decisão de ferramenta. Todos saem
imediatamente com código 0 e deixam a animação rodando em outro processo.

---

## Configuração

Opcional. Copie `claude-mascot/config.example.json` para
`~/.config/claude-mascot/config.json` (ou `opencode-mascot/config.example.json` para `~/.config/opencode-mascot/config.json` no OpenCode):

| chave | padrão | o que faz |
| --- | --- | --- |
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

## Limitações conhecidas

- Linux (X11, ou Wayland com `wlr-layer-shell` — não o GNOME) é o único
  ambiente validado. Windows é experimental e não foi testado por ninguém;
  macOS não existe.
- **No Wayland fora do Hyprland**, o mascote aparece e anima, mas o monitor
  vira palpite do compositor (normalmente o que está em foco, sem garantia) e o
  clique só dispensa o mascote em vez de trazer o terminal de volta. Não existe
  protocolo padrão para perguntar quem está em foco nem para ativar uma janela;
  cada compositor resolve com o próprio IPC. O do Hyprland (`hyprctl`) está em
  `overlay/wm.py` e serve de molde para os outros.
- Um mascote por vez na máquina — várias sessões do Claude Code disputam o
  mesmo canto, e o evento mais recente vence.
- O clique depende da janela do terminal registrada no `SessionStart`. Se ela
  não existir mais, o clique só dispensa o mascote em vez de trocar de janela.

## Créditos

Mascote inspirado no bichinho pixel art do Claude Code. Os frames são
redesenhados na grade, não extraídos de arte de terceiros.
