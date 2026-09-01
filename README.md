<h1 align="center">claude-reminder</h1>

<p align="center">
  <b>O mascote do Claude aparece, se mexe e faz barulho quando o Claude precisa de você.</b><br>
  Clique nele e você volta direto pro terminal.
</p>

<p align="center">
  <img src="docs/animacoes.gif" alt="As dez animações do mascote" width="100%">
</p>

<p align="center">
  <sub>X11 · Wayland · Claude Code · OpenCode · zero dependência nova</sub>
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

No `opencode.json` (global `~/.config/opencode/opencode.json` ou do projeto):

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "plugins": ["github:rafaelmaestro/claude-reminder?path=opencode-mascot"]
  // ou local: ["./opencode-mascot"] se você clonou o repo
}
```

Ou copie o plugin para o diretório auto-carregado:

```bash
mkdir -p .opencode/plugins
cp -r opencode-mascot .opencode/plugins/opencode-mascot
```

Reinicie o serviço (`opencode2 service restart`) ou reabra o TUI. Mesma animação e sons, mas com a paleta da marca OpenCode (grafite `#4B4646`/`#211E1E` + `#CFCECD`/`#F1ECEC` em vez do laranja do Claude) e config em `~/.config/opencode-mascot/config.json` — distinto do `claude-mascot`.

### Requisitos

Quase tudo já vem no Ubuntu. Se estiver faltando algo:

```bash
sudo apt install python3-gi gir1.2-webkit2-4.1 pipewire-bin sound-theme-freedesktop
sudo apt install xdotool                        # se você usa X11
sudo apt install gir1.2-gtklayershell-0.1       # se você usa Wayland
```

| precisa de | por quê |
| --- | --- |
| `python3-gi` (GTK 3.0 + WebKit2 4.1) | desenhar e animar o mascote |
| `pw-play` (PipeWire) | tocar o som |
| `sound-theme-freedesktop` | os arquivos de som |
| **no X11:** `xdotool` | posicionar a janela, achar o monitor em foco, devolver o foco ao terminal |
| **no Wayland:** `gtk-layer-shell` | posicionar a janela e mantê-la por cima |
| **no Wayland:** `hyprctl` (só no Hyprland) | achar o monitor em foco e devolver o foco ao terminal |

O plugin escolhe sozinho entre os dois: quem manda é o `WAYLAND_DISPLAY` (com
`GDK_BACKEND` por cima, se você forçou). Num compositor Wayland o `DISPLAY`
continua existindo por causa do Xwayland, então ele não serve para decidir.

**Wayland precisa do `wlr-layer-shell`** — o protocolo que deixa um cliente
escolher o canto da tela onde nasce. Hyprland, Sway, Niri, Wayfire e o KDE
Plasma implementam. O GNOME (Mutter) não implementa: lá o plugin sai calado em
vez de abrir uma janela no meio da tela roubando o seu foco.

Sem nenhum servidor gráfico — sessão por SSH, headless — o plugin simplesmente
não faz nada, sem erro nenhum.

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

- Linux apenas: X11, ou Wayland com `wlr-layer-shell` (não o GNOME). macOS e
  Windows não.
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
