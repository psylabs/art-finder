import { expect, test } from "@playwright/test"

const tinyPng = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/w8AAgMBg3x8A5YAAAAASUVORK5CYII=",
  "base64",
)

test("app keeps CTA visible, renders image/actions, and preserves state across Help navigation", async ({ page }) => {
  let searchCallCount = 0

  await page.route("**/api/options", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        source_names: {
          AIC: "Art Institute of Chicago",
          CMA: "Cleveland Museum of Art",
          MOMA: "Museum of Modern Art",
        },
        genre_options: ["All genres", "American Art"],
        medium_options: ["All media", "Painting"],
        fetch_limit_options: [50, 100],
        defaults: {
          sources: ["CMA"],
          orientation: "Portrait",
          limit: 50,
          use_random_seed: false,
          random_seed: 42,
          ssl_bypass: false,
        },
      }),
    })
  })

  await page.route("**/api/search", async (route) => {
    searchCallCount += 1
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        artworks: [
          {
            id: "A1",
            source: "CMA",
            title: "Test Artwork",
            artist: "Artist",
            image_url: "http://127.0.0.1:4173/__fixtures__/test-image.png",
            filename: "test-artwork.jpg",
            date: "1900",
            medium: "Oil on canvas",
            department: "Modern Art",
            classification: "Painting",
            is_downloadable: true,
            metadata: {},
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
        logs: ["log"],
      }),
    })
  })

  await page.route("**/api/help/mappings", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        genres: ["American Art"],
        media: ["Painting"],
        department_map: {
          "American Art": {
            cma: ["American Painting and Sculpture"],
            aic: ["American Art"],
            moma: ["american"],
          },
        },
        museum_field_map: {
          CMA: { genre: { source_fields: ["department"], match: "exact" } },
        },
        medium_keyword_map: {
          Painting: { cma: ["painting"], aic: ["painting"], moma: ["painting"] },
        },
      }),
    })
  })

  await page.route("**/__fixtures__/test-image.png", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "image/png",
      body: tinyPng,
    })
  })

  await page.goto("/")

  const loadButton = page.getByRole("button", { name: "Load Artworks" })
  await expect(loadButton).toBeVisible()

  const box = await loadButton.boundingBox()
  expect(box).not.toBeNull()
  if (box) {
    expect(box.y + box.height).toBeLessThanOrEqual(page.viewportSize()!.height)
  }

  await loadButton.click()

  await expect(page.getByText("Test Artwork")).toBeVisible()
  await expect(page.getByText("1 of 1")).toBeVisible()

  const image = page.getByRole("img", { name: "Test Artwork" })
  await expect(image).toBeVisible()
  const naturalWidth = await image.evaluate((element) => (element as HTMLImageElement).naturalWidth)
  expect(naturalWidth).toBeGreaterThan(0)

  const actions = page.getByTestId("artwork-actions")
  await expect(actions).toBeVisible()
  await expect(actions.getByRole("button", { name: "Skip" })).toBeVisible()
  await expect(actions.getByRole("button", { name: "Download" })).toBeVisible()

  const detailsButton = page.getByRole("button", { name: "Details" })
  await expect(detailsButton).toHaveAttribute("aria-expanded", "false")
  await detailsButton.click()
  await expect(detailsButton).toHaveAttribute("aria-expanded", "true")
  const detailsPanel = page.getByText("Applied filters")
  await expect(detailsPanel).toBeVisible()
  const panelBox = await detailsPanel.boundingBox()
  expect(panelBox).not.toBeNull()
  if (panelBox) {
    expect(panelBox.x).toBeGreaterThanOrEqual(0)
    expect(panelBox.x + panelBox.width).toBeLessThanOrEqual(page.viewportSize()!.width)
  }

  await expect(page.getByText(/^Museums:/)).toHaveCount(0)

  await page.getByRole("link", { name: "Help" }).click()
  await expect(page.getByText("About")).toBeVisible()
  await expect(page.getByText("Art Findr is a tool exploring and downloading open-access artworks across major museums.")).toBeVisible()

  await page.getByRole("link", { name: "App" }).click()
  await expect(page.getByText("Test Artwork")).toBeVisible()
  expect(searchCallCount).toBe(1)
})
