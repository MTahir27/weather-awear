# Weather-Aware Truck Routing — Implementation Plan

Spotter Full Stack assessment. React + Django app that helps a truck driver pick the safest route
based on weather, load weight, and travel time.

**Deadline:** ~2 days remaining (submit by 2026-10-12). Then Spotter's team tests the hosted app.

## Grading → priorities

| Weight | Area | Strategy |
|---|---|---|
| **40%** | Routes, weather, risk & recommendation logic | Pure, unit-tested domain functions; every ambiguity resolved explicitly and documented |
| **35%** | UI, map & heatmap smoothness/performance | Fetch heatmap data once; slider = zero network + zero React re-render; WebGL (deck.gl) |
| 10% | Code quality | Typed, thin views + services layer, provider interfaces, CI |
| 5% | Docs & walkthrough | README "Interpretations & Assumptions" section + 5–10 min Loom |

"Prioritize correctness and clarity over extra features."

---

## 1. Spec interpretations (closing the loopholes)

Each item below gets a unit test and a line in the README.

1. **Threshold boundaries** — half-open intervals; a boundary value escalates.
   - Wind (mph): Low <25 · Moderate [25,35) · High [35,45) · Severe [45,55) · No Travel ≥55
   - Rain (in/hr): Low <0.10 · Moderate [0.10,0.25) · High [0.25,0.50) · Severe [0.50,1.00] · No Travel >1.00
   - Snow (in/hr): Low <0.5 · Moderate [0.5,1.0) · High [1.0,2.0) · Severe [2.0,3.0] · No Travel >3.0
   - Decimal values (e.g. 34.6 mph) fall into the gaps of the integer table — handled by the intervals above.
2. **Checkpoint risk = worst of factors**: `max(wind_after_load_rules, rain, snow)`. Store the *driver*
   (e.g. "Wind 47 mph + 38,000 lb load") so the UI explains every level.
3. **Load rules only escalate** (strict `>`):
   - wind ≥55 → No Travel (any load)
   - wind [45,55) and load >30,000 lb → No Travel
   - wind [35,45) and load >40,000 lb → Severe
   - Tests at 30,000 / 30,001 and 40,000 / 40,001 lb.
4. **No Travel in ranking** (spec omits it). Ranking key (lexicographic):
   `(no_travel_miles, severe_miles, high_miles, avg_risk, duration)`.
   If **all** routes contain No Travel → "Do not travel at this departure time" banner + least-bad option.
5. **Sampling interval** 10 / 25 / 50 mi is a user selector (default 25). Checkpoints always include
   mile 0 and the destination. Same interval for all routes.
6. **Risk miles** — each checkpoint owns the route stretch from the midpoint to the previous checkpoint
   to the midpoint to the next. Stretches sum exactly to route length. Average risk is
   distance-weighted (Low=0, Moderate=1, High=2, Severe=3, No Travel=4).
7. **Checkpoint ETA** — distance→time mapping built from routing API per-instruction
   `routeOffsetInMeters` + `travelTimeInSeconds` (not a uniform average speed). Departure-aware truck routing.
8. **Forecast-hour alignment** — Open-Meteo rain/showers/snowfall are *preceding-hour* sums, so an
   ETA of 14:20 uses the 15:00 value. Wind is instantaneous → linear interpolation between hours.
9. **Missing data ≠ Low** — beyond forecast horizon or failed fetch → **Unknown**. Routes report
   unknown miles and show a warning; ranking penalises unknown data, never hides it.
10. **Wind = sustained 10 m wind** (decided). Gusts shown in tooltip; "⚠ Gusty" badge when gusts ≥45 mph.
    Documented as a deliberate choice.
11. **Time zones** — UTC internally; frontend sends ISO with offset; display in viewer's tz with label.
12. **Departure validation** — reject past times (small skew allowed); warn when part of the trip
    falls beyond the forecast horizon.
13. **"Balancing"** — implement the spec's priority order exactly; show a plain-English
    "Why this route" line (e.g. "0 Severe mi vs 12; 40 min longer").
14. **Hours of Service** (decided: include, ON by default, toggle off) — simplified FMCSA rules:
    30-min break after 8 h cumulative driving; 10 h off after 11 h driving. Weather while parked is
    not counted as driving risk. Rest stops shown as markers. Not modelled: 14-h window, 60/70-h weekly limits.

---

## 2. Stack & third-party APIs

| Concern | Choice |
|---|---|
| Routing | **TomTom Routing API** — `travelMode=truck`, `vehicleWeight` (kg), `departAt`, `maxAlternatives=2`, instructions for per-segment timing |
| Geocoding | TomTom Search (autocomplete, `countrySet=US,CA`), proxied through backend |
| Weather | **Open-Meteo** hourly forecast — `wind_speed_unit=mph`, `precipitation_unit=inch`, `timeformat=unixtime`; vars `wind_speed_10m, wind_gusts_10m, rain, showers, snowfall`; batched multi-location requests |
| Map | MapLibre GL + **deck.gl**, OpenFreeMap tiles (no key) |
| Backend | Django 5 + DRF, httpx (concurrent), tenacity retries |
| Frontend | React + TypeScript + Vite, TanStack Query, Zod, Tailwind, zustand |

**To verify at build time:** TomTom `maxAlternatives` param (check official docs); whether Open-Meteo
counts a multi-location request as 1 call or N (design for N: cap grid points, round + dedupe coords).

**Fewer than 3 routes:** re-query with a lateral via-point offset at route midpoint / avoid
motorways or tolls; dedupe near-identical routes (>90% shared distance); if still <3, say so in the UI.

**Secrets:** `TOMTOM_API_KEY` in `backend/.env` (gitignored, `.env.example` committed) and in Vercel
env vars. Key never reaches the browser. No referrer restriction on the key (server-side calls).

---

## 3. Backend design (stateless — required for Vercel serverless)

```
backend/
  config/                 settings (env-driven), urls
  trips/
    api/                  views.py, serializers.py          (thin)
    providers/            routing_base.py, tomtom.py,
                          weather_base.py, open_meteo.py    (Protocol interfaces)
    domain/               pure, no I/O, ~100% tested
      risk.py             thresholds, load rules, RiskLevel enum, classify()
      sampling.py         haversine, cumulative distance, points every N mi
      eta.py              distance→time mapping + HOS breaks
      scoring.py          stretch ownership, severe/high/unknown miles, avg risk
      recommend.py        ranking key + "why" text
      corridor.py         heatmap grid generation
    services/plan_trip.py orchestration
  tests/
api/index.py              Vercel entry (exposes Django WSGI app)
```

**Endpoints**
- `GET  /api/geocode?q=` — debounced client-side.
- `POST /api/trips/plan` — `{origin, destination, departure_time, load_weight_lb, sample_interval_mi, hos_enabled}`
  → 3 routes (encoded polyline, distance, duration, arrival, checkpoints, summary, rest stops), ranking, "why".
- `POST /api/trips/heatmap` — `{routes (simplified encoded polylines), departure_time, load_weight_lb}`
  → `{points[], hours[], frames: {risk, wind, rain, snow}[hour][point]}` (compact arrays, gzipped).
  Called after plan returns so routes render first.

**plan_trip pipeline:** validate → routes (+fill to 3) → sample checkpoints → ETA (+HOS) →
batched/deduped weather → classify → score → rank.

**Heatmap:** ~25–30 mi buffer around the routes, adaptive grid spacing capped at 250 points,
49 hourly frames (0–48 h from departure), risk pre-scored with load rules.

**Robustness:** timeouts + retry/backoff on upstream calls; upstream failure → 502 with readable message;
partial weather failure → Unknown checkpoints; no keys client-side.

---

## 4. Frontend design

- **Trip form:** origin/destination autocomplete, departure datetime, weight (lb), interval 10/25/50,
  HOS toggle. Zod validation, inline errors.
- **Route cards:** distance, duration, arrival, No Travel/Severe/High/Unknown miles, avg risk,
  stacked risk-by-mile bar, ★ Recommended badge + "why" line.
- **Map (deck.gl):** all 3 routes; selected route coloured per segment by risk; checkpoint dots with
  tooltip (mile, ETA, wind/gust, rain, snow, level + driver, load-rule note); rest-stop markers; auto-fit.
- **Heatmap:** one translucent disc per corridor grid cell (meters-sized, coloured by risk band; unknown
  cells grey). A kernel `HeatmapLayer` was prototyped and rejected because its smoothing hid isolated
  hazardous cells (see docs/assumptions.md). Metric toggle: risk / wind / rain / snow / off.
- **Slider:** 0–48 h from departure, absolute-time label, ▶ play. Truck marker on each route at slider time.
- **Performance:** all frames fetched once into Float32Arrays; slider only changes layer hour index via
  `updateTriggers` + rAF; memoised layers; simplified polylines; lazy-loaded map bundle.
- **Polish:** colour-blind-safe palette + text labels, skeleton loading, legend, responsive.

---

## 5. Testing

- **pytest:** table-driven boundary tests for every threshold and load rule; sampling on synthetic
  polylines; ETA interpolation; HOS schedule; stretch ownership sums to length; ranking (No Travel,
  ties, all-blocked); forecast-hour alignment; missing data → Unknown; providers mocked with respx + JSON fixtures.
- **Vitest:** frontend utils.
- **CI:** GitHub Actions — ruff, pytest, eslint, tsc, vitest.

---

## 6. Hosting, docs, Loom

**Primary: Vercel (free Hobby)** — one project: Vite build served statically, Django as a Python
serverless function under `/api/*`. One URL, no CORS, no sleeping. Set `maxDuration` for the API function.
No database, no cache required.

**Fallback:** frontend on Vercel + Django on Render free, kept warm with an UptimeRobot ping every 10 min.

**README:** live link, Loom link, architecture/data-flow diagram, Interpretations & Assumptions (section 1),
APIs and limits, setup (~3 commands), env vars, running tests, known limitations.

**Loom (5–10 min):** demo a weather trip → recommendation explanation → scrub slider →
heavy-load/high-wind No Travel case → quick tour of `domain/` → tests passing.

---

## 7. Development phases & engineering rules

### Rules (every phase)
- **Conventional Commits** (`feat(scope):`, `fix:`, `test:`, `chore:`, `docs:`, `ci:`), one logical change
  per commit, imperative mood, body explains *why* when not obvious.
- **Every commit is green**: lint + type-check + tests pass before committing (pre-commit hooks + `make check`).
- One branch per phase (`phase-N-name`) → PR → merge to `main`. `main` is always deployable.
- Tests are written alongside the code they cover (same commit), never "later".
- No secrets in git. `.env` gitignored, `.env.example` committed.
- Each phase ends with: all checks green, a short review, and a go-ahead before the next phase.

### Phase 0 — Foundation
Repo + tooling, nothing functional yet.
- Monorepo layout: `backend/` (Django, uv, Python 3.12), `frontend/` (Vite + React + TS), `api/index.py` (Vercel entry).
- Backend: env-driven settings, DRF, `GET /api/health`, pytest, ruff, mypy.
- Frontend: Tailwind, ESLint, Prettier, Vitest, typed API client stub.
- `vercel.json` (static SPA + Python function under `/api/*`), `requirements.txt` exported from uv.
- `Makefile` (`make dev`, `make check`), pre-commit hooks, GitHub Actions CI.
- **Exit:** `make check` green locally and in CI; hello-world deployed on Vercel.

### Phase 1 — Domain core (pure logic, the 40%)
`backend/trips/domain/` — no I/O, table-driven tests, near-100% coverage.
- `units.py` / `geo.py` — haversine, polyline cumulative distance, interpolate point at distance.
- `risk.py` — `RiskLevel` enum, thresholds, load rules, `classify()` returning level + drivers.
- `sampling.py` — checkpoints every N mi incl. origin & destination.
- `eta.py` — distance→time mapping from routing instructions; ETA at any mile (HOS hook point).
- `scoring.py` — stretch ownership, per-level miles, unknown miles, distance-weighted avg risk.
- `recommend.py` — ranking key, all-blocked detection, "why" explanation.
- **Exit:** every interpretation in section 1 has a passing test.

### Phase 2 — Providers & API
- `providers/` — `RoutingProvider` / `GeocodingProvider` / `WeatherProvider` Protocols; TomTom + Open-Meteo
  implementations (httpx, timeouts, retries, typed parsing); respx-mocked tests with JSON fixtures.
- `services/plan_trip.py` — orchestration (routes → sample → ETA → batched weather → classify → score → rank).
- `api/` — serializers with validation, `GET /api/geocode`, `POST /api/trips/plan`, error mapping (400/502).
- **Exit:** real Denver→Chicago request returns 3 scored routes; all tests green.

### Phase 3 — Frontend core
- App shell & layout, typed API client (TanStack Query), Zod-validated trip form with autocomplete.
- Route cards with summary + recommended badge + "why".
- Map: MapLibre + deck.gl, routes, risk-coloured selected route, checkpoint tooltips, legend, auto-fit.
- **Exit:** full plan flow works end to end against the local backend.

### Phase 4 — Heatmap & time slider
- Backend `domain/corridor.py` + `POST /api/trips/heatmap` (compact arrays, capped grid).
- Frontend per-cell heatmap layer (risk-band colours), metric toggle, 0–48 h slider with play,
  truck-position markers. Zero network / zero React re-render while scrubbing.
- **Exit:** smooth 60 fps scrubbing on a long route.

### Phase 5 — Hardening
- HOS breaks (toggle, rest-stop markers); fill to 3 routes; all-blocked banner; departure/horizon
  validation; Unknown-data UX; error & loading states; accessibility & mobile pass.
- **Exit:** edge-case checklist verified manually + tests.

### Phase 6 — Delivery
- README (architecture, assumptions, setup, API, tests, limitations), final Vercel deploy,
  production QA on 3–4 real trips, Loom script & recording.

## 8. Schedule (2 days)

**Day 1**
- [ ] 0–1 h: repo scaffold (backend + frontend), deploy "hello world" to Vercel early
- [ ] 1–5 h: domain logic + tests (risk, load rules, sampling, ETA, scoring, ranking)
- [ ] 5–8 h: TomTom + Open-Meteo providers, `/api/trips/plan`, `/api/geocode`
- [ ] 8–12 h: frontend form, route cards, map with routes + checkpoint tooltips

**Day 2**
- [ ] 0–4 h: heatmap endpoint + slider + play + truck marker
- [ ] 4–6 h: HOS, edge cases (<3 routes, past departure, Unknown data, all-blocked), error/loading states
- [ ] 6–8 h: polish, README, CI
- [ ] 8–10 h: final deploy, test 3–4 real trips on prod, record Loom
- [ ] ~2 h buffer

**Cut first if behind:** earliest-safe-departure finder, kg toggle, Playwright, HOS (document as limitation).
