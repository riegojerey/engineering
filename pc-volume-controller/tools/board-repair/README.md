# Board repair scripts — pc-volume-controller

These five scripts are the **working record** of the EMC/DFM repair applied to
`pc-volume-controller.kicad_pcb`. They are kept because the committed board
diff is roughly 7,400 lines of s-expression and cannot be reviewed by eye —
this is the readable account of what changed, where, and why.

> **They are a record, not a toolkit. Do not re-run them.**
> `fix_review_items.py` has no "already applied?" guard: running it again would
> add a *second* set of copper pours, fiducials and stitching vias. The scripts
> mutate `pc-volume-controller.kicad_pcb` in place, and their result is already
> committed. The absolute path to the board is hardcoded at the top of each one.

## Why they exist

The board was run through a design review — schematic, PCB, EMC and
cross-analysis. Five findings were fixed. The scripts below are the edits.

## Order of execution

| # | Script | Ran | What it did | Finding closed |
|---|--------|-----|-------------|----------------|
| 1 | `fix_review_items.py` | 12:49 | GND pours on F.Cu and B.Cu (0.5 mm edge inset, 0.25 mm clearance, thermal reliefs) plus 26 validated stitching vias; moved the six via-in-pad vias off the C1–C6 pads from y=23.50 to y=21.50 with 0.4 mm F.Cu stubs; added three `Fiducial_1mm_Mask2mm` on F.Cu | `GP-002`, `VS-002`, `VP-001` ×6, `FD-001` |
| 2 | `drc_repair.py` | 12:50 | DRC found 3 new errors — each fiducial's 2 mm mask aperture exposed the GND pour beneath it while the pad carried no net. Bound the fiducials to GND. Also retargeted a `+5V` track whose only connection at y=23.50 had been the via that moved. | mask-bridge ×3, dangling track end |
| 3 | `drc_repair2.py` | 12:52 | Repair of pass 2. Pass 2 had retargeted **both** endpoints sitting at y=23.50 — including the F.Cu stub's pad-side end — collapsing it to zero length and severing `+5V` from C6 pad 1. Also relocated the fiducials away from RV1's reference text, whose silk was being clipped. | `unconnected_items` ×1, silk-over-mask ×1 |
| 4 | `drc_repair3.py` | 12:52 | Repair of pass 3, which relocated a stitching via to (34, 50.5) without checking the via already at (34, 51.0) — 0.5 mm away, under the hole-to-hole minimum. | `hole_to_hole` ×1 |
| 5 | `fix_rp001.py` | 13:20 | A 0.6 mm ground via within 0.95 mm of each of the **ten** `/VOL*` signal layer transitions (five nets × two transitions each). | `RP-001` ×5 |

**Passes 2, 3 and 4 exist because of mistakes made in the preceding pass and
caught by `kicad-cli pcb drc`.** That is deliberate: the trail is left visible
rather than tidied into a single suspiciously clean script. The timestamps show
four passes in three minutes, each one reacting to what DRC reported. Only
pass 5 is a planned change rather than a correction.

## Geometry rules used

Read from the board's own settings, not assumed:

| Rule | Value |
|------|-------|
| Netclass `Default` clearance | 0.2 mm |
| Netclass `Default` via | 0.6 mm / 0.3 mm drill |
| `min_hole_to_hole` | 0.25 mm |
| `min_via_diameter` | 0.5 mm |
| `min_copper_edge_clearance` | 0.5 mm |
| KiCad 9 API note | `FOOTPRINT.SetReferenceTextSize` does not exist; use `fp.Reference().SetVisible(False)` |

Two `pcbnew` traps worth knowing before writing anything similar:

- **`board.Remove()` invalidates the SWIG proxy.** Every later `GetTracks()`,
  `GetNetInfo()` or `Zones()` call raises. These scripts never remove —
  clashing vias are *relocated* — and read the GND netcode before mutating.
- **`GetPosition()` returns a live reference.** `SetPosition()` mutates the
  object already read, so a printed "before" value can silently show the
  "after". Copy coordinates out as floats immediately.

## Result

Verified after all five passes:

- **DRC**: 1 violation — a pre-existing cosmetic `lib_footprint_mismatch` on U1
  (also present before any of these scripts ran), 0 unconnected items,
  0 schematic-parity differences
- **ERC**: 0 violations
- **EMC** pre-compliance score: 86.5 → 95.5, findings 10 → 5
- Ground stitching vias: 0 → 36

The human-readable outcome is in `../../fabrication/ORDERING.md` under
"Design-review fixes applied".

## Reusing these

They are not portable as written. To adapt one: change the `PCB` constant at
the top, read the geometry rules out of the target board's own
`.kicad_pro`, and confirm every placement against DRC on a **copy** first —
and keep a pre-change baseline so violations you introduce can be told apart
from ones that were already there.
