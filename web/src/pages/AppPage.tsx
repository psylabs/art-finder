import { useEffect, useMemo, useState } from "react"
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Bug,
  CalendarRange,
  ChevronLeft,
  ChevronRight,
  Download,
  Filter,
  Info,
  Landmark,
  Loader2,
  Palette,
  Search,
  SlidersHorizontal,
  TriangleAlert,
  X,
} from "lucide-react"

import { getOptions, searchArtworks } from "@/lib/api"
import { readAppSession, readLayoutState, writeAppSession, writeLayoutState } from "@/lib/session"
import type { AppFormState, AppLayoutState, AppOptions, Artwork, Orientation, SearchRequest, SearchResponse } from "@/lib/types"
import { cn } from "@/lib/utils"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Sidebar, SidebarContent, SidebarHeader } from "@/components/ui/sidebar"

const ALL_GENRES_LABEL = "All genres"
const ALL_MEDIA_LABEL = "All media"
const DEFAULT_ERROR = "Unable to load data right now. Check that the API server is running on localhost:8000."
const MUSEUM_LOGOS: Record<string, string> = {
  AIC: "https://upload.wikimedia.org/wikipedia/commons/3/32/Art_Institute_of_Chicago_logo.svg",
  CMA: "https://upload.wikimedia.org/wikipedia/commons/7/74/Logo_Cleveland_Museum_of_Art.svg",
  MOMA: "https://upload.wikimedia.org/wikipedia/commons/2/21/Museum_of_Modern_Art_logo.svg",
}

const MUSEUM_NAMES: Record<string, string> = {
  AIC: "Art Institute of Chicago",
  CMA: "Cleveland Museum of Art",
  MOMA: "Museum of Modern Art",
}

const DEFAULT_LAYOUT_STATE: AppLayoutState = {
  isSidebarCollapsed: false,
  showAdvanced: false,
  showDiagnostics: false,
}

const emptyForm: AppFormState = {
  selectedSources: [],
  department: ALL_GENRES_LABEL,
  medium: ALL_MEDIA_LABEL,
  query: "",
  orientation: "Portrait",
  fromDate: "",
  toDate: "",
  limit: 50,
  sslBypass: false,
  useRandomSeed: false,
  randomSeed: "42",
}

function parseYearFromDate(value: string): number | null {
  const text = value.trim()
  if (!text) {
    return null
  }

  const year = Number.parseInt(text.slice(0, 4), 10)
  if (!Number.isFinite(year)) {
    return null
  }

  return year
}

function cleanFilterDescription(description: string) {
  return description
    .replace(/\bYear Range\b/gi, "Date Range")
    .replace(/\s*\((?:client-side|mapped)\)\s*/g, " ")
    .replace(/\s{2,}/g, " ")
    .trim()
}

function formatField(value: unknown) {
  if (!value) {
    return ""
  }
  if (Array.isArray(value)) {
    return value.filter(Boolean).join(", ")
  }
  return String(value)
}

function createDefaultForm(options: AppOptions): AppFormState {
  return {
    selectedSources: options.defaults.sources,
    department: ALL_GENRES_LABEL,
    medium: ALL_MEDIA_LABEL,
    query: "",
    orientation: options.defaults.orientation,
    fromDate: "",
    toDate: "",
    limit: options.defaults.limit,
    sslBypass: options.defaults.ssl_bypass,
    useRandomSeed: options.defaults.use_random_seed,
    randomSeed: String(options.defaults.random_seed),
  }
}

function normalizeOrientation(value: string | undefined, fallback: Orientation): Orientation {
  if (value === "Any" || value === "Portrait" || value === "Landscape") {
    return value
  }
  return fallback
}

function normalizeForm(form: AppFormState, options: AppOptions): AppFormState {
  const availableSources = new Set(Object.keys(options.source_names))
  const normalizedSources = form.selectedSources.filter((code) => availableSources.has(code))

  const selectedSources = normalizedSources.length > 0 ? normalizedSources : options.defaults.sources
  const department = options.genre_options.includes(form.department) ? form.department : ALL_GENRES_LABEL
  const medium = options.medium_options.includes(form.medium) ? form.medium : ALL_MEDIA_LABEL

  const limit = options.fetch_limit_options.includes(form.limit)
    ? form.limit
    : options.fetch_limit_options[0] ?? options.defaults.limit

  return {
    ...form,
    selectedSources,
    department,
    medium,
    orientation: normalizeOrientation(form.orientation, options.defaults.orientation),
    limit,
  }
}

function clampIndex(currentIndex: number, result: SearchResponse | null): number {
  if (!result || result.artworks.length === 0) {
    return 0
  }

  return Math.min(Math.max(currentIndex, 0), result.artworks.length)
}

function DateField({
  id,
  label,
  value,
  onChange,
  onClear,
}: {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  onClear: () => void
}) {
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>{label}</Label>
      <div className="relative">
        <Input
          id={id}
          type="date"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="date-input pr-16"
        />
        {value ? (
          <button
            type="button"
            aria-label={`Clear ${label.toLowerCase()}`}
            className="absolute right-8 top-2 rounded-sm p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            onClick={onClear}
          >
            <X className="h-3 w-3" aria-hidden="true" />
          </button>
        ) : null}
        <CalendarRange className="pointer-events-none absolute right-2 top-2.5 h-4 w-4 text-muted-foreground" aria-hidden="true" />
      </div>
    </div>
  )
}

export function AppPage() {
  const [options, setOptions] = useState<AppOptions | null>(null)
  const [form, setForm] = useState<AppFormState>(emptyForm)
  const [result, setResult] = useState<SearchResponse | null>(null)
  const [debugLogs, setDebugLogs] = useState<string[]>([])
  const [isBootLoading, setIsBootLoading] = useState(true)
  const [isSearching, setIsSearching] = useState(false)
  const [isHydrated, setIsHydrated] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [noticeMessage, setNoticeMessage] = useState<string | null>(null)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [showSummaryDetails, setShowSummaryDetails] = useState(false)
  const [layoutState, setLayoutState] = useState<AppLayoutState>(() => readLayoutState(DEFAULT_LAYOUT_STATE))

  useEffect(() => {
    let cancelled = false

    getOptions()
      .then((payload) => {
        if (cancelled) {
          return
        }

        const persisted = readAppSession()
        const nextForm = persisted ? normalizeForm(persisted.form, payload) : createDefaultForm(payload)
        const nextResult = persisted?.result ?? null
        const nextDebugLogs = persisted?.debugLogs ?? []
        const nextIndex = clampIndex(persisted?.currentIndex ?? 0, nextResult)

        setOptions(payload)
        setForm(nextForm)
        setResult(nextResult)
        setDebugLogs(nextDebugLogs)
        setCurrentIndex(nextIndex)
        setLayoutState(readLayoutState(DEFAULT_LAYOUT_STATE))
        setIsHydrated(true)
      })
      .catch((error) => {
        if (!cancelled) {
          setErrorMessage((error as Error).message || DEFAULT_ERROR)
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsBootLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!isHydrated) {
      return
    }

    writeAppSession({
      form,
      result,
      currentIndex,
      debugLogs,
    })
  }, [isHydrated, form, result, currentIndex, debugLogs])

  useEffect(() => {
    writeLayoutState(layoutState)
  }, [layoutState])

  const artworks = result?.artworks ?? []
  const hasCompleted = result !== null && artworks.length > 0 && currentIndex >= artworks.length
  const currentArtwork = !hasCompleted ? artworks[currentIndex] : undefined

  const sourceEntries = useMemo(() => Object.entries(options?.source_names ?? {}), [options?.source_names])

  const appliedFilters = useMemo(() => {
    if (!result || !options) {
      return []
    }

    const descriptions = new Map<string, Set<string>>()
    for (const [name, description] of Object.entries(result.filter_status.applied)) {
      if (name.includes("random_seed")) {
        continue
      }
      const clean = cleanFilterDescription(description)
      if (!clean) {
        continue
      }
      if (!descriptions.has(clean)) {
        descriptions.set(clean, new Set<string>())
      }
      const source = name.includes(".") ? name.split(".")[0].toUpperCase() : ""
      if (source) {
        descriptions.get(clean)?.add(options.source_names[source] ?? MUSEUM_NAMES[source] ?? source)
      }
    }

    return Array.from(descriptions.entries()).map(([description, sources]) => ({
      description,
      sourceSuffix: sources.size > 1 ? ` (${Array.from(sources).sort().join(", ")})` : "",
    }))
  }, [options, result])

  const sourceCounts = useMemo(() => {
    if (!result || !options) {
      return []
    }

    return Object.entries(result.source_counts).map(([source, count]) => ({
      source,
      label: options.source_names[source] ?? source,
      count,
    }))
  }, [options, result])

  async function handleLoad() {
    if (!options) {
      return
    }

    if (form.selectedSources.length === 0) {
      setErrorMessage("Select at least one museum source.")
      return
    }

    const payload: SearchRequest = {
      sources: form.selectedSources,
      query: form.query.trim() || null,
      year_from: parseYearFromDate(form.fromDate),
      year_to: parseYearFromDate(form.toDate),
      department: form.department === ALL_GENRES_LABEL ? null : form.department,
      medium: form.medium === ALL_MEDIA_LABEL ? null : form.medium,
      orientation: form.orientation,
      limit: form.limit,
      use_random_seed: false,
      random_seed: null,
      ssl_bypass: form.sslBypass,
    }

    try {
      setIsSearching(true)
      setNoticeMessage(null)
      setErrorMessage(null)
      setShowSummaryDetails(false)
      const nextResult = await searchArtworks(payload)
      setResult(nextResult)
      setDebugLogs(nextResult.logs ?? [])
      setCurrentIndex(0)
    } catch (error) {
      setErrorMessage((error as Error).message || DEFAULT_ERROR)
    } finally {
      setIsSearching(false)
    }
  }

  function toggleSource(source: string) {
    setForm((prev) => {
      const exists = prev.selectedSources.includes(source)
      if (exists && prev.selectedSources.length === 1) {
        setNoticeMessage("At least one museum must be selected.")
        return prev
      }

      if (exists) {
        return {
          ...prev,
          selectedSources: prev.selectedSources.filter((code) => code !== source),
          department: ALL_GENRES_LABEL,
        }
      }

      return { ...prev, selectedSources: [...prev.selectedSources, source] }
    })
  }

  function updateArtworkIndex(next: number) {
    setCurrentIndex(Math.max(0, next))
  }

  return (
    <div className={cn("grid items-start gap-4", layoutState.isSidebarCollapsed ? "xl:grid-cols-[72px_minmax(0,1fr)]" : "xl:grid-cols-[320px_minmax(0,1fr)]")}>
      <Sidebar className={cn("overflow-hidden transition-[width] duration-300 xl:sticky xl:top-16", layoutState.isSidebarCollapsed ? "w-[72px]" : "w-full")}>
        <SidebarHeader>
          <div className={cn("flex items-center gap-2", layoutState.isSidebarCollapsed && "justify-center")}>
            <Filter className="h-4 w-4" aria-hidden="true" />
            {!layoutState.isSidebarCollapsed ? <p className="font-medium">Filters</p> : null}
          </div>
          <Button
            variant="ghost"
            size="icon"
            aria-label={layoutState.isSidebarCollapsed ? "Expand filters" : "Collapse filters"}
            onClick={() => setLayoutState((prev) => ({ ...prev, isSidebarCollapsed: !prev.isSidebarCollapsed }))}
            className="hidden xl:inline-flex"
          >
            {layoutState.isSidebarCollapsed ? <ChevronRight className="h-4 w-4" aria-hidden="true" /> : <ChevronLeft className="h-4 w-4" aria-hidden="true" />}
          </Button>
        </SidebarHeader>

        <SidebarContent>
          {layoutState.isSidebarCollapsed ? (
            <div className="flex flex-col items-center gap-2">
              <Button
                size="icon"
                variant="outline"
                aria-label="Expand filters"
                onClick={() => setLayoutState((prev) => ({ ...prev, isSidebarCollapsed: false }))}
              >
                <ChevronRight className="h-4 w-4" aria-hidden="true" />
              </Button>
            </div>
          ) : (
            <>
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Landmark className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
              <Label>Museum</Label>
            </div>
            <details className="rounded-md border">
              <summary className="cursor-pointer list-none px-3 py-2 text-sm font-medium text-muted-foreground">
                {form.selectedSources.length} selected
              </summary>
              <div className="grid gap-2 border-t p-2">
                {sourceEntries.map(([code, label]) => (
                  <label key={code} className="flex cursor-pointer items-center justify-between rounded-md border px-3 py-2 text-sm">
                    <span>{label}</span>
                    <Checkbox aria-label={label} checked={form.selectedSources.includes(code)} onChange={() => toggleSource(code)} />
                  </label>
                ))}
              </div>
            </details>
          </div>

              <div className="grid gap-3">
                <div className="flex items-center gap-2">
                  <Palette className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                  <Label htmlFor="department" title="Genre maps your selection to museum-specific department fields.">Genre</Label>
                </div>
                <Select
                  id="department"
                  value={form.department}
                  onChange={(event) => setForm((prev) => ({ ...prev, department: event.target.value }))}
                >
                  {(options?.genre_options ?? []).map((genre) => (
                    <option key={genre} value={genre}>
                      {genre}
                    </option>
                  ))}
                </Select>
              </div>

              <div className="grid gap-3">
                <div className="flex items-center gap-2">
                  <Palette className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                  <Label htmlFor="medium" title="Medium applies keyword matching across each museum’s own metadata fields.">Medium</Label>
                </div>
                <Select id="medium" value={form.medium} onChange={(event) => setForm((prev) => ({ ...prev, medium: event.target.value }))}>
                  {(options?.medium_options ?? []).map((medium) => (
                    <option key={medium} value={medium}>
                      {medium}
                    </option>
                  ))}
                </Select>
              </div>

              <div className="grid gap-3">
                <div className="flex items-center gap-2">
                  <Search className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                  <Label htmlFor="query" title="Search term matches title, artist, and museum metadata text.">Search Term</Label>
                </div>
                <Input id="query" value={form.query} onChange={(event) => setForm((prev) => ({ ...prev, query: event.target.value }))} />
              </div>

              <div className="grid gap-3">
                <div className="flex items-center gap-2">
                  <SlidersHorizontal className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                  <Label htmlFor="orientation">Orientation</Label>
                </div>
                <Select
                  id="orientation"
                  value={form.orientation}
                  onChange={(event) => setForm((prev) => ({ ...prev, orientation: event.target.value as Orientation }))}
                >
                  <option value="Any">Any</option>
                  <option value="Portrait">Portrait</option>
                  <option value="Landscape">Landscape</option>
                </Select>
              </div>

              <Button data-testid="load-artworks-cta" onClick={handleLoad} className="w-full" disabled={isSearching || isBootLoading}>
                {isSearching ? <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" /> : null}
                {isSearching ? "Loading Artworks..." : "Load Artworks"}
              </Button>

              <p className="text-xs text-muted-foreground">
                Will fetch up to {form.limit} artworks per museum across {form.selectedSources.length || 0} museums.
              </p>

              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setLayoutState((prev) => ({ ...prev, showAdvanced: !prev.showAdvanced }))}
                >
                  <SlidersHorizontal className="h-3 w-3" aria-hidden="true" />
                  Advanced
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setLayoutState((prev) => ({ ...prev, showDiagnostics: !prev.showDiagnostics }))}
                >
                  <Bug className="h-3 w-3" aria-hidden="true" />
                  Diagnostics
                </Button>
              </div>

              {layoutState.showAdvanced ? (
                <div className="space-y-3 rounded-md border p-3">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <CalendarRange className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                      <p className="text-sm font-medium">Date Range</p>
                    </div>
                    <div className="grid grid-cols-1 gap-3">
                      <DateField
                        id="date-from"
                        label="From date"
                        value={form.fromDate}
                        onChange={(value) => setForm((prev) => ({ ...prev, fromDate: value }))}
                        onClear={() => setForm((prev) => ({ ...prev, fromDate: "" }))}
                      />
                      <DateField
                        id="date-to"
                        label="To date"
                        value={form.toDate}
                        onChange={(value) => setForm((prev) => ({ ...prev, toDate: value }))}
                        onClear={() => setForm((prev) => ({ ...prev, toDate: "" }))}
                      />
                    </div>
                  </div>

                  <Separator />

                  <div className="grid gap-3">
                    <Label htmlFor="limit">Fetch Limit</Label>
                    <Select
                      id="limit"
                      value={String(form.limit)}
                      onChange={(event) => setForm((prev) => ({ ...prev, limit: Number.parseInt(event.target.value, 10) || 50 }))}
                    >
                      {(options?.fetch_limit_options ?? [50, 100, 200]).map((limit) => (
                        <option key={limit} value={String(limit)}>
                          {limit}
                        </option>
                      ))}
                    </Select>
                  </div>

                  <label className="flex items-center gap-3 text-sm">
                    <Checkbox checked={form.sslBypass} onChange={(event) => setForm((prev) => ({ ...prev, sslBypass: event.target.checked }))} />
                    Bypass SSL verification
                  </label>
                </div>
              ) : null}

              {layoutState.showDiagnostics ? (
                <details className="rounded-md border p-3 text-xs text-muted-foreground" open>
                  <summary className="cursor-pointer font-medium text-foreground">Debug Logs</summary>
                  <div className="mt-2 space-y-2">
                    <Button variant="outline" size="sm" onClick={() => setDebugLogs([])}>
                      Clear Logs
                    </Button>
                    <pre className="max-h-48 overflow-auto whitespace-pre-wrap">{debugLogs.join("\n") || "No logs yet."}</pre>
                  </div>
                </details>
              ) : null}
            </>
          )}
        </SidebarContent>
      </Sidebar>

      <div className="space-y-4">
        {errorMessage ? (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" aria-hidden="true" />
            <AlertTitle>Request failed</AlertTitle>
            <AlertDescription>{errorMessage}</AlertDescription>
          </Alert>
        ) : null}

        {noticeMessage ? (
          <Alert>
            <Info className="h-4 w-4" aria-hidden="true" />
            <AlertTitle>Notice</AlertTitle>
            <AlertDescription>{noticeMessage}</AlertDescription>
          </Alert>
        ) : null}

        {result ? (
          <Card>
            <CardContent className="pt-6">
              <div className="w-full">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <p className="text-sm font-medium">Search Summary:</p>

                    {sourceCounts.length > 0
                      ? sourceCounts.map((entry) => (
                          <Badge key={entry.source} variant="secondary" title={`${entry.count} result${entry.count === 1 ? "" : "s"} from ${entry.label}`}>
                            {entry.label}
                          </Badge>
                        ))
                      : null}

                    {result.warnings.length > 0 ? (
                      <Badge variant="outline" className="gap-1">
                        <TriangleAlert className="h-3 w-3" aria-hidden="true" />
                        {result.warnings.length} warning{result.warnings.length > 1 ? "s" : ""}
                      </Badge>
                    ) : null}

                    {result.errors.length > 0 ? (
                      <Badge variant="destructive" className="gap-1">
                        <AlertCircle className="h-3 w-3" aria-hidden="true" />
                        {result.errors.length} error{result.errors.length > 1 ? "s" : ""}
                      </Badge>
                    ) : null}
                  </div>

                  <Button
                    variant="outline"
                    size="sm"
                    type="button"
                    aria-expanded={showSummaryDetails}
                    onClick={() => setShowSummaryDetails((current) => !current)}
                  >
                    Details
                  </Button>
                </div>

                {showSummaryDetails ? (
                  <div className="mt-3 space-y-3 rounded-md border bg-popover p-3 text-sm text-popover-foreground">
                    {appliedFilters.length > 0 ? (
                      <div>
                        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Applied filters</p>
                        <ul className="list-disc space-y-1 pl-5 text-sm">
                          {appliedFilters.map((item) => (
                            <li key={item.description} className="break-words">
                              {item.description + item.sourceSuffix}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}

                    {Object.values(result.filter_status.skipped).length > 0 ? (
                      <div>
                        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Skipped filters</p>
                        <ul className="list-disc space-y-1 pl-5 text-sm">
                          {Object.values(result.filter_status.skipped).map((value) => (
                            <li key={value} className="break-words">
                              {value}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </CardContent>
          </Card>
        ) : null}

        {currentArtwork ? (
          <ArtworkPanel
            artwork={currentArtwork}
            currentIndex={currentIndex}
            totalCount={artworks.length}
            sslBypass={form.sslBypass}
            onBack={() => updateArtworkIndex(currentIndex - 1)}
            onNext={() => updateArtworkIndex(currentIndex + 1)}
          />
        ) : null}

        {result && artworks.length === 0 && !isSearching ? (
          <Card>
            <CardHeader>
              <CardTitle>No Results</CardTitle>
              <CardDescription>Try broadening date range, changing genre/medium, or enabling additional sources.</CardDescription>
            </CardHeader>
          </Card>
        ) : null}

        {hasCompleted ? (
          <Card>
            <CardHeader>
              <CardTitle>You reviewed every artwork.</CardTitle>
              <CardDescription>Start over to browse this result set again.</CardDescription>
            </CardHeader>
            <CardContent>
              <Button onClick={() => setCurrentIndex(0)}>Start Over</Button>
            </CardContent>
          </Card>
        ) : null}

        {!result ? (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Ready to Load</CardTitle>
              <CardDescription>Choose filters and click Load Artworks to begin browsing.</CardDescription>
            </CardHeader>
          </Card>
        ) : null}
      </div>
    </div>
  )
}

function ArtworkPanel({
  artwork,
  currentIndex,
  totalCount,
  sslBypass,
  onBack,
  onNext,
}: {
  artwork: Artwork
  currentIndex: number
  totalCount: number
  sslBypass: boolean
  onBack: () => void
  onNext: () => void
}) {
  const [imageStatus, setImageStatus] = useState<"loading" | "loaded" | "error">("loading")
  const [imageAttempt, setImageAttempt] = useState(0)
  const [downloadPending, setDownloadPending] = useState(false)
  const [downloadError, setDownloadError] = useState<string | null>(null)

  useEffect(() => {
    setImageStatus("loading")
    setImageAttempt(0)
    setDownloadPending(false)
    setDownloadError(null)
  }, [artwork.id])

  const title = formatField(artwork.title) || "Untitled"
  const sourceCode = String(artwork.source || "").toUpperCase()
  const sourceName = MUSEUM_NAMES[sourceCode] ?? sourceCode
  const sourceLogo = MUSEUM_LOGOS[sourceCode]
  const downloadUrl = `/api/download?${new URLSearchParams({
    url: artwork.image_url,
    filename: artwork.filename || "artwork.jpg",
    ssl_bypass: String(sslBypass),
  }).toString()}`

  const metadataItems = [
    ["Artist", artwork.artist],
    ["Date", artwork.date],
    ["Type", artwork.classification],
    ["Department", artwork.department],
    ["Medium", artwork.medium],
    ["Credit", artwork.credit],
    ["Culture", artwork.culture],
    ["Rights", artwork.rights_label],
  ].filter(([, value]) => Boolean(formatField(value)))

  async function handleDownload() {
    if (artwork.is_downloadable === false || downloadPending) {
      return
    }

    try {
      setDownloadPending(true)
      setDownloadError(null)
      const response = await fetch(downloadUrl)
      if (!response.ok) {
        throw new Error(`Download failed: ${response.status} ${response.statusText}`)
      }

      const blob = await response.blob()
      const objectUrl = URL.createObjectURL(blob)
      const anchor = document.createElement("a")
      anchor.href = objectUrl
      anchor.download = artwork.filename || "artwork.jpg"
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(objectUrl)

      onNext()
    } catch (error) {
      setDownloadError((error as Error).message || "Download failed")
    } finally {
      setDownloadPending(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start gap-3">
          <CardTitle className="min-w-0 flex-1 break-words">{title}</CardTitle>
          {sourceLogo ? (
            <div className="flex shrink-0 items-center gap-2 rounded-md border px-2 py-1">
              <img src={sourceLogo} alt={sourceName} className="h-4 w-auto object-contain" />
              <span className="text-xs text-muted-foreground">{sourceName}</span>
            </div>
          ) : sourceName ? (
            <Badge variant="outline" className="shrink-0">
              {sourceName}
            </Badge>
          ) : null}
        </div>
      </CardHeader>

      <CardContent className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_330px]">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2" data-testid="artwork-actions">
            <p className="text-xs text-muted-foreground">
              {currentIndex + 1} of {totalCount}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={onBack} disabled={currentIndex === 0}>
                <ArrowLeft className="h-4 w-4" aria-hidden="true" />
                Back
              </Button>

              <Button variant="outline" onClick={onNext}>
                Skip
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Button>

              <Button onClick={handleDownload} disabled={artwork.is_downloadable === false || downloadPending}>
                {downloadPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Download className="h-4 w-4" aria-hidden="true" />}
                {downloadPending ? "Downloading..." : "Download"}
              </Button>
            </div>
          </div>

          <div className="relative h-[min(56vh,560px)] min-h-[300px] overflow-hidden rounded-lg border bg-muted/10">
            {imageStatus === "loading" ? <div className="absolute inset-0 animate-pulse bg-muted/30" aria-hidden="true" /> : null}

            <img
              key={`${artwork.id}-${imageAttempt}`}
              src={artwork.image_url}
              alt={title}
              className={cn("h-full w-full object-contain transition-opacity", imageStatus === "loading" ? "opacity-0" : "opacity-100")}
              loading="lazy"
              onLoad={() => setImageStatus("loaded")}
              onError={() => setImageStatus("error")}
            />

            {imageStatus === "error" ? (
              <div className="absolute inset-x-2 top-2">
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" aria-hidden="true" />
                  <AlertTitle>Image failed to load</AlertTitle>
                  <AlertDescription>
                    <div className="space-y-2">
                      <p>Retry the image request.</p>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setImageStatus("loading")
                          setImageAttempt((value) => value + 1)
                        }}
                      >
                        Retry image
                      </Button>
                    </div>
                  </AlertDescription>
                </Alert>
              </div>
            ) : null}
          </div>

          {downloadError ? (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" aria-hidden="true" />
              <AlertTitle>Download failed</AlertTitle>
              <AlertDescription>{downloadError}</AlertDescription>
            </Alert>
          ) : null}
        </div>

        <aside className="space-y-3 rounded-lg border p-3">
          <dl className="grid gap-2 text-sm">
            {metadataItems.map(([label, value]) => (
              <div key={label} className="grid grid-cols-[auto_1fr] gap-2">
                <dt className="font-semibold">{label}:</dt>
                <dd className="text-muted-foreground">{formatField(value)}</dd>
              </div>
            ))}
          </dl>

          {formatField(artwork.metadata?.tombstone) ? (
            <details className="rounded-md border p-2 text-sm">
              <summary className="cursor-pointer font-medium">Tombstone</summary>
              <p className="mt-2 text-muted-foreground">{formatField(artwork.metadata?.tombstone)}</p>
            </details>
          ) : null}

          {formatField(artwork.description) ? (
            <details className="rounded-md border p-2 text-sm">
              <summary className="cursor-pointer font-medium">Description</summary>
              <p className="mt-2 text-muted-foreground">{formatField(artwork.description)}</p>
            </details>
          ) : null}

          {formatField(artwork.metadata?.did_you_know) ? (
            <details className="rounded-md border p-2 text-sm">
              <summary className="cursor-pointer font-medium">Did you know</summary>
              <p className="mt-2 text-muted-foreground">{formatField(artwork.metadata?.did_you_know)}</p>
            </details>
          ) : null}
        </aside>
      </CardContent>
    </Card>
  )
}
