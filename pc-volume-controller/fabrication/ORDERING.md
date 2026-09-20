# JLCPCB ordering notes — pc-volume-controller

Generated from the KiCad 9 project. Re-generate with the commands in
"Regenerating" below; every figure here comes from the design files, not from
memory.

## Board spec for the JLCPCB quote form

| Field | Value |
|---|---|
| Dimensions | 98 x 54 mm |
| Layers | 2 |
| Thickness | 1.6 mm |
| Material | FR-4 |
| Min track / clearance | 0.40 mm / 0.20 mm |
| Min drill | 0.40 mm (vias), 1.00 mm (component leads) |
| Surface finish | HASL (cheapest; fine for THT hand soldering) |
| Edge connector / impedance control | none |
| Gold fingers | none |

Every one of those sits **inside JLCPCB's cheapest standard 2-layer tier**
(their minimum is 0.127 mm track/space and 0.30 mm drill), so the board itself
should quote at the lowest price band. Board area is 5,292 mm².

## Files to upload

| File | Use |
|---|---|
| `pc-volume-controller-gerbers.zip` | Gerbers + Excellon drill. Upload as the PCB. |
| `pc-volume-controller-jlcpcb-bom.csv` | BOM, in JLCPCB's column format. |
| `pc-volume-controller-jlcpcb-cpl.csv` | Pick-and-place, SMD parts only. |
| `pc-volume-controller-bom-raw.csv` | Reference BOM as KiCad exported it. |

The gerber zip contains exactly: F_Cu, B_Cu, F_Mask, B_Mask, F_Silkscreen,
B_Silkscreen, Edge_Cuts, plus PTH and NPTH drill files. Drill maps and the
`.gbrjob` are deliberately excluded — JLCPCB does not want them.

## What is actually on this board

| Ref | Value | Package | Mounting | LCSC |
|---|---|---|---|---|
| C1–C6 | 100 nF 50 V X7R | 0805 | SMD | `C49678` — **verified** |
| RV1–RV5 | 10 kΩ linear | 9 mm panel pot | through-hole | **not verified** |
| U1 | Arduino Nano v3.x | module, 30 pins | through-hole | **not verified** |
| H1–H4 | M3 mounting holes | 3.2 mm NPTH | — | not a part |

`C49678` is YAGEO `CC0805KRX7R9BB104`, 100 nF 50 V X7R ±10 % 0805 — confirmed
against JLCPCB's and LCSC's own part pages.

## Read this before you choose assembly

**Only 6 components on this board are SMD.** The other six are through-hole:
five panel-mount potentiometers and the Nano module. That single fact decides
the whole cost question.

1. **SMT-only assembly is the worst option here.** You would pay the stencil
   fee plus the PCBA order minimum to have a machine place about ten cents of
   capacitors — and you would *still* hand-solder the pots and the Nano.
2. **THT assembly is available on Economic PCBA**, not just Standard. JLCPCB
   wave-solders through-hole parts; there is a one-time charge of roughly
   $3.50 for the first THT part plus roughly $0.02 per joint. Expect ~45 THT
   joints here.
3. **The Nano module is the risk.** JLCPCB's library does list Nano V3 modules
   (`C9900187880`, `C9900175652`), but there is widely repeated community
   guidance that pre-built module footprints cannot be assembled. This is
   unresolved — confirm with JLCPCB support *before* designing around it.
4. **The potentiometers are a mechanical choice, not an electrical one.**
   They must match your enclosure and knobs, so pick the exact part first and
   read its LCSC code off the product page. It is not safe to substitute
   silently: the PCB footprint is for an Alpha RD901F-40-00D vertical.

### Cheapest path, in order

1. **Bare PCB + hand assembly.** Order the board, buy the parts, solder. Only
   six through-hole components beyond the caps — a short job. This is almost
   always cheapest at hobbyist quantities.
2. **Full assembly (SMD *and* THT lines both included).** Only worth it if the
   pot and the Nano are both confirmed available and assembliable.
3. **SMD-only assembly.** Don't. See point 1 above.

Cost figures above are order-of-magnitude only — pricing changes and the exact
quote depends on quantity and options. Get the live figure from JLCPCB's
calculator before committing.

## Two things to check on JLCPCB's site

1. **The placement preview.** `Mid X/Mid Y` in the CPL are expressed in the
   **same coordinate frame as the Gerbers** — KiCad writes the board at
   Y = −54…0 mm with the origin at the top-left, and the drill file confirms it
   (the via at board (3.55, 23.5) appears as `X3.55Y-23.5`). JLCPCB requires the
   CPL to share the Gerber origin, so that is what is shipped. **Verify against
   JLCPCB's on-screen preview anyway** — it is free and it is the ground truth.
   If parts look mirrored or shifted, the Y convention is the thing to flip.
2. **The part-type flag on the BOM lines.** Confirm `C49678` is flagged
   *Basic* (no extended-part fee). Confirm the pot and Nano lines have a real
   LCSC number filled in before you submit; an empty LCSC cell cannot be
   assembled.

## Good news on orientation

All six SMD parts are non-polarised 0805 capacitors, so a CPL rotation error
cannot damage anything — the worst case is a 90° part rotation that electrically
still works. There are no diodes, electrolytics, ICs or connectors on the SMD
side to get backwards.

## Regenerating

Everything in this folder except the source of truth is produced by one script:

```bash
export KICAD_CONFIG_HOME=/tmp/kicad-cfg      # scratch config; any dir works
cd pc-volume-controller
python3 fabrication/make_jlcpcb_outputs.py .
```

It runs `kicad-cli` for the gerbers, drill, position and BOM exports, then
converts them into JLCPCB's column formats and audits the board against
JLCPCB's cheapest 2-layer tier. Stdlib only — no packages to install.

The `.kicad_pcb` and `.kicad_sch` are the source of truth. If you change
either, re-run the script and re-run DRC:

```bash
kicad-cli pcb drc --severity-all pc-volume-controller.kicad_pcb
kicad-cli sch erc --severity-all pc-volume-controller.kicad_sch
```

Current state: **0 DRC violations** (one cosmetic `lib_footprint_mismatch`
warning on U1, because KiCad's library comparison does not account for the
Nano's 90° rotation), 0 unconnected items, 0 schematic-parity differences, and
**0 ERC violations**.
