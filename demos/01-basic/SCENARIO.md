# Demo 01 — Basic: One week of an engineering team's meetings

A small engineering squad exports one week of their calendar as
`team-week.ics`. It contains four real-world meetings:

| Meeting                     | People | Duration |
|-----------------------------|:------:|:--------:|
| Daily Engineering Standup   |   6    |  0.5 h   |
| Sprint Planning (whole squad) | 8    |  2.0 h   |
| 1:1 Chris / Priya           |   2    |  0.5 h   |
| Monthly All-Hands           |  13    |  1.0 h   |

MEETINGCOST reads the `.ics` directly, counts attendees (ATTENDEE lines plus
the ORGANIZER if not already listed), multiplies person-hours by a blended
hourly rate, and ranks the meetings by total cost.

The blended hourly rate is derived from an average salary:

    rate = (salary / 2080 work-hours) * overhead_multiplier

With the defaults (`--salary 100000 --overhead 1.4`) the rate is
`(100000 / 2080) * 1.4 = $67.31/hr`.

## Run it

Human-readable table (sorted most expensive first):

    python -m meetingcost cost demos/01-basic/team-week.ics

Machine-readable JSON, with a real average salary of $140k:

    python -m meetingcost cost demos/01-basic/team-week.ics \
        --salary 140000 --format json

Pipe a calendar in over stdin:

    cat demos/01-basic/team-week.ics | python -m meetingcost cost -

## What you'll see

The All-Hands and Sprint Planning dominate the bill — 13 people for an hour
and 8 people for two hours are the expensive line items, while the 1:1 is the
cheapest. That ranking is the whole point: it tells you which recurring
meeting to shrink or kill first.

`--version` prints the tool version; a calendar with no parseable events
exits non-zero with an error on stderr.
