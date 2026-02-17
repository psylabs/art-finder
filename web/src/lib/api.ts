import type { AppOptions, HelpMappings, SearchRequest, SearchResponse } from "@/lib/types"

const API_BASE = "/api"
const RETRYABLE_STATUSES = new Set([502, 503, 504])
const MAX_ATTEMPTS = 3

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  let lastError: Error | null = null

  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
    try {
      const response = await fetch(`${API_BASE}${path}`, {
        ...init,
        headers: {
          "Content-Type": "application/json",
          ...(init?.headers ?? {}),
        },
      })

      if (!response.ok) {
        const detail = await response.text()
        const error = new Error(`${response.status} ${response.statusText}: ${detail}`)
        if (!RETRYABLE_STATUSES.has(response.status) || attempt === MAX_ATTEMPTS) {
          throw error
        }
        lastError = error
        await sleep(200 * attempt)
        continue
      }

      return (await response.json()) as T
    } catch (error) {
      const nextError = error as Error
      if (attempt === MAX_ATTEMPTS) {
        throw nextError
      }
      lastError = nextError
      await sleep(200 * attempt)
    }
  }

  throw lastError ?? new Error("Request failed")
}

export function getOptions() {
  return fetchJson<AppOptions>("/options")
}

export function searchArtworks(payload: SearchRequest) {
  return fetchJson<SearchResponse>("/search", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export function getHelpMappings() {
  return fetchJson<HelpMappings>("/help/mappings")
}

export function buildDownloadUrl(url: string, filename: string, sslBypass: boolean) {
  const params = new URLSearchParams({
    url,
    filename,
    ssl_bypass: String(sslBypass),
  })
  return `${API_BASE}/download?${params.toString()}`
}
