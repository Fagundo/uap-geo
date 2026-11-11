# Future work

Ideas raised during analysis and parked. Each would be a new pre-registered hypothesis tested on
data not yet used for that question (for most, the 2021+ holdout or newly obtained reports).

## Launch nights beyond the rocket window (from H-launch-01)

Twilight launch nights are elevated over the whole night, not only in the 90 minutes after liftoff.
Test whether launch nights still show excess reports once reports within the launch window are
removed. Expect some residual from late filing and wrong report times, so the test needs a null
for that (for example, reports timed before liftoff on the same night).

Related: turn the launch-window match into a high-confidence filter rule (reports within 90 minutes
after a twilight launch within 1,200 km), replacing the text-only rocket rule.

## Earthquakes with refined windows (from H-geo-01 diagnostics)

The two decades disagree (see results/H-geo-01/*/diagnostics.md). A follow-up would use the quake's
local night, exclude the quake night, include M >= 3.5 for power, and needs reports from 2024 on.

## Big geomagnetic storms (from H-geo-01 diagnostics)

The Kp >= 8 hint in 2011-2020 rests on three storms and does not replicate in 2001-2010. Worth
revisiting only with reports covering the May and October 2024 storms.

## What the unexplained celebration excess is (from H-celebrate-01)

July 4 and New Year's Eve nights keep a rise of about 2.5x and 1.8x after removing lantern, fireworks
and fire-coloured-light wording. Read a sample of those reports to see what they describe
(undescribed lanterns, drones, aircraft, other), and consider a text classifier for the unexplained
tier instead of word lists.

## Persistence refinements (from H-persist-01)

The 2001-2020 watch list is still led by hotel-tourism beach counties (the seasonal-housing control
catches vacation homes, not hotel stays) and by small Virginia independent cities, whose reports are
named for the city while nearby residents are counted in the surrounding county. Next steps: a
visitor-volume control (lodging tax or hotel occupancy by county), merging Virginia independent
cities into their surrounding counties, the 2011-2020 -> 2021-2023 holdout check, and a forecasting
version that scores counties by prior excess and measures ranking accuracy on later years.
