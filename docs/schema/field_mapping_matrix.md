# Art Findr Field Mapping Matrix (v1)

This document shows how normalized UI filters and output fields map to source APIs.

## 1) Normalized Filter Schema

| Normalized filter | Type | CMA source fields | AIC source fields | MoMA source fields | Match strategy |
|---|---|---|---|---|---|
| `query` | `str` | request param `q` | request param `q` | request param emulation over dataset rows | API-level where supported; otherwise client-side search |
| `department` (UI label: Genre) | enum | request param `department` when 1:1 mapping; client-side OR match when many-to-many | client-side over `department_title` | client-side over `Department`, `Classification`, `Medium`, `Nationality`, `ArtistBio` | canonical-to-source mapping + case-insensitive contains |
| `medium` | enum | client-side over `technique`, `type`, `department` | client-side over `medium_display`, `classification_title`, `department_title` | client-side over `Medium`, `Classification`, `Department` | keyword-based contains |
| `place_of_origin` | `str` | client-side over normalized `place_of_origin` fallback `culture` | client-side over `place_of_origin` | client-side over normalized `Nationality` fallback `ArtistBio` | case-insensitive substring |
| `year_from` / `year_to` | `int` | request params `created_after` / `created_before` | client-side over `date_start` / `date_end` | client-side over `BeginDate` / `EndDate` | range overlap logic |
| `orientation` | enum | client-side over image width/height | client-side over thumbnail width/height | client-side over parsed `Width (cm)` / `Height (cm)` | portrait/landscape check |
| `limit` | `int` | request param `limit` | request param `limit` | client-side trim | API-level + merged trim |
| `random_seed` | `int \| None` | n/a | n/a | n/a | merged deterministic shuffle |

## 2) Canonical Genre Enum

```text
African Art
American Art
Ancient Near Eastern Art
Asian Art
Contemporary Art
Egyptian Art
European Art
Greek and Roman Art
Islamic Art
Medieval Art
Modern Art
```

## 3) Canonical Medium Enum

```text
Decorative Arts
Drawings
Painting
Photography
Prints
Sculpture
Textiles
```

## 4) Many-to-Many Genre Mapping Table

| Canonical genre | CMA department mapping | AIC department mapping | MoMA keyword mapping |
|---|---|---|---|
| African Art | `African Art` | `Arts of Africa` | `africa`, `african` |
| American Art | `American Painting and Sculpture`, `Art of the Americas` | `American Art`, `Arts of the Americas` | `american`, `united states`, `u.s.`, `usa` |
| Ancient Near Eastern Art | `Egyptian and Ancient Near Eastern Art` | `Ancient and Byzantine Art` | `ancient`, `near eastern`, `mesopotamia`, `assyrian` |
| Asian Art | `Chinese Art`, `Japanese Art`, `Korean Art`, `Indian and South East Asian Art` | `Asian Art` | `asian`, `china`, `chinese`, `japan`, `japanese`, `korea`, `korean`, `india`, `indian` |
| Contemporary Art | `Contemporary Art` | `Contemporary Art` | `contemporary` |
| Egyptian Art | `Egyptian and Ancient Near Eastern Art` | `Ancient and Byzantine Art` | `egypt`, `egyptian` |
| European Art | `European Painting and Sculpture`, `Modern European Painting and Sculpture` | `Painting and Sculpture of Europe`, `European Decorative Arts` | `europe`, `european`, `france`, `french`, `italy`, `italian`, `germany`, `german`, `spain`, `spanish`, `britain`, `english`, `dutch` |
| Greek and Roman Art | `Greek and Roman Art` | `Ancient and Byzantine Art` | `greek`, `roman` |
| Islamic Art | `Islamic Art` | `Islamic Art` | `islamic` |
| Medieval Art | `Medieval Art` | `Medieval Art` | `medieval` |
| Modern Art | `Modern European Painting and Sculpture`, `Contemporary Art` | `Modern Art`, `Contemporary Art` | `modern` |

Notes:
- `Modern Art` has an implicit lower year guard (`>= 1860`) when no `year_from` is supplied.
- When a canonical genre maps to multiple source departments, client-side OR filtering is used.

## 5) Medium Keyword Matching (Client-side)

| Canonical medium | CMA keywords | AIC keywords |
|---|---|---|
| Decorative Arts | `decorative`, `design`, `furniture` | `decorative`, `applied arts` |
| Drawings | `drawing` | `drawing` |
| Painting | `painting` | `painting` |
| Photography | `photography`, `photo` | `photograph`, `photo` |
| Prints | `print`, `etching`, `lithograph`, `woodcut` | `print`, `etching`, `lithograph`, `woodcut` |
| Sculpture | `sculpture`, `statue` | `sculpture`, `statue` |
| Textiles | `textile`, `fabric`, `tapestry` | `textile`, `fabric`, `tapestry` |

## 6) Output Field Mapping (Important Fields)

| Normalized output field | CMA source field(s) | AIC source field(s) | MoMA source field(s) |
|---|---|---|---|
| `title` | `title` | `title` | `Title` |
| `artist` | `creators[0].description` fallback `culture` | `artist_display` fallback `artist_title` | `Artist` |
| `department` | `department` | `department_title` | `Department` |
| `classification` | `type` | `classification_title` | `Classification` |
| `medium` | `technique` | `medium_display` | `Medium` |
| `place_of_origin` | `place_of_origin` fallback `culture` | `place_of_origin` | `Nationality` fallback `ArtistBio` |
| `rights_label` | `share_license_status` fallback normalized default | `copyright_notice` fallback public-domain/restricted | metadata/thumbnail-rights placeholder |
| `is_downloadable` | derived from image/licensing markers | derived from `is_public_domain` | currently `False` (metadata-first) |

## 7) Known Source Enums (Currently Tracked)

### CMA department enum (native)

```text
African Art
American Painting and Sculpture
Art of the Americas
Chinese Art
Contemporary Art
Decorative Art and Design
Drawings
Egyptian and Ancient Near Eastern Art
European Painting and Sculpture
Greek and Roman Art
Indian and South East Asian Art
Islamic Art
Japanese Art
Korean Art
Medieval Art
Modern European Painting and Sculpture
Oceania
Performing Arts, Music, & Film
Photography
Prints
Textiles
```

### AIC department enum (native)

AIC department values are treated as dynamic. Current filtering uses mapping targets in section 4 and case-insensitive contains matching over `department_title`.

### MoMA department enum (native)

MoMA department values are treated as dataset-driven dynamic values from the `Department` column, loaded from the public collection CSV.
