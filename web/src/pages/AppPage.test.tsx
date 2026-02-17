import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { APP_SESSION_STORAGE_KEY, APP_SESSION_VERSION } from "@/lib/session"
import type { AppOptions, SearchResponse } from "@/lib/types"
import * as api from "@/lib/api"
import { AppPage } from "@/pages/AppPage"

vi.mock("@/lib/api", () => ({
  getOptions: vi.fn(),
  searchArtworks: vi.fn(),
}))

const mockedGetOptions = vi.mocked(api.getOptions)
const mockedSearchArtworks = vi.mocked(api.searchArtworks)

const optionsFixture: AppOptions = {
  source_names: {
    AIC: "Art Institute of Chicago",
    CMA: "Cleveland Museum of Art",
    MOMA: "Museum of Modern Art",
  },
  genre_options: ["All genres", "American Art"],
  medium_options: ["All media", "Painting"],
  fetch_limit_options: [50, 100],
  defaults: {
    sources: ["CMA", "AIC", "MOMA"],
    orientation: "Portrait",
    limit: 50,
    use_random_seed: false,
    random_seed: 42,
    ssl_bypass: false,
  },
}

function makeSearchFixture(imageUrl = "https://example.com/image.jpg"): SearchResponse {
  return {
    artworks: [
      {
        id: "A1",
        source: "CMA",
        title: "Test Artwork",
        artist: "Artist",
        image_url: imageUrl,
        filename: "test-artwork.jpg",
        date: "1900",
        medium: "Oil on canvas",
        department: "Modern Art",
        classification: "Painting",
        credit: "Gift",
        culture: "French",
        description: "A sample description",
        accession_number: "123.4",
        is_downloadable: true,
        rights_label: "Public Domain",
        metadata: {
          tombstone: "Tombstone text",
        },
      },
    ],
    errors: [],
    warnings: [],
    filter_status: {
      applied: {
        "CMA.orientation": "Portrait",
      },
      skipped: {},
    },
    source_counts: {
      CMA: 1,
    },
    seed_used: 7,
    logs: ["2026-02-16 12:00:00 | INFO  | Fetching from sources: CMA"],
  }
}

describe("AppPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
  })

  it("loads options, submits search, and renders artwork metadata and image", async () => {
    mockedGetOptions.mockResolvedValue(optionsFixture)
    mockedSearchArtworks.mockResolvedValue(makeSearchFixture())

    render(<AppPage />)

    await screen.findByRole("button", { name: "Load Artworks" })
    await userEvent.click(screen.getByRole("button", { name: "Load Artworks" }))

    await waitFor(() => {
      expect(mockedSearchArtworks).toHaveBeenCalledTimes(1)
    })

    expect(mockedSearchArtworks).toHaveBeenCalledWith(
      expect.objectContaining({
        sources: ["CMA", "AIC", "MOMA"],
        orientation: "Portrait",
        year_from: null,
        year_to: null,
      }),
    )

    expect(await screen.findByText("Test Artwork")).toBeInTheDocument()
    expect(screen.getByText("1 of 1")).toBeInTheDocument()

    const image = screen.getByRole("img", { name: "Test Artwork" })
    expect(image).toHaveAttribute("src", "https://example.com/image.jpg")

    fireEvent.load(image)
    await waitFor(() => {
      expect(screen.queryByText("Loading image...")).not.toBeInTheDocument()
    })

    expect(screen.queryByText(/^Museums:/)).not.toBeInTheDocument()
  })

  it("prevents deselecting the last museum source", async () => {
    mockedGetOptions.mockResolvedValue({
      ...optionsFixture,
      source_names: { CMA: "Cleveland Museum of Art" },
      defaults: { ...optionsFixture.defaults, sources: ["CMA"] },
    })

    render(<AppPage />)

    await userEvent.click(await screen.findByText("1 selected"))
    const sourceToggle = await screen.findByLabelText("Cleveland Museum of Art")
    expect(sourceToggle).toBeChecked()

    await userEvent.click(sourceToggle)

    expect(await screen.findByText("At least one museum must be selected.")).toBeInTheDocument()
    expect(sourceToggle).toBeChecked()
  })

  it("shows an image error state and allows retry", async () => {
    mockedGetOptions.mockResolvedValue(optionsFixture)
    mockedSearchArtworks.mockResolvedValue(makeSearchFixture("https://example.com/broken.jpg"))

    render(<AppPage />)

    await screen.findByRole("button", { name: "Load Artworks" })
    await userEvent.click(screen.getByRole("button", { name: "Load Artworks" }))

    const image = await screen.findByRole("img", { name: "Test Artwork" })
    fireEvent.error(image)

    expect(await screen.findByText("Image failed to load")).toBeInTheDocument()

    await userEvent.click(screen.getByRole("button", { name: "Retry image" }))

    await waitFor(() => {
      expect(screen.queryByText("Image failed to load")).not.toBeInTheDocument()
    })
  })

  it("restores persisted session state on mount", async () => {
    mockedGetOptions.mockResolvedValue(optionsFixture)

    window.localStorage.setItem(
      APP_SESSION_STORAGE_KEY,
      JSON.stringify({
        version: APP_SESSION_VERSION,
        savedAt: Date.now(),
        form: {
          selectedSources: ["CMA"],
          department: "All genres",
          medium: "All media",
          query: "",
          orientation: "Portrait",
          fromDate: "",
          toDate: "",
          limit: 50,
          sslBypass: false,
          useRandomSeed: false,
          randomSeed: "42",
        },
        result: makeSearchFixture(),
        currentIndex: 0,
        debugLogs: ["persisted log"],
      }),
    )

    render(<AppPage />)

    expect(await screen.findByText("Test Artwork")).toBeInTheDocument()
    expect(mockedSearchArtworks).not.toHaveBeenCalled()
  })

  it("clears date fields through integrated clear controls", async () => {
    mockedGetOptions.mockResolvedValue(optionsFixture)

    render(<AppPage />)

    await screen.findByRole("button", { name: "Load Artworks" })
    await userEvent.click(screen.getByRole("button", { name: "Advanced" }))

    const fromDate = screen.getByLabelText("From date")
    const toDate = screen.getByLabelText("To date")

    await userEvent.type(fromDate, "2024-01-10")
    await userEvent.type(toDate, "2024-12-31")

    expect(fromDate).toHaveValue("2024-01-10")
    expect(toDate).toHaveValue("2024-12-31")

    await userEvent.click(screen.getByRole("button", { name: "Clear from date" }))
    await userEvent.click(screen.getByRole("button", { name: "Clear to date" }))

    expect(fromDate).toHaveValue("")
    expect(toDate).toHaveValue("")
  })
})
