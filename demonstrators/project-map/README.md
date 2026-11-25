# Accessible Interactive Project Map — Synthetic Demonstration

**What this page proves:** a public-facing project map can be fully usable without
a mouse. Every project is reachable by keyboard on the map itself, and the same
information is available as a plain text list, so the map is never the only way
to get it. Projects are managed by editing a CSV file — no database, no backend,
no account, no build step.

**Synthetic data only.** Every project, name, and coordinate on this page is
fictional. No real projects, places, or clients are represented. This demonstrator
makes no claim of survey or engineering licensure and no claim of ArcGIS
Enterprise experience.

## How to open it

Open `index.html` directly in a browser (double-click, or File → Open). No server
needed. It loads:

- Leaflet 1.9.4 (unpkg CDN) for the map, with the CartoDB `light_all` raster
  basemap (free, no key).
- Papa Parse 5.4.1 (jsDelivr CDN) to parse `projects.csv`.

One caveat, handled in the page: some browsers block `fetch()` of a local file
when a page is opened via `file://`. If that happens, the page falls back to an
embedded copy of the CSV (identical content, in the `<script type="text/csv"
id="embedded-csv">` block) and says so on screen. When served over HTTP the live
`projects.csv` is always used. To avoid the fallback entirely, serve the folder
with any static server, e.g. `python3 -m http.server` in this directory.

## How to manage projects

1. Edit `projects.csv` in any spreadsheet or text editor. Columns (all required):
   `id`, `name`, `category`, `status`, `lat`, `lon`, `description`, `contact_note`.
2. Keep names obviously fictional (e.g. "… — Concept"), keep coordinates as
   illustrative points near New Smyrna Beach, FL (approx. 29.0° N, 80.9° W),
   and never put a real client or site in `contact_note` — the sample rows say
   "Demonstration contact only — no real client."
3. Save the file and reload the page. Markers, list, filter options, and counts
   are all rebuilt from the CSV at load. No other file needs editing — unless
   you opened the page via `file://` and it used the embedded fallback, in which
   case keep the embedded copy in `index.html` in sync (same rows, same order).
4. Adding a category: just use the new category value in a row; the filter
   dropdown is built from the distinct categories in the file.

Current rows (6): P-01 Demo Riverwalk Trail — Concept (Trail/Concept),
P-02 Synthetic Wetland Boardwalk — Concept (Wetland/Concept),
P-03 Imaginary Pocket Park — Concept (Park/Planning),
P-04 Fictional Waterfront Overlook — Concept (Waterfront/Concept),
P-05 Sample Greenway Connector — Concept (Trail/Planning),
P-06 Mock Community Plaza — Concept (Park/Concept).

## Accessibility features

- **Markers are real `<button>` elements.** Each Leaflet marker is a `divIcon`
  whose HTML is a `<button class="marker-btn">` with an `aria-label` like
  "Project 2 of 6: Synthetic Wetland Boardwalk — Concept, Wetland, status
  Concept. Press Enter to open details." Tab reaches every marker in list order.
- **Arrow-key navigation.** `onProjectKeydown` (attached to every marker button
  and every list button) handles ArrowRight/ArrowDown (next project) and
  ArrowLeft/ArrowUp (previous project), wrapping at the ends, moving focus in
  list order. It calls `preventDefault()` + `stopPropagation()` so Leaflet's
  own map-panning arrow keys do not also fire. Enter/Space activate natively
  because the markers are buttons (a `click` listener opens the detail).
- **Visible focus.** `:focus-visible` gives a 3 px solid `#005FCC` outline with
  2 px offset on every focusable element (3 px offset on markers). Focus is
  never conveyed by colour alone; the open project also gets
  `aria-pressed="true"` and a darker marker colour.
- **Focus management.** Opening a project moves focus to the detail panel
  heading (`tabindex="-1"`). Closing it (Close button or Escape) returns focus
  to the marker/list button that opened it.
- **List alternative.** "All projects" below the map lists every project with
  the same name, category, status, and description, with the same keyboard
  behaviour. A skip link jumps straight to it.
- **Filter by category.** A labelled `<select>` filters markers and list
  together; the result count ("N of 6 projects shown") is announced via
  `aria-live="polite"`, and an empty state appears when nothing matches.
- **Labels and structure.** Map region has `role="region"` + `aria-label` +
  `aria-describedby` pointing at the keyboard instructions; the detail panel
  is `aria-live`-adjacent via its heading focus; legend explains the badges.
- **Visible SYNTHETIC banner** at the top of every view, plus a footer
  disclaimer, stating no real projects or places are represented.

### How to test it (keyboard-only pass)

1. Open the page, press Tab from the top: skip link → banner is text, not a
   stop → filter dropdown → Reset button → marker 1 on the map.
2. On a marker, press ArrowRight repeatedly: focus moves 1 → 2 → 3 → 4 → 5 →
   6 → wraps to 1. ArrowLeft goes the other way.
3. Press Enter on a marker: focus moves into the Project detail panel and the
   details are announced. Press Escape: focus returns to that marker.
4. Tab past the map into the list: the same arrow keys move between list
   entries; Enter opens the same detail panel.
5. Change the filter to "Trail": the map shows 2 markers, the list shows 2
   entries, and the count reads "2 of 6 projects shown."
6. With a screen reader, confirm each marker announces its project name,
   category, and status, and the detail heading is reached on activation.

## Contrast pairs (WCAG 2.1 AA, computed — all pass)

| Text / element | Foreground | Background | Ratio | Requirement |
|---|---|---|---|---|
| Body text | `#1A1A1A` | `#FFFFFF` | 17.40:1 | ≥ 4.5:1 |
| Header text | `#FFFFFF` | `#0B3D5C` | 11.44:1 | ≥ 4.5:1 |
| Links / list titles | `#0B4F6C` | `#FFFFFF` | 8.94:1 | ≥ 4.5:1 |
| Button text | `#FFFFFF` | `#0B4F6C` | 8.94:1 | ≥ 4.5:1 |
| Synthetic banner text | `#4A3200` | `#FFF3CD` | 10.85:1 | ≥ 4.5:1 |
| Badge "Concept" | `#1B4D2A` | `#E3F2E6` | 8.46:1 | ≥ 4.5:1 |
| Badge "Planning" | `#4A3200` | `#FFF3CD` | 10.85:1 | ≥ 4.5:1 |
| Marker number | `#FFFFFF` | `#0B4F6C` | 8.94:1 | ≥ 4.5:1 |
| Selected marker number | `#FFFFFF` | `#7A3B00` | 8.56:1 | ≥ 4.5:1 |
| Focus outline (non-text UI) | `#005FCC` | `#FFFFFF` | 5.98:1 | ≥ 3:1 |

## Verification (run 2026-11-16)

1. **CSV parse (python3 `csv` module):** `COLUMNS: ['id', 'name', 'category',
   'status', 'lat', 'lon', 'description', 'contact_note']` — all required
   columns present; **row count 6**; every `lat`/`lon` parses as a number in
   28.9–29.1° N / −81.0–−80.8° W (e.g. P-01 29.0253, −80.9201; P-06 29.0289,
   −80.9330). **PASS.** The embedded fallback CSV in `index.html` is
   byte-identical to `projects.csv`. **PASS.**
2. **`node --check` on the extracted inline JS** (10,617 chars, the single
   `<script>` block): **PASS** (exit 0, no output = no syntax errors).
3. **Code inspection of the wiring:**
   - `onProjectKeydown` is attached at **two sites**: marker buttons
     (`index.html:321`, inside `render()` after `marker.getElement()`) and
     list buttons (`index.html:348`, inside `renderList()`). It handles
     ArrowRight/ArrowDown/ArrowLeft/ArrowUp with wrap-around via
     `focusProject()`, which focuses the marker button if present, else the
     list button; other keys return early so Enter/Space fire the native
     button `click` → `openProject()`.
   - Focus management: `openProject()` calls `detailHeading.focus()` (line
     410); `closeDetail()` returns focus to `lastInvoker` (line 422); Escape
     closes the detail (line 427, document-level listener).
   - List alternative: `renderList()` rebuilds `<ul id="project-list">` from
     the same `visibleProjects` array as the markers, same order, same
     details — verified by inspection, plus the skip link targets
     `#project-list-heading`.
   - Contrast ratios computed programmatically (table above); all pass.
4. **CDN reachability (curl HEAD):** all HTTP 200 —
   `unpkg.com/leaflet@1.9.4/dist/leaflet.css`, `leaflet.js`,
   `cdn.jsdelivr.net/npm/papaparse@5.4.1/papaparse.min.js`, and a sample
   CartoDB tile `basemaps.cartocdn.com/light_all/13/2375/3333.png`.
