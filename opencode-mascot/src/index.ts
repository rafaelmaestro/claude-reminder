import { spawn } from "node:child_process"
import * as fs from "node:fs"
import * as path from "node:path"
import * as os from "node:os"
import { fileURLToPath } from "node:url"

// ---------------------------------------------------------------------------
// Shared core: no OpenCode SDK imports here, so this module loads under both
// the v1 runtime (opencode 1.x, hooks-object API) and the v2 runtime
// (opencode2 beta, Plugin.define API).
// ---------------------------------------------------------------------------

function getCacheDir(): string {
  const base = process.env.XDG_CACHE_HOME || path.join(os.homedir(), ".cache")
  return path.join(base, "opencode-mascot")
}

function getOverlayDir(): string {
  // src/index.ts -> ../overlay  (local dev)  or  ./overlay when built
  const here = path.dirname(fileURLToPath(import.meta.url))
  const candidates = [
    path.resolve(here, "../overlay"),
    path.resolve(here, "./overlay"),
    path.resolve(here, "../../claude-mascot/overlay"),
    path.resolve(here, "../claude-mascot/overlay"),
  ]
  for (const c of candidates) {
    if (fs.existsSync(path.join(c, "mascot.py"))) return c
  }
  // fallback: try to locate relative to package root (when installed via npm)
  // package root = one level above src
  return path.resolve(here, "../overlay")
}

function hasDisplay(): boolean {
  return Boolean(process.env.DISPLAY || process.env.WAYLAND_DISPLAY)
}

function sanitizeSession(sid: string): string {
  return (sid || "default").replace(/[^A-Za-z0-9_-]/g, "") || "default"
}

function ensureCache(): string {
  const dir = getCacheDir()
  try {
    fs.mkdirSync(dir, { recursive: true })
  } catch {}
  return dir
}

function pidAlive(pidFile: string): boolean {
  try {
    if (!fs.existsSync(pidFile)) return false
    const raw = fs.readFileSync(pidFile, "utf8").trim()
    const pid = Number.parseInt(raw, 10)
    if (!Number.isFinite(pid) || pid <= 0) return false
    process.kill(pid, 0)
    return true
  } catch {
    return false
  }
}

function killOverlay(cacheDir: string): void {
  const pidFile = path.join(cacheDir, "overlay.pid")
  if (pidAlive(pidFile)) {
    try {
      const pid = Number.parseInt(fs.readFileSync(pidFile, "utf8").trim(), 10)
      process.kill(pid, "SIGTERM")
    } catch {}
  }
  try {
    fs.unlinkSync(pidFile)
  } catch {}
}

function dismissIfAsk(cacheDir: string): void {
  const stateFile = path.join(cacheDir, "overlay.state")
  try {
    const cur = fs.readFileSync(stateFile, "utf8").trim()
    if (cur === "ask") killOverlay(cacheDir)
  } catch {}
}

function recordWindow(sessionID: string, cacheDir: string, overlayDir: string): void {
  if (!hasDisplay()) return
  const safe = sanitizeSession(sessionID)
  const dest = path.join(cacheDir, `session-${safe}.win`)
  try {
    const wmPy = path.join(overlayDir, "wm.py")
    // spawn detached python record; ignore output
    const child = spawn("python3", [wmPy, "record", dest], {
      detached: true,
      stdio: "ignore",
    })
    child.unref()
  } catch {}
}

function show(state: "ask" | "done", sessionID: string, cacheDir: string, overlayDir: string): void {
  if (!hasDisplay()) return
  const safe = sanitizeSession(sessionID)
  ensureCache()
  const stateFile = path.join(cacheDir, "overlay.state")
  const tsFile = path.join(cacheDir, "overlay.ts")

  const now = Date.now()
  let last = 0
  let prev = ""
  try {
    last = Number.parseInt(fs.readFileSync(tsFile, "utf8").trim(), 10) || 0
  } catch {}
  try {
    prev = fs.readFileSync(stateFile, "utf8").trim()
  } catch {}

  // dedupe ask -> ask within 1500ms (same as mascot.sh)
  if (state === "ask" && prev === "ask" && now - last < 1500) return

  killOverlay(cacheDir)

  try {
    fs.writeFileSync(stateFile, state, "utf8")
    fs.writeFileSync(tsFile, String(now), "utf8")
  } catch {}

  const mascotPy = path.join(overlayDir, "mascot.py")
  if (!fs.existsSync(mascotPy)) return

  try {
    const child = spawn("python3", [mascotPy, "--state", state, "--session", safe], {
      detached: true,
      stdio: "ignore",
    })
    child.unref()
  } catch {}
}

// ---------------------------------------------------------------------------
// v1 runtime (opencode 1.x): the module exports plugin functions that receive
// a context and return a hooks object. No SDK value import — v1's package has
// no runtime `Plugin` export, so even a static `import { Plugin }` would fail
// at load time. Plain `any` keeps this callable under both SDKs.
// Differences from v2: events carry `properties` (not `data`), there is no
// `permission.asked` event (the ask signal is the `permission.ask` hook), and
// `session.created` carries the session at `properties.info.id`.
// ---------------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const OpencodeMascot = async (_input: any): Promise<any> => {
  const cacheDir = ensureCache()
  const overlayDir = getOverlayDir()

  return {
    // Earliest ask signal on v1: fires when a tool needs permission.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    "permission.ask": async (input: any) => {
      const sid = (input?.sessionID as string) || "default"
      show("ask", sid, cacheDir, overlayDir)
    },
    // Approved and ran (PostToolUse equivalent): dismiss a lingering ask.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    "tool.execute.after": async (_input: any) => {
      dismissIfAsk(cacheDir)
    },
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    event: async ({ event }: any) => {
      const type = event?.type as string | undefined
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const props = (event?.properties ?? {}) as Record<string, any>
      if (type === "session.created") {
        const sid = (props?.info?.id as string) || "default"
        recordWindow(sid, cacheDir, overlayDir)
      } else if (type === "session.idle") {
        const sid = (props?.sessionID as string) || "default"
        show("done", sid, cacheDir, overlayDir)
      } else if (type === "permission.replied") {
        const reply = props?.response as string | undefined
        if (reply === "once" || reply === "always") {
          dismissIfAsk(cacheDir)
        }
      } else if (type === "session.status") {
        const status = (props?.status as { type?: string } | undefined)?.type
        if (status === "busy") {
          dismissIfAsk(cacheDir)
        }
      }
    },
  }
}

// ---------------------------------------------------------------------------
// v2 runtime (opencode2 beta): the module default-exports Plugin.define().
// The SDK is imported lazily: under v1 the package has no runtime `Plugin`
// export, so a static import would break module load there. If the v2 API is
// unavailable we export a stub with just the id, which the v2 loader ignores.
// ---------------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const sdk: any = await import("@opencode-ai/plugin").catch(() => undefined)
const V2Plugin = sdk?.Plugin as
  | { define: (p: unknown) => unknown }
  | undefined

function createV2Setup() {
  return async (ctx: {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    permission?: { hook: (name: string, cb: (e: any) => unknown) => Promise<{ dispose(): Promise<void> }> }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    event: { subscribe: (opts: unknown) => AsyncIterable<{ type: string; data: Record<string, unknown> }> }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    tool?: { hook: (name: string, cb: (e: any) => unknown) => Promise<{ dispose(): Promise<void> }> }
  }) => {
    const cacheDir = ensureCache()
    const overlayDir = getOverlayDir()

    // Permission hook — earliest signal that user attention is needed.
    // Runs before the event is published, so we show immediately and
    // let the event dedupe handle duplicates.
    let permHook: { dispose(): Promise<void> } | undefined
    try {
      permHook = await ctx.permission?.hook("evaluate", async (event) => {
        if (event.effect === "ask") {
          show("ask", event.sessionID, cacheDir, overlayDir)
        }
      })
    } catch {}

    // Event stream — covers session lifecycle and permission replies.
    const controller = new AbortController()
    const eventLoop = (async () => {
      try {
        for await (const event of ctx.event.subscribe({ signal: controller.signal })) {
          const type = (event as unknown as { type: string }).type
          const data = (event as unknown as { data: Record<string, unknown> }).data as Record<string, unknown>

          if (type === "permission.asked") {
            const sid = (data?.sessionID as string) || "default"
            show("ask", sid, cacheDir, overlayDir)
          } else if (type === "permission.replied") {
            // reply once/always -> dismiss; reject keeps ask visible
            const reply = data?.reply as string | undefined
            if (reply === "once" || reply === "always") {
              dismissIfAsk(cacheDir)
            }
          } else if (type === "session.created") {
            const sessionID = (data?.sessionID as string) ?? (data?.id as string) ?? "default"
            recordWindow(sessionID, cacheDir, overlayDir)
          } else if (type === "session.idle") {
            const sid = (data?.sessionID as string) || "default"
            // idle means the turn finished — celebration (Stop equivalent)
            // kill any lingering ask first, then show done
            // show() already kills previous overlay
            show("done", sid, cacheDir, overlayDir)
          } else if (type === "session.status") {
            const status = (data?.status as { type?: string } | undefined)?.type
            // session.status busy -> a tool started running after permission was granted,
            // so dismiss the ask overlay (PostToolUse equivalent)
            if (status === "busy") {
              dismissIfAsk(cacheDir)
            }
            // idle via status is handled by session.idle — ignore to avoid double done
          }
        }
      } catch (err) {
        if ((err as Error)?.name === "AbortError") return
        // silent — plugin must not crash opencode
      }
    })()

    // Also hook tool execution to dismiss ask when a tool runs
    // (PostToolUse equivalent). Some tools don't require permission,
    // so this also covers the "approved and ran" case.
    let toolAfter: { dispose(): Promise<void> } | undefined
    try {
      toolAfter = await ctx.tool?.hook("execute.after", async (_event) => {
        dismissIfAsk(cacheDir)
      })
    } catch {}

    return async () => {
      controller.abort()
      try {
        await eventLoop
      } catch {}
      try {
        await permHook?.dispose()
      } catch {}
      try {
        await toolAfter?.dispose()
      } catch {}
    }
  }
}

const v2Plugin = V2Plugin
  ? V2Plugin.define({
      id: "opencode-mascot",
      setup: createV2Setup(),
    })
  : { id: "opencode-mascot" }

export default v2Plugin
