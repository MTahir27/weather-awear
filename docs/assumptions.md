# Interpretations & assumptions

The brief leaves several rules open to interpretation. Each decision below is
implemented in `backend/trips/domain/` and pinned by tests in
`backend/tests/domain/`.

## Risk classification — [`risk.py`](../backend/trips/domain/risk.py)

| Condition | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind (mph) | < 25 | 25 – < 35 | 35 – < 45 | 45 – < 55 | ≥ 55 |
| Rain (in/hr) | < 0.10 | 0.10 – < 0.25 | 0.25 – < 0.50 | 0.50 – 1.00 | > 1.00 |
| Snow (in/hr) | < 0.5 | 0.5 – < 1.0 | 1.0 – < 2.0 | 2.0 – 3.0 | > 3.0 |

- **Shared edges go up.** The table's ranges touch (rain "0.10–0.25" and
  "0.25–0.50"), so a boundary value belongs to the higher level.
- **Explicit strict bounds are kept.** Rain No Travel is "> 1.00" and snow No
  Travel is "> 3.0", so exactly 1.00 in/hr rain or 3.0 in/hr snow is Severe.
- **Fractional wind speeds are covered.** The table's whole-number ranges
  (25–34, 35–44) leave gaps such as 34.6 mph. Those values fall into the lower band.
- **The overall checkpoint level is the worst factor** of wind (after load
  rules), rain and snow. The factors that set it are reported, so the UI can
  explain every level.
- **Wind uses sustained speed**, matching the table. Gusts are shown for
  information only.
- **Load rules only escalate** and use strict inequalities: 45–54 mph with a
  load above 30,000 lb is No Travel, and 35–44 mph with a load above 40,000 lb
  is Severe. Exactly 30,000 or 40,000 lb does not trigger them.
- **Missing data is Unknown, never Low.**
- Measurements are rounded to 6 decimals before comparison so floating-point
  noise (0.07 + 0.03 = 0.0999…) cannot drop a value below a threshold.

## Checkpoints — [`sampling.py`](../backend/trips/domain/sampling.py)

- The 10 / 25 / 50-mile sampling interval is chosen by the user (default 25).
  The same interval applies to every route, so routes are compared fairly.
- Checkpoints are placed at mile 0 and every multiple of the interval, plus
  one at the destination, so both trip ends are always assessed.

## Arrival times — [`eta.py`](../backend/trips/domain/eta.py), [`hos.py`](../backend/trips/domain/hos.py)

- ETAs are interpolated from the routing provider's progress anchors
  (distance → driving time, traffic-aware for the departure time), not from a
  route-average speed, so slow city stretches are reflected.
- **Hours of service** (on by default, can be turned off): a 30-minute break
  after 8 hours of driving and 10 hours off after 11 hours of driving, which
  also resets the break clock. A stop is only scheduled if driving remains.
  Not modelled: the 14-hour on-duty window, 60/70-hour weekly limits and the
  sleeper-berth split.

## Route risk — [`scoring.py`](../backend/trips/domain/scoring.py)

- The recommendation rules count *miles*, but checkpoints are points. Each
  checkpoint covers the road between the midpoints to its neighbours. These
  stretches add up exactly to the route length.
- Average risk is distance-weighted (Low = 0 … No Travel = 4).

## Recommendation — [`recommend.py`](../backend/trips/domain/recommend.py)

Routes are compared in this order:

1. **Fewest No Travel miles.** The brief's list starts at Severe, but a route
   crossing No Travel conditions must never outrank one that does not.
2. Fewest Severe miles.
3. Fewest High miles.
4. Lowest average risk.
5. Shortest travel time, including hours-of-service stops.
6. Shortest distance, then the provider's order, so ties are deterministic.

- **Unknown miles count as Severe when ranking.** This stops a route with
  missing forecasts from looking safer than one with known bad weather.
  Unknown miles are still reported separately.
- **When every route crosses No Travel conditions**, the least risky route is
  still returned, but flagged as not advised, with a suggestion to change the
  departure time.
- Distances are compared at 0.001-mile (~1.6 m) resolution and average risk at 0.001,
  so floating-point noise never decides a ranking, yet even a very short No
  Travel stretch still counts.
- The spec's order is applied strictly. "Balancing" risk and time means time
  only decides between routes whose weather risk is equal. Each recommendation
  states the deciding factor in plain English.

## Routes — [`route_options.py`](../backend/trips/services/route_options.py)

- **Three routes are guaranteed where the road network allows.** TomTom often
  returns fewer alternatives than requested (one or two for Denver → Chicago).
  To make up the difference, extra candidates are requested at the same time as
  the main request: via points 15% of the trip distance (15–150 km) to either
  side of the midpoint, plus routes avoiding toll roads and motorways.
- A fallback is used only if it overlaps every chosen route by less than 90%
  (checked in both directions) and takes at most 1.5× the fastest travel time.
- Trade-off: four extra routing calls per plan, in exchange for ~40% lower
  latency on long trips.
- **Routing uses gross vehicle weight.** The brief's load weight is cargo,
  while truck routing restrictions apply to the whole vehicle. Routing is
  therefore requested with load + 35,000 lb (a typical empty tractor-trailer).
  Risk rules use the load weight, as the brief specifies.

## Weather — [`forecast.py`](../backend/trips/domain/forecast.py), [`open_meteo.py`](../backend/trips/providers/open_meteo.py)

- Forecasts come from Open-Meteo (hourly, mph and inches, up to 16 days ahead).
- Precipitation values are totals for the hour *ending* at their timestamp,
  so an arrival at 14:20 uses the 15:00 value. Wind and gusts are interpolated
  between hours.
- Liquid precipitation is rain plus showers.
- Checkpoints within ~2 km of each other share one forecast location. This is
  finer than the weather models' own grid, and avoids duplicate lookups on
  shared highway stretches.
- **Weather-API budget.** Open-Meteo's free tier allows 600 calls a minute,
  5,000 an hour and 10,000 a day. Its documentation doesn't say how
  multi-location requests count, so each location is assumed to count as one
  call. A plan uses at most 200 forecast locations and a heatmap at most 150.
  On very long trips at 10-mile spacing (New York → Los Angeles has ~890
  checkpoints), the shared-location grid coarsens until the trip fits.
  Coarsened, it stays close to the ~13–25 km grid of the models that forecast
  beyond 2 days. Every checkpoint is still read at its own arrival time.
- Arrivals beyond the forecast horizon are **Unknown**.

## Departure window — [`serializers.py`](../backend/trips/api/serializers.py)

- Departure must be between now (with 15 minutes' grace, treated as "now")
  and 7 days ahead. Further out, forecasts for the far end of a long trip are
  unreliable.
- Origin and destination must be at least 1 mile apart. Load weight is
  limited to 0–150,000 lb.

## Heatmap — [`corridor.py`](../backend/trips/domain/corridor.py), [`heatmap.py`](../backend/trips/services/heatmap.py), [`layers.ts`](../frontend/src/map/layers.ts)

- The slider runs from the departure time (0 h) to 48 h after it, in hourly
  frames. Each frame is scored like route checkpoints, using the same hour
  alignment and the same load rules, so the heatmap and the route colours
  always agree. A truck marker shows where each route's truck is at that
  hour, parked during rest stops.
- Forecasts come from a regular grid within ~25 miles of every route. The
  grid is capped at 150 points: the cell size grows until the trip fits, which
  keeps weather-API usage predictable.
- The Wind, Rain and Snow views use a continuous 0–4 score that crosses each
  integer exactly at that factor's threshold. They share the risk legend's
  colour bands, even though the thresholds are unevenly spaced.
- **Each grid cell is drawn with its own value.** A kernel-density heatmap was
  tried and rejected: smoothing averaged isolated hazardous cells with calm
  neighbours until they disappeared. Low cells are clear, and cells without
  forecast data are grey.
