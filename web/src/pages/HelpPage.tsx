import { useEffect, useMemo, useState } from "react"
import { FileSearch, Info, Loader2, Tags } from "lucide-react"

import { getHelpMappings } from "@/lib/api"
import type { HelpMappings } from "@/lib/types"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Select } from "@/components/ui/select"

function asList(value: string | string[] | null | undefined) {
  if (!value) {
    return []
  }
  return Array.isArray(value) ? value : [value]
}

const MUSEUM_NAMES: Record<string, string> = {
  CMA: "Cleveland Museum of Art",
  AIC: "Art Institute of Chicago",
  MOMA: "Museum of Modern Art",
}

export function HelpPage() {
  const [mappings, setMappings] = useState<HelpMappings | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedGenre, setSelectedGenre] = useState<string>("")
  const [selectedMedium, setSelectedMedium] = useState<string>("")

  useEffect(() => {
    let cancelled = false

    getHelpMappings()
      .then((payload) => {
        if (cancelled) {
          return
        }
        setMappings(payload)
        setSelectedGenre(payload.genres[0] ?? "")
        setSelectedMedium(payload.media[0] ?? "")
      })
      .catch((fetchError) => {
        if (!cancelled) {
          setError((fetchError as Error).message)
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  const selectedGenreMap = useMemo(() => {
    if (!mappings || !selectedGenre) {
      return null
    }
    return mappings.department_map[selectedGenre] ?? null
  }, [mappings, selectedGenre])

  const selectedMediumKeywords = useMemo(() => {
    if (!mappings || !selectedMedium) {
      return null
    }
    return mappings.medium_keyword_map[selectedMedium] ?? null
  }, [mappings, selectedMedium])

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 pt-6 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          Loading mapping reference...
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Help data unavailable</CardTitle>
          <CardDescription>{error}</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  if (!mappings) {
    return null
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Info className="h-5 w-5" aria-hidden="true" />
            About
          </CardTitle>
          <CardDescription>
            Art Findr is a tool exploring and downloading open-access artworks across major museums.
          </CardDescription>
        </CardHeader>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <FileSearch className="h-5 w-5" aria-hidden="true" />
              Genre / Department
            </CardTitle>
            <CardDescription>Canonical genres mapped to museum-specific fields.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="genre-select">Inspect genre</Label>
              <Select id="genre-select" value={selectedGenre} onChange={(event) => setSelectedGenre(event.target.value)}>
                {mappings.genres.map((genre) => (
                  <option key={genre} value={genre}>
                    {genre}
                  </option>
                ))}
              </Select>
            </div>

            <div className="space-y-3 rounded-md border p-3">
              <MappingRow title="Cleveland Museum of Art" values={asList(selectedGenreMap?.cma)} />
              <MappingRow title="Art Institute of Chicago" values={asList(selectedGenreMap?.aic)} />
              <MappingRow title="Museum of Modern Art" values={asList(selectedGenreMap?.moma)} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Tags className="h-5 w-5" aria-hidden="true" />
              Medium Keywords
            </CardTitle>
            <CardDescription>Client-side keywords used per museum for medium classification.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="medium-select">Inspect medium</Label>
              <Select id="medium-select" value={selectedMedium} onChange={(event) => setSelectedMedium(event.target.value)}>
                {mappings.media.map((medium) => (
                  <option key={medium} value={medium}>
                    {medium}
                  </option>
                ))}
              </Select>
            </div>

            <div className="space-y-3 rounded-md border p-3">
              <KeywordRow title="Cleveland Museum of Art" values={selectedMediumKeywords?.cma ?? []} />
              <KeywordRow title="Art Institute of Chicago" values={selectedMediumKeywords?.aic ?? []} />
              <KeywordRow title="Museum of Modern Art" values={selectedMediumKeywords?.moma ?? []} />
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Museum Field Reference</CardTitle>
          <CardDescription>Expanded metadata is available below for deeper debugging/reference.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3">
          {Object.entries(mappings.museum_field_map).map(([museum, fields]) => (
            <details key={museum} className="rounded-md border p-3">
              <summary className="cursor-pointer font-medium">{MUSEUM_NAMES[museum.toUpperCase()] ?? museum}</summary>
              <div className="mt-3 grid gap-2">
                {Object.entries(fields).map(([fieldName, fieldConfig]) => (
                  <div key={fieldName} className="rounded border p-2 text-xs">
                    <p className="font-semibold uppercase tracking-wide">{fieldName}</p>
                    <pre className="mt-1 overflow-x-auto whitespace-pre-wrap text-[11px] text-muted-foreground">
                      {JSON.stringify(fieldConfig, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>
            </details>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}

function MappingRow({ title, values }: { title: string; values: string[] }) {
  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-[0.1em] text-muted-foreground">{title}</p>
      <div className="flex flex-wrap gap-2">
        {values.length > 0 ? values.map((value) => <Badge key={value} variant="secondary">{value}</Badge>) : <Badge variant="outline">No mapping</Badge>}
      </div>
    </div>
  )
}

function KeywordRow({ title, values }: { title: string; values: string[] }) {
  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-[0.1em] text-muted-foreground">{title} keywords</p>
      <div className="flex flex-wrap gap-2">
        {values.map((value) => (
          <Badge key={value} variant="outline">
            {value}
          </Badge>
        ))}
      </div>
    </div>
  )
}
