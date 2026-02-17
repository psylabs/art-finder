export interface Artwork {
  id: string
  source: string
  title: string
  artist: string
  image_url: string
  filename: string
  date?: string
  medium?: string
  department?: string
  classification?: string
  credit?: string
  culture?: string
  dimensions?: string
  description?: string
  accession_number?: string
  is_downloadable?: boolean
  rights_label?: string
  image_width?: number | null
  image_height?: number | null
  metadata?: Record<string, unknown>
}

export type Orientation = "Any" | "Portrait" | "Landscape"

export interface FilterStatus {
  applied: Record<string, string>
  skipped: Record<string, string>
}

export interface SearchResponse {
  artworks: Artwork[]
  errors: string[]
  warnings: string[]
  filter_status: FilterStatus
  source_counts: Record<string, number>
  seed_used: number | null
  logs: string[]
}

export interface AppOptions {
  source_names: Record<string, string>
  genre_options: string[]
  medium_options: string[]
  fetch_limit_options: number[]
  defaults: {
    sources: string[]
    orientation: Orientation
    limit: number
    use_random_seed: boolean
    random_seed: number
    ssl_bypass: boolean
  }
}

export interface HelpMappings {
  genres: string[]
  media: string[]
  department_map: Record<string, Record<string, string | string[] | null>>
  museum_field_map: Record<string, Record<string, Record<string, unknown>>>
  medium_keyword_map: Record<string, Record<string, string[]>>
}

export interface SearchRequest {
  sources: string[]
  query: string | null
  year_from: number | null
  year_to: number | null
  department: string | null
  medium: string | null
  orientation: Orientation
  limit: number
  use_random_seed: boolean
  random_seed: number | null
  ssl_bypass: boolean
}

export interface AppFormState {
  selectedSources: string[]
  department: string
  medium: string
  query: string
  orientation: Orientation
  fromDate: string
  toDate: string
  limit: number
  sslBypass: boolean
  useRandomSeed: boolean
  randomSeed: string
}

export interface AppLayoutState {
  isSidebarCollapsed: boolean
  showAdvanced: boolean
  showDiagnostics: boolean
}

export interface AppSessionState {
  version: number
  savedAt: number
  form: AppFormState
  result: SearchResponse | null
  currentIndex: number
  debugLogs: string[]
}
