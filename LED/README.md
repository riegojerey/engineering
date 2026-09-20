# LED indicator — 9 V, single LED

Status: **schematic and PCB complete, ERC and DRC clean.** Not yet sourced
(fixes 6–9 below) and not yet fabbed.

## Design

Chain: `BT1+ → R1 → D2 (A→K) → D1 (A→K) → GND (BT1−)`

| Ref | Part | Value | Footprint |
|-----|------|-------|-----------|
| BT1 | 9 V PP3 battery holder | `9V` | `Battery:BatteryHolder_MPD_BA9VPC_1xPP3` |
| R1  | current-limiting resistor | `620` | `Resistor_SMD:R_0805_2012Metric` |
| D2  | series reverse-polarity protection | `1N4148W` | `Diode_SMD:D_SOD-123` |
| D1  | indicator LED | `LED` | `LED_SMD:LED_0805_2012Metric` |

`R1 = (Vbat − Vf_LED − Vf_D2) / I = (9 − 2.0 − 0.7) / 620 ≈ 10.2 mA`, and the
SPICE `.op` run gives **10.14 mA** with **64 mW** in R1. Vf is assumed for a red
LED; a blue/white part (Vf 3.2) gives 8.2 mA at 620 Ω, or use 510 Ω for 10 mA.
**Do not fit 47 Ω**: with D2 forward that is 133 mA and 828 mW in R1.

D2 is deliberate, not leftover. It blocks a reversed battery instead of
destroying the LED, and a series diode is the right choice for an unfused
battery loop (a shunt diode would dead-short the pack). It costs 0.7 V by
design and R1 is sized with that drop included. Neither D2 nor D1 may be
flipped: a reversed D2 makes the circuit an open circuit.

## Board

66 × 44 mm, 2 layers, ground pour on B.Cu, one via. The size is set by the PP3
holder (56 × 33 mm), not by the circuit.

Routing: chain parts in a row at y = 38 mm; `Net-(BT1-+)` runs down the left
board margin (x = 1.8 mm) to stay clear of the holder; D1's cathode reaches the
B.Cu pour through one via at (33, 38).

One deliberate trade-off: ~2.5 mm of the `Net-(BT1-+)` segment leaves pad 1 at
y = 11 mm inside the holder's outline. The holder lifts the cell off the board
and that area is covered by holder plastic, so it is electrically safe. If you
want literally zero copper under the holder, run that segment on B.Cu instead —
pad 1 is THT so it already exists there — and bring it back up with a via next
to R1 pad 1.

## Verification

| Check | Command | Result |
|-------|---------|--------|
| ERC | `kicad-cli sch erc LED.kicad_sch` | 0 errors (7 warnings, all environmental `lib_symbol_issues` — this box has no `sym-lib-table`, the symbols are embedded in the sheet) |
| DRC | `kicad-cli pcb drc --schematic-parity --severity-all LED.kicad_pcb` | **0 violations, 0 unconnected, 0 parity issues** |
| DRC rules live | mutated copy with a 0.10 mm track | correctly flagged `track_width` + `clearance` |
| Netlist parity | `kicad-cli sch export netlist` + `--schematic-parity` | board matches schematic exactly |
| Current | `ngspice -b` on the equivalent netlist | 10.14 mA, 64 mW in R1 |

DRC rules in `LED.kicad_pro` are set to a JLCPCB-comfortable floor:
min track 0.2 mm, min clearance 0.2 mm, min via 0.6/0.3 mm, copper-to-edge 0.5 mm.
The project shipped with `min_clearance: 0.0` and `min_track_width: 0.0`, which
made a passing DRC meaningless.

## 2026-09-20 review fixes applied (items 1–5)

1. **One canonical design.** The broken original is quarantined as
   `archive/LED-original-broken.*` (D2 reversed → open circuit, 47 Ω resistor,
   `10V` on a 1.5 V cell symbol, no footprints). `LED.*` is now the corrected
   design, formerly named `LED-revised`.
2. **D2 kept at 90°** (forward) and documented on the sheet with a text note
   explaining its purpose and that its polarity is load-bearing.
3. **R1 kept at 620 Ω** and documented on the sheet with the sizing formula.
4. **Battery fixed**: `Device:Battery_Cell` (a 1.5 V cell) replaced with
   `Device:Battery` (multi-cell), value `9V`, with a real PP3 holder footprint.
   The GND symbol and PWR_FLAG moved to the new pin-2 position, so the netlist
   is unchanged from the corrected revision.
5. **Board built, routed, DRC'd** — from an empty 78-byte stub to a real
   2-layer board, with footprints on all four parts.

## Open items

- **Fix 6 — sourcing/MPN (`SS-001`, `DS-001`)**: still 0/4 BOM lines have an
  MPN and there is no `datasheets/` directory. Run the `digikey`/`lcsc` skills
  and write MPNs into the symbol properties.
- **Fix 3 follow-up**: revisit R1 if the LED colour changes from red.
- **Fix 8 — title block** is still empty in the schematic (no title/rev/date).
- **Fix 9 — backup housekeeping**: `LED-backups/LED-2026-09-20_092742.zip`
  contains a stale `~LED.kicad_sch.lck` and a third schematic variant (20,572 B)
  matching neither file on disk.
- **Fabrication outputs** (gerbers, drill, CPL) have not been generated.
- **Fiducials / test points**: `FD-001` and `TE-001` flag these. Only needed if
  you machine-assemble or test this board at volume; hand assembly doesn't need
  them.
- **`LR-001` is a false positive and will keep appearing.** The analyzer reports
  "LED D1: no current-limiting resistor found" on this design. R1 *is* in series
  (battery+ → R1 → D2 → D1 → GND, confirmed by netlist). The detector
  (`skills/kicad/scripts/validation_detectors.py`, `validate_led_resistors`) only
  recognises a resistor that shares a net directly with the LED *and* whose other
  terminal is on a net whose name parses as a power/ground rail. D2 breaks the
  adjacency and the battery net is unnamed (`Net-(BT1-+)`), so it falls into the
  "no resistor at all" branch — while the branch that would catch a genuine
  overcurrent never runs. No detector in the pack evaluates diode orientation or
  DC path continuity, which is why the reversed-D2 original and the working board
  produced identical finding sets.

## KiCad traps hit while doing this

- **Two `.kicad_pro` files in one directory silently redirect analysis.** Name a
  file and the analyzer resolves the project root instead, describing a
  different board with full confidence. Never keep two projects in one folder.
- **`ZONE_FILLER.Fill()` segfaults on a `CreateEmptyBoard()` board** but works on
  a board loaded back from disk. Build → save → reload → fill → save.
- **`PCB_VIA.SetWidth()` in KiCad 9 takes an explicit layer.** A bare call trips a
  C++ assert and kills the process before anything is written.
- **`FootprintLoad()` sets only the item name**, so the library nickname has to be
  restored with `SetFPID()` or `DRC --schematic-parity` reports a
  `footprint_symbol_mismatch` on every part.
- **Writing a board whose project pcbnew does not hold rewrites the sibling
  `.kicad_pro` with in-memory defaults**, resetting the design rules to
  `min_clearance: 0.0` / `min_track_width: 0.0`. Apply rule changes *after* any
  board build, and read them back.
