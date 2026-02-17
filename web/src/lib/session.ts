import type { AppLayoutState, AppSessionState } from "@/lib/types"

export const APP_SESSION_STORAGE_KEY = "artfindr.app.session"
export const APP_SESSION_VERSION = 1
export const APP_LAYOUT_STORAGE_KEY = "artfindr.app.layout"
export const APP_LAYOUT_VERSION = 1

interface StoredLayoutState {
  version: number
  savedAt: number
  layout: AppLayoutState
}

function readStorage<T>(key: string): T | null {
  if (typeof window === "undefined") {
    return null
  }

  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) {
      return null
    }
    return JSON.parse(raw) as T
  } catch {
    return null
  }
}

function writeStorage(key: string, value: unknown): void {
  if (typeof window === "undefined") {
    return
  }

  try {
    window.localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Ignore storage write failures.
  }
}

export function readAppSession(): AppSessionState | null {
  const parsed = readStorage<AppSessionState>(APP_SESSION_STORAGE_KEY)
  if (!parsed || parsed.version !== APP_SESSION_VERSION) {
    return null
  }
  return parsed
}

export function writeAppSession(session: Omit<AppSessionState, "version" | "savedAt">): void {
  writeStorage(APP_SESSION_STORAGE_KEY, {
    version: APP_SESSION_VERSION,
    savedAt: Date.now(),
    ...session,
  } satisfies AppSessionState)
}

export function readLayoutState(defaults: AppLayoutState): AppLayoutState {
  const parsed = readStorage<StoredLayoutState>(APP_LAYOUT_STORAGE_KEY)
  if (!parsed || parsed.version !== APP_LAYOUT_VERSION || !parsed.layout) {
    return defaults
  }
  return parsed.layout
}

export function writeLayoutState(layout: AppLayoutState): void {
  writeStorage(APP_LAYOUT_STORAGE_KEY, {
    version: APP_LAYOUT_VERSION,
    savedAt: Date.now(),
    layout,
  } satisfies StoredLayoutState)
}
