# Repeat hot spots in NYC 311, March 2026

A *repeat* is a ticket filed while an earlier ticket for the same agency, complaint type and building address was still open (Part 1). Here repeats are counted per agency and address, across complaint types. Street names only: house numbers are left out of this report.

- Repeats: 57,948 at 17,276 agency-address pairs (out of 135,720 pairs with a matchable ticket).
- Top 10 per agency found with one size-10 heap per agency in a single pass over the counts; the top 1% with one heap per agency sized to 1% of its addresses.

## 1. Concentration by agency

![Hot-spot concentration](charts/03_hot_spot_concentration.png)

| Agency | Repeats | Addresses | …with a repeat | Top 1% of addresses | Their repeats | Share | Top 10 addresses' share | Top address's share |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| HPD | 33,003 | 15,056 | 6,721 | 151 | 8,689 | **26.3%** | 6.3% | 1.4% |
| NYPD | 15,041 | 58,420 | 5,532 | 585 | 8,483 | **56.4%** | 20.5% | 10.1% |
| DEP | 2,125 | 10,798 | 1,047 | 108 | 932 | **43.9%** | 19.9% | 4.6% |
| DOB | 1,771 | 7,793 | 833 | 78 | 703 | **39.7%** | 12.6% | 1.8% |
| DSNY | 1,626 | 19,875 | 1,091 | 199 | 702 | **43.2%** | 12.2% | 4.2% |
| DPR | 1,037 | 4,722 | 454 | 48 | 494 | **47.6%** | 29.0% | 10.0% |
| DOHMH | 930 | 4,838 | 421 | 49 | 415 | **44.6%** | 20.6% | 4.8% |
| DOT | 676 | 8,640 | 484 | 87 | 264 | **39.1%** | 11.2% | 1.9% |

## 2. Top 10 addresses per agency

*Main complaint* is the most common complaint type / descriptor among all of the address's tickets for that agency, with its share. *Days* = days in March with at least one ticket there.

### HPD

| # | Street (no house number) | Repeats | Tickets | Days | Main complaint | Share | Agency dup flags |
|---:|---|---:|---:|---:|---|---:|---:|
| 1 | EAST 217 STREET, BRONX | 461 | 471 | 22 | HEAT/HOT WATER / APARTMENT ONLY | 100.0% | 251 |
| 2 | CRESTON AVENUE, BRONX | 360 | 372 | 31 | HEAT/HOT WATER / ENTIRE BUILDING | 96.2% | 170 |
| 3 | WOODYCREST AVENUE, BRONX | 216 | 242 | 31 | UNSANITARY CONDITION / GARBAGE/RECYCLING STORAGE | 46.7% | 17 |
| 4 | CENTRAL PARK NORTH, MANHATTAN | 173 | 177 | 29 | HEAT/HOT WATER / ENTIRE BUILDING | 98.9% | 62 |
| 5 | EXTERIOR STREET, BRONX | 171 | 176 | 4 | PLUMBING / WATER SUPPLY | 81.8% | 118 |
| 6 | EAST 242 STREET, BRONX | 163 | 171 | 25 | HEAT/HOT WATER / ENTIRE BUILDING | 74.9% | 54 |
| 7 | STUYVESANT PLACE, STATEN ISLAND | 146 | 166 | 16 | HEAT/HOT WATER / ENTIRE BUILDING | 32.5% | 30 |
| 8 | PACIFIC STREET, BROOKLYN | 136 | 152 | 12 | FLOORING/STAIRS / FLOOR | 13.8% | 4 |
| 9 | SEAMAN AVENUE, MANHATTAN | 129 | 142 | 17 | PAINT/PLASTER / WALL | 12.7% | 0 |
| 10 | SHAKESPEARE AVENUE, BRONX | 125 | 161 | 18 | FLOORING/STAIRS / FLOOR | 19.3% | 4 |

### NYPD

| # | Street (no house number) | Repeats | Tickets | Days | Main complaint | Share | Agency dup flags |
|---:|---|---:|---:|---:|---|---:|---:|
| 1 | EAST 230 STREET, BRONX | 1,526 | 1,596 | 9 | Noise - Residential / Loud Music/Party | 99.6% | 0 |
| 2 | 83 STREET, BROOKLYN | 325 | 746 | 31 | Noise - Residential / Banging/Pounding | 99.2% | 0 |
| 3 | PARSONS BOULEVARD, QUEENS | 296 | 697 | 29 | Noise - House of Worship / Loud Talking | 21.7% | 0 |
| 4 | 159 STREET, QUEENS | 208 | 629 | 31 | Noise - Street/Sidewalk / Loud Music/Party | 99.7% | 0 |
| 5 | WILLETS POINT BOULEVARD, QUEENS | 204 | 221 | 7 | Noise - Street/Sidewalk / Loud Music/Party | 98.2% | 0 |
| 6 | EAST 27 STREET, MANHATTAN | 129 | 270 | 31 | Noise - Residential / Banging/Pounding | 99.6% | 0 |
| 7 | WASHINGTON AVENUE, BRONX | 123 | 269 | 31 | Noise - Residential / Loud Music/Party | 64.3% | 0 |
| 8 | MONROE AVENUE, BRONX | 93 | 141 | 25 | Noise - Residential / Banging/Pounding | 87.9% | 0 |
| 9 | AMSTERDAM AVENUE, MANHATTAN | 91 | 117 | 12 | Noise - Commercial / Loud Music/Party | 88.9% | 0 |
| 10 | 164 STREET, QUEENS | 88 | 374 | 31 | Noise - Vehicle / Car/Truck Horn | 60.7% | 0 |

### DEP

| # | Street (no house number) | Repeats | Tickets | Days | Main complaint | Share | Agency dup flags |
|---:|---|---:|---:|---:|---|---:|---:|
| 1 | 10 AVENUE, MANHATTAN | 98 | 99 | 11 | Noise / Noise, Barking Dog (NR5) | 100.0% | 0 |
| 2 | 8 AVENUE, MANHATTAN | 94 | 99 | 12 | Air Quality / Air: Odor/Fumes, Vehicle Idling (AD3) | 100.0% | 7 |
| 3 | PARSONS BOULEVARD, QUEENS | 84 | 97 | 20 | Noise / Noise: Alarms (NR3) | 99.0% | 14 |
| 4 | JEFFERSON STREET, BROOKLYN | 29 | 33 | 23 | Noise / Noise, Barking Dog (NR5) | 100.0% | 32 |
| 5 | 86 STREET, BROOKLYN | 28 | 30 | 3 | Noise / Noise: Construction Before/After Hours (NM1) | 76.7% | 27 |
| 6 | BROADWAY, MANHATTAN | 25 | 27 | 4 | Noise / Noise: air condition/ventilation equipment (NV1) | 66.7% | 23 |
| 7 | CARROLL STREET, BROOKLYN | 19 | 23 | 12 | Noise / Noise: Construction Before/After Hours (NM1) | 60.9% | 12 |
| 8 | WEST 11 STREET, MANHATTAN | 19 | 22 | 10 | Noise / Noise: Construction Before/After Hours (NM1) | 68.2% | 11 |
| 9 | 1 AVENUE, MANHATTAN | 15 | 17 | 7 | Noise / Noise: Construction Before/After Hours (NM1) | 70.6% | 10 |
| 10 | YORK AVENUE, MANHATTAN | 12 | 14 | 2 | Noise / Noise: Construction Equipment (NC1) | 92.9% | 10 |

### DOB

| # | Street (no house number) | Repeats | Tickets | Days | Main complaint | Share | Agency dup flags |
|---:|---|---:|---:|---:|---|---:|---:|
| 1 | NELSON AVENUE, BRONX | 31 | 40 | 19 | Elevator / Elevator - Multiple Devices On Property | 95.0% | 0 |
| 2 | EAST 163 STREET, BRONX | 31 | 32 | 8 | Elevator / Elevator - Multiple Devices On Property | 100.0% | 0 |
| 3 | HOE AVENUE, BRONX | 28 | 30 | 12 | Elevator / Elevator - Multiple Devices On Property | 100.0% | 0 |
| 4 | WOODYCREST AVENUE, BRONX | 24 | 37 | 20 | Boilers / Boiler - Defective/Inoperative/No Permit | 59.5% | 0 |
| 5 | 86 STREET, BROOKLYN | 24 | 31 | 5 | Emergency Response Team (ERT) / After Hours Work - Illegal | 35.5% | 0 |
| 6 | GRAND CONCOURSE, BRONX | 22 | 24 | 10 | Elevator / Elevator - Single Device On Property/No Alternate Service | 100.0% | 0 |
| 7 | CRANSTON STREET, QUEENS | 19 | 20 | 10 | Building/Use / Illegal Conversion Of Residential Building/Space | 100.0% | 0 |
| 8 | ATLANTIC AVENUE, BROOKLYN | 15 | 19 | 10 | Elevator / Elevator - Single Device On Property/No Alternate Service | 94.7% | 0 |
| 9 | FORT WASHINGTON AVENUE, MANHATTAN | 15 | 21 | 15 | Building/Use / Illegal Conversion Of Residential Building/Space | 47.6% | 0 |
| 10 | WEST 145 STREET, MANHATTAN | 14 | 15 | 10 | Elevator / Elevator - Single Device On Property/No Alternate Service | 100.0% | 0 |

### DSNY

| # | Street (no house number) | Repeats | Tickets | Days | Main complaint | Share | Agency dup flags |
|---:|---|---:|---:|---:|---|---:|---:|
| 1 | WOODYCREST AVENUE, BRONX | 69 | 71 | 28 | Dirty Condition / Trash | 84.5% | 0 |
| 2 | WOODYCREST AVENUE, BRONX | 60 | 62 | 29 | Dirty Condition / Trash | 98.4% | 0 |
| 3 | HUGUENOT AVENUE, STATEN ISLAND | 14 | 21 | 17 | Illegal Posting / Poster or Sign | 47.6% | 0 |
| 4 | 162 STREET, QUEENS | 13 | 14 | 14 | Dirty Condition / Trash | 100.0% | 0 |
| 5 | BROADWAY, MANHATTAN | 8 | 15 | 6 | Vendor Enforcement / Food Vendor | 80.0% | 0 |
| 6 | EAST 173 STREET, BRONX | 8 | 36 | 24 | Dirty Condition / Trash | 100.0% | 0 |
| 7 | ROCKAWAY AVENUE, BROOKLYN | 8 | 12 | 4 | Derelict Vehicles / Derelict Vehicles | 100.0% | 0 |
| 8 | WEST 141 STREET, MANHATTAN | 6 | 11 | 7 | Dirty Condition / Trash | 36.4% | 0 |
| 9 | EAST 112 STREET, MANHATTAN | 6 | 11 | 3 | Dirty Condition / Trash | 36.4% | 0 |
| 10 | VETERANS ROAD WEST, STATEN ISLAND | 6 | 7 | 6 | Dirty Condition / Trash | 100.0% | 0 |

### DPR

| # | Street (no house number) | Repeats | Tickets | Days | Main complaint | Share | Agency dup flags |
|---:|---|---:|---:|---:|---|---:|---:|
| 1 | 5 AVENUE, MANHATTAN | 104 | 116 | 30 | Animal in a Park / Dead Animal | 25.9% | 0 |
| 2 | PROSPECT PARK WEST, BROOKLYN | 71 | 83 | 25 | Animal in a Park / Dog Off Leash | 27.7% | 0 |
| 3 | EAST END AVENUE, MANHATTAN | 20 | 24 | 11 | Maintenance or Facility / Structure - Outdoors | 79.2% | 0 |
| 4 | 19 STREET, QUEENS | 18 | 22 | 14 | Maintenance or Facility / Structure - Outdoors | 50.0% | 0 |
| 5 | IRVING AVENUE, BROOKLYN | 17 | 31 | 11 | Animal in a Park / Dog Off Leash | 41.9% | 0 |
| 6 | JEROME AVENUE, BRONX | 16 | 23 | 19 | Maintenance or Facility / Graffiti or Vandalism | 21.7% | 0 |
| 7 | COMMERCIAL STREET, BROOKLYN | 16 | 48 | 22 | Animal in a Park / Dog Off Leash | 75.0% | 0 |
| 8 | SHORE PARKWAY SR SOUTH, BROOKLYN | 16 | 19 | 11 | Animal in a Park / Dead Animal | 26.3% | 0 |
| 9 | 30 ROAD, QUEENS | 13 | 18 | 6 | Violation of Park Rules / Unsafe Use of Playground | 44.4% | 0 |
| 10 | 45 ROAD, QUEENS | 10 | 12 | 9 | Animal in a Park / Dog Off Leash | 58.3% | 0 |

### DOHMH

| # | Street (no house number) | Repeats | Tickets | Days | Main complaint | Share | Agency dup flags |
|---:|---|---:|---:|---:|---|---:|---:|
| 1 | WOODBINE STREET, BROOKLYN | 45 | 46 | 24 | Smoking or Vaping / Allowed in Smoke Free Area | 100.0% | 0 |
| 2 | STUYVESANT PLACE, STATEN ISLAND | 39 | 42 | 10 | Smoking or Vaping / Allowed in Smoke Free Area | 85.7% | 0 |
| 3 | YORK AVENUE, MANHATTAN | 22 | 23 | 10 | Food Establishment / Pet/Animal | 100.0% | 0 |
| 4 | 45 STREET, QUEENS | 18 | 22 | 9 | Smoking or Vaping / Allowed in Smoke Free Area | 81.8% | 0 |
| 5 | MAIN STREET, MANHATTAN | 13 | 23 | 15 | Smoking or Vaping / Allowed in Smoke Free Area | 60.9% | 0 |
| 6 | OCEAN DRIVE, BROOKLYN | 12 | 16 | 10 | Smoking or Vaping / Allowed in Smoke Free Area | 75.0% | 0 |
| 7 | WOODYCREST AVENUE, BRONX | 11 | 29 | 23 | Rodent / Rat Sighting | 69.0% | 0 |
| 8 | GREENWOOD AVENUE, BROOKLYN | 11 | 16 | 7 | Rodent / Rat Sighting | 62.5% | 0 |
| 9 | 7 AVENUE, MANHATTAN | 11 | 12 | 12 | Mobile Food Vendor / Equipment | 100.0% | 0 |
| 10 | EAST 90 STREET, MANHATTAN | 10 | 13 | 10 | Smoking or Vaping / Allowed in Smoke Free Area | 69.2% | 0 |

### DOT

| # | Street (no house number) | Repeats | Tickets | Days | Main complaint | Share | Agency dup flags |
|---:|---|---:|---:|---:|---|---:|---:|
| 1 | WARREN STREET, MANHATTAN | 13 | 14 | 5 | Street Condition / Plate Condition - Noisy | 50.0% | 0 |
| 2 | 8 STREET, BROOKLYN | 12 | 13 | 4 | Street Condition / Cave-in | 100.0% | 0 |
| 3 | EAST 49 STREET, MANHATTAN | 10 | 13 | 5 | Street Condition / Defective Hardware | 100.0% | 0 |
| 4 | WEST 58 STREET, MANHATTAN | 8 | 9 | 4 | Street Condition / Plate Condition - Noisy | 100.0% | 0 |
| 5 | LEFFERTS BOULEVARD, QUEENS | 6 | 7 | 3 | Street Condition / Cave-in | 85.7% | 0 |
| 6 | COLGATE AVENUE, BRONX | 6 | 17 | 10 | Street Condition / Cave-in | 41.2% | 0 |
| 7 | EAST 14 STREET, MANHATTAN | 6 | 8 | 6 | Street Condition / Plate Condition - Noisy | 75.0% | 0 |
| 8 | EAST 148 STREET, BRONX | 5 | 7 | 7 | Sidewalk Condition / Broken Sidewalk | 100.0% | 0 |
| 9 | MACDOUGAL STREET, MANHATTAN | 5 | 8 | 7 | Outdoor Dining / Sidewalk Zone Blocked | 50.0% | 0 |
| 10 | NASSAU STREET, MANHATTAN | 5 | 9 | 9 | Curb Condition / Broken Curb | 77.8% | 0 |

Full table: [`hot_spots.csv`](hot_spots.csv). Two buildings on the same street show the same label.

## 3. Buildings with repeats for 3+ agencies

113 buildings had repeat tickets for 3 or more agencies. Top 10 by total repeats:

| # | Street (no house number) | Total repeats | Agencies | Repeats by agency |
|---:|---|---:|---:|---|
| 1 | PARSONS BOULEVARD, QUEENS | 388 | 3 | NYPD 296 · DEP 84 · EDC 8 |
| 2 | WOODYCREST AVENUE, BRONX | 315 | 5 | HPD 216 · DSNY 60 · DOB 24 · DOHMH 11 · NYPD 4 |
| 3 | STUYVESANT PLACE, STATEN ISLAND | 238 | 4 | HPD 146 · NYPD 52 · DOHMH 39 · DOB 1 |
| 4 | 10 AVENUE, MANHATTAN | 115 | 3 | DEP 98 · NYPD 14 · DOHMH 3 |
| 5 | 5 AVENUE, MANHATTAN | 111 | 3 | DPR 104 · DOHMH 5 · TLC 2 |
| 6 | CODWISE PLACE, QUEENS | 94 | 3 | HPD 87 · NYPD 4 · DSNY 3 |
| 7 | SCHROEDERS AVENUE, BROOKLYN | 83 | 3 | NYPD 80 · DOHMH 2 · DOT 1 |
| 8 | WOODYCREST AVENUE, BRONX | 82 | 3 | DSNY 69 · DOHMH 10 · NYPD 3 |
| 9 | WEST 148 STREET, MANHATTAN | 81 | 4 | NYPD 57 · HPD 16 · DEP 7 · DOB 1 |
| 10 | EAST 148 STREET, BRONX | 64 | 4 | HPD 53 · DOT 5 · NYPD 3 · DSNY 3 |
