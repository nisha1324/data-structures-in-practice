# Repeat reports in NYC 311, March 2026

Rule: a ticket is a **repeat** when an earlier ticket with the same agency, complaint type and normalised address was still open when it came in. The 24-hour variant (earlier ticket within 24 hours, open or not) is shown for comparison.

- Tickets: 342,390; repeats: **72,098 (21.1%)**; distinct issues: 270,292.
- 24-hour variant: 78,832 repeats (23.0%).

## 1. Check against the agencies' own duplicate flags

Complaint types where the agency marked at least 5% of tickets (and 100+ tickets) as duplicates. They cover 22,056 of the 22,175 agency flags. *Recall* = share of the agency's flags the rule also finds; *precision* = share of the rule's repeats the agency also flagged.

| Agency | Complaint type | Tickets | Agency flags | …with an address | Rule: open → repeats | Recall | Precision | Rule: 24h → repeats | Recall | Precision |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| HPD | HEAT/HOT WATER | 29,783 | 8,126 | 8,126 | 15,851 | 97.5% | 50.0% | 12,942 | 89.5% | 56.2% |
| DOT | Street Condition | 28,629 | 9,787 | 6,051 | 12,314 | 56.8% | 45.1% | 7,892 | 38.9% | 48.2% |
| HPD | PLUMBING | 6,927 | 363 | 363 | 3,089 | 95.0% | 11.2% | 2,294 | 85.7% | 13.6% |
| DEP | Noise | 5,990 | 1,176 | 1,044 | 1,224 | 41.1% | 39.5% | 912 | 31.4% | 40.5% |
| DEP | Water System | 5,463 | 2,247 | 1,714 | 597 | 22.8% | 85.8% | 505 | 19.3% | 85.9% |
| HPD | GENERAL | 3,469 | 357 | 357 | 1,269 | 85.4% | 24.0% | 770 | 53.5% | 24.8% |

Across these types the open rule finds 15,125 of the 22,056 agency flags (68.6%). Flags on tickets with no address can't be found by an address-based rule.

### HPD HEAT/HOT WATER: repeats the agency didn't mark as duplicates

7,930 tickets. Most common resolution texts (first 90 characters):

| Tickets | Resolution text starts with |
|---:|---|
| 3,040 | The Department of Housing Preservation and Development conducted or attempted to conduct a… |
| 1,381 | The Department of Housing Preservation and Development contacted a tenant in the building… |
| 1,035 | HPD responded to a complaint of no heat or hot water in the building. An occupant of the b… |
| 862 | HPD called the telephone number on file for this complaint.  Someone at that number indica… |
| 799 | The following complaint conditions are still open. HPD has already attempted to notify the… |

## 2. Repeat share by agency

| Agency | Tickets | Repeats (open rule) | Share | Agency duplicate flags |
|---|---:|---:|---:|---:|
| NYPD | 139,705 | 15,646 | 11.2% | 0 |
| HPD | 74,386 | 33,008 | 44.4% | 8,858 |
| DOT | 46,417 | 12,939 | 27.9% | 9,787 |
| DSNY | 28,814 | 1,856 | 6.4% | 0 |
| DEP | 17,272 | 2,142 | 12.4% | 3,508 |
| DOB | 11,079 | 1,776 | 16.0% | 0 |
| DPR | 7,652 | 1,250 | 16.3% | 0 |
| DOHMH | 6,824 | 936 | 13.7% | 0 |
| DHS | 3,613 | 594 | 16.4% | 0 |
| TLC | 3,345 | 1,009 | 30.2% | 11 |

## 3. The 15 largest complaint types

![Repeat share by complaint type](charts/01_repeat_share_by_type.png)

| Agency | Complaint type | Tickets | With address | Repeats | Share | Distinct issues | Agency flags |
|---|---|---:|---:|---:|---:|---:|---:|
| NYPD | Illegal Parking | 54,104 | 54,104 | 3,404 | 6.3% | 50,700 | 0 |
| NYPD | Noise - Residential | 31,823 | 31,823 | 6,537 | 20.5% | 25,286 | 0 |
| HPD | HEAT/HOT WATER | 29,783 | 29,783 | 15,851 | 53.2% | 13,932 | 8,126 |
| DOT | Street Condition | 28,629 | 19,752 | 12,314 | 43.0% | 16,315 | 9,787 |
| NYPD | Blocked Driveway | 16,388 | 16,388 | 1,223 | 7.5% | 15,165 | 0 |
| NYPD | Noise - Street/Sidewalk | 10,865 | 10,865 | 1,942 | 17.9% | 8,923 | 0 |
| HPD | UNSANITARY CONDITION | 10,355 | 10,355 | 4,626 | 44.7% | 5,729 | 0 |
| DSNY | Dirty Condition | 7,826 | 7,826 | 586 | 7.5% | 7,240 | 0 |
| NYPD | Abandoned Vehicle | 7,660 | 7,654 | 500 | 6.5% | 7,160 | 0 |
| DOT | Traffic Signal Condition | 7,075 | 23 | 6 | 0.1% | 7,069 | 0 |
| HPD | PLUMBING | 6,927 | 6,927 | 3,089 | 44.6% | 3,838 | 363 |
| HPD | PAINT/PLASTER | 6,014 | 6,014 | 2,612 | 43.4% | 3,402 | 0 |
| DEP | Noise | 5,990 | 5,442 | 1,224 | 20.4% | 4,766 | 1,176 |
| DEP | Water System | 5,463 | 4,582 | 597 | 10.9% | 4,866 | 2,247 |
| NYPD | Noise - Commercial | 5,199 | 5,199 | 888 | 17.1% | 4,311 | 0 |

Full table for every agency and complaint type: [`repeat_reports.csv`](repeat_reports.csv).
