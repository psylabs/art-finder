import type { AppOptions, HelpMappings, SearchRequest, SearchResponse } from "@/lib/types"

const API_BASE = "/api"

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  })

  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`${response.status} ${response.statusText}: ${detail}`)
  }

  return (await response.json()) as T
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
