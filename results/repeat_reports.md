# Repeat reports in NYC 311, March 2026

Rule: a ticket is a **repeat** when an earlier ticket with the same agency, complaint type and building address (house number, street, borough) was still open when it came in. Street-name-only addresses are never matched. The 24-hour variant (earlier ticket within 24 hours, open or not) is shown for comparison.

- Tickets: 342,390; repeats: **57,948 (16.9%)**; distinct issues: 284,442.
- 24-hour variant: 68,276 repeats (19.9%).

## 1. Check against the agencies' own duplicate flags

Complaint types where the agency marked at least 5% of tickets (and 100+ tickets) as duplicates. They cover 22,056 of the 22,175 agency flags. *Recall* = share of the agency's flags the rule also finds; *precision* = share of the rule's repeats the agency also flagged.

| Agency | Complaint type | Tickets | Agency flags | …with an address | Rule: open → repeats | Recall | Recall (flags with an address) | Precision | Rule: 24h → repeats | Recall | Precision |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| HPD | HEAT/HOT WATER | 29,783 | 8,126 | 8,126 | 15,848 | 97.5% | 97.5% | 50.0% | 12,941 | 89.5% | 56.2% |
| DOT | Street Condition | 28,629 | 9,787 | 32 | 387 | 0.1% | 15.6% | 1.3% | 252 | 0.0% | 0.0% |
| HPD | PLUMBING | 6,927 | 363 | 363 | 3,087 | 95.0% | 95.0% | 11.2% | 2,293 | 85.7% | 13.6% |
| DEP | Noise | 5,990 | 1,176 | 1,010 | 1,213 | 40.6% | 47.3% | 39.4% | 904 | 31.0% | 40.4% |
| DEP | Water System | 5,463 | 2,247 | 1,656 | 593 | 22.7% | 30.7% | 85.8% | 494 | 18.9% | 86.0% |
| HPD | GENERAL | 3,469 | 357 | 357 | 1,269 | 85.4% | 85.4% | 24.0% | 770 | 53.5% | 24.8% |

Across these types the open rule finds 9,563 of the 22,056 agency flags (43.4%). Flags on tickets with no address can't be found by an address-based rule.

### HPD HEAT/HOT WATER: repeats the agency didn't mark as duplicates

7,927 tickets. Most common resolution texts (first 90 characters):

| Tickets | Resolution text starts with |
|---:|---|
| 3,040 | The Department of Housing Preservation and Development conducted or attempted to conduct a… |
| 1,381 | The Department of Housing Preservation and Development contacted a tenant in the building… |
| 1,034 | HPD responded to a complaint of no heat or hot water in the building. An occupant of the b… |
| 861 | HPD called the telephone number on file for this complaint.  Someone at that number indica… |
| 798 | The following complaint conditions are still open. HPD has already attempted to notify the… |

## 2. Repeat share by agency

| Agency | Tickets | Repeats (open rule) | Share | Agency duplicate flags |
|---|---:|---:|---:|---:|
| NYPD | 139,705 | 15,041 | 10.8% | 0 |
| HPD | 74,386 | 33,003 | 44.4% | 8,858 |
| DOT | 46,417 | 676 | 1.5% | 9,787 |
| DSNY | 28,814 | 1,626 | 5.6% | 0 |
| DEP | 17,272 | 2,125 | 12.3% | 3,508 |
| DOB | 11,079 | 1,771 | 16.0% | 0 |
| DPR | 7,652 | 1,037 | 13.6% | 0 |
| DOHMH | 6,824 | 930 | 13.6% | 0 |
| DHS | 3,613 | 463 | 12.8% | 0 |
| TLC | 3,345 | 356 | 10.6% | 11 |

## 3. The 15 largest complaint types

![Repeat share by complaint type](charts/01_repeat_share_by_type.png)

| Agency | Complaint type | Tickets | With address | Repeats | Share | Distinct issues | Agency flags |
|---|---|---:|---:|---:|---:|---:|---:|
| NYPD | Illegal Parking | 54,104 | 50,216 | 3,106 | 5.7% | 50,998 | 0 |
| NYPD | Noise - Residential | 31,823 | 31,611 | 6,527 | 20.5% | 25,296 | 0 |
| HPD | HEAT/HOT WATER | 29,783 | 29,783 | 15,848 | 53.2% | 13,935 | 8,126 |
| DOT | Street Condition | 28,629 | 3,973 | 387 | 1.4% | 28,242 | 9,787 |
| NYPD | Blocked Driveway | 16,388 | 16,252 | 1,223 | 7.5% | 15,165 | 0 |
| NYPD | Noise - Street/Sidewalk | 10,865 | 9,759 | 1,784 | 16.4% | 9,081 | 0 |
| HPD | UNSANITARY CONDITION | 10,355 | 10,355 | 4,626 | 44.7% | 5,729 | 0 |
| DSNY | Dirty Condition | 7,826 | 7,356 | 552 | 7.1% | 7,274 | 0 |
| NYPD | Abandoned Vehicle | 7,660 | 7,055 | 465 | 6.1% | 7,195 | 0 |
| DOT | Traffic Signal Condition | 7,075 | 1 | 0 | 0.0% | 7,075 | 0 |
| HPD | PLUMBING | 6,927 | 6,927 | 3,087 | 44.6% | 3,840 | 363 |
| HPD | PAINT/PLASTER | 6,014 | 6,014 | 2,612 | 43.4% | 3,402 | 0 |
| DEP | Noise | 5,990 | 5,349 | 1,213 | 20.3% | 4,777 | 1,176 |
| DEP | Water System | 5,463 | 4,497 | 593 | 10.9% | 4,870 | 2,247 |
| NYPD | Noise - Commercial | 5,199 | 5,081 | 885 | 17.0% | 4,314 | 0 |

Full table for every agency and complaint type: [`repeat_reports.csv`](repeat_reports.csv).
