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
- Distances are compared at 0.1-mile resolution and average risk at 0.001,
  so floating-point noise never decides a ranking.
- The spec's order is applied strictly. "Balancing" risk and time means time
  only decides between routes whose weather risk is equal. Each recommendation
  states the deciding factor in plain English.
