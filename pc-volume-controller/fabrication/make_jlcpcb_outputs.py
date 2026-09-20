#!/usr/bin/env python3
"""Build JLCPCB-format BOM + CPL from a KiCad project, and audit the board
against JLCPCB's cheapest standard 2-layer process tier.

Stdlib only. Requires `kicad-cli` on PATH.

    python3 make_jlcpcb_outputs.py [project_dir]

Writes into <project_dir>/fabrication/:
    <name>-jlcpcb-bom.csv
    <name>-jlcpcb-cpl.csv
    <name>-gerbers.zip
    <name>-bom-raw.csv       (KiCad's own export, for reference)
"""
import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

# LCSC part numbers. Leave a code empty rather than guessing: a wrong LCSC
# number ships the wrong part and no DRC will catch it.
LCSC = {
    "100n":  "C49678",   # YAGEO CC0805KRX7R9BB104, 100nF 50V X7R 0805
    "10k":   "",         # panel pot - must match your enclosure, source it yourself
    "Arduino_Nano_v3.x": "",   # module; availability for assembly unconfirmed
}
PACKAGE = {"100n": "CAP 0805", "10k": "POT THT", "Arduino_Nano_v3.x": "MODULE THT"}

# JLCPCB standard 2-layer, cheapest tier
MIN_TRACK_MM = 0.127
MIN_DRILL_MM = 0.30
MIN_PAD_MM = 0.50
MIN_BOARD_MM = 10.0

LAYERS = "F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts"


def run(args):
    return subprocess.run(args, capture_output=True, text=True)


def audit(pcb_text):
    """Design minimums, read straight out of the board file."""
    tracks = [float(x) for x in re.findall(r"\(segment\b.*?\(width ([0-9.]+)\)", pcb_text, re.S)]
    via_drills = [float(x) for x in re.findall(r"\(via\b.*?\(drill ([0-9.]+)\)", pcb_text, re.S)]
    pad_drills, pad_sizes = [], []
    for m in re.finditer(r"\(pad \S+ \S+ \S+.*?\n(.*?)\n\t*\)", pcb_text, re.S):
        blk = m.group(1)
        d = re.search(r"\(drill (?:oval )?([0-9.]+)", blk)
        if d:
            pad_drills.append(float(d.group(1)))
        s = re.search(r"\(size ([0-9.]+) ([0-9.]+)\)", blk)
        if s:
            pad_sizes += [float(s.group(1)), float(s.group(2))]
    xs, ys = [], []
    for m in re.finditer(r"\(gr_line\b.*?\(start ([0-9.]+) ([0-9.]+)\)\s*\(end ([0-9.]+) ([0-9.]+)\)", pcb_text, re.S):
        xs += [float(m.group(1)), float(m.group(3))]
        ys += [float(m.group(2)), float(m.group(4))]
    W, H = (max(xs) - min(xs)), (max(ys) - min(ys))
    rows = [
        ("board size", f"{W:.0f} x {H:.0f} mm", f">= {MIN_BOARD_MM:.0f} x {MIN_BOARD_MM:.0f} mm",
         W >= MIN_BOARD_MM and H >= MIN_BOARD_MM),
        ("min track width", f"{min(tracks):.3f} mm", f">= {MIN_TRACK_MM} mm", min(tracks) >= MIN_TRACK_MM),
        ("min via drill", f"{min(via_drills):.3f} mm", f">= {MIN_DRILL_MM} mm", min(via_drills) >= MIN_DRILL_MM),
        ("min PTH drill", f"{min(pad_drills):.3f} mm", f">= {MIN_DRILL_MM} mm", min(pad_drills) >= MIN_DRILL_MM),
        ("min pad dimension", f"{min(pad_sizes):.3f} mm", f">= {MIN_PAD_MM} mm", min(pad_sizes) >= MIN_PAD_MM),
    ]
    return rows, W, H


def main():
    proj = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
    name = None
    for f in sorted(os.listdir(proj)):
        if f.endswith(".kicad_pcb"):
            name = f[:-len(".kicad_pcb")]
    if name is None:
        sys.exit(f"no .kicad_pcb found in {proj}")
    sch = os.path.join(proj, name + ".kicad_sch")
    pcb = os.path.join(proj, name + ".kicad_pcb")
    out = os.path.join(proj, "fabrication")
    os.makedirs(out, exist_ok=True)
    tmp = tempfile.mkdtemp()

    rows, W, H = audit(open(pcb, encoding="utf-8").read())
    print(f"=== {name}: design vs JLCPCB cheapest 2-layer tier ===")
    ok_all = True
    for n, got, need, ok in rows:
        ok_all &= ok
        print(f"  {n:20s} {got:16s} {need:18s} {'PASS' if ok else 'FAIL'}")
    print(f"  => {'within' if ok_all else 'EXCEEDS'} the cheapest tier\n")

    # --- gerbers + drill -------------------------------------------------
    gdir = os.path.join(out, "gerber")
    os.path.isdir(gdir) and shutil.rmtree(gdir)
    os.makedirs(gdir)
    run(["kicad-cli", "pcb", "export", "gerbers", "--layers", LAYERS,
         "--output", gdir + os.sep, pcb])
    run(["kicad-cli", "pcb", "export", "drill", "--format", "excellon",
         "--drill-origin", "absolute", "--excellon-separate-th",
         "--output", gdir + os.sep, pcb])
    zpath = os.path.join(out, f"{name}-gerbers.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for n in sorted(os.listdir(gdir)):
            if "drl_map" in n or n.endswith(".gbrjob"):
                continue          # JLCPCB does not want drill maps or the job file
            z.write(os.path.join(gdir, n), n)
    print("=== gerber zip ===")
    with zipfile.ZipFile(zpath) as z:
        for n in z.namelist():
            print("  " + n)
    print()

    # --- BOM -------------------------------------------------------------
    raw_bom = os.path.join(out, f"{name}-bom-raw.csv")
    run(["kicad-cli", "sch", "export", "bom", "--output", raw_bom, sch])
    groups = {}
    with open(raw_bom, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            refs = [x.strip() for x in r["Refs"].split(",") if x.strip()]
            if not refs or refs[0].startswith("H"):
                continue                      # mounting holes are NPTH features
            groups.setdefault(r["Value"], []).extend(refs)
    bom = os.path.join(out, f"{name}-jlcpcb-bom.csv")
    with open(bom, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for val, refs in sorted(groups.items()):
            w.writerow([val, ",".join(sorted(refs)), PACKAGE.get(val, ""), LCSC.get(val, "")])
    print("=== JLCPCB BOM ===")
    print(open(bom, encoding="utf-8").read().rstrip())
    print("\n  blank LCSC cells cannot be assembled - fill them in first\n")

    # --- CPL -------------------------------------------------------------
    # Mid Y deliberately shares the Gerber frame: KiCad writes the board at
    # Y = -H..0, and the drill file confirms it (a via at board y=23.5 appears
    # as Y-23.5). JLCPCB requires the CPL to use the Gerber origin.
    pos = os.path.join(tmp, "pos.csv")
    run(["kicad-cli", "pcb", "export", "pos", "--format", "csv", "--units", "mm",
         "--side", "both", "--smd-only", "--output", pos, pcb])
    cpl = os.path.join(out, f"{name}-jlcpcb-cpl.csv")
    with open(pos, newline="", encoding="utf-8") as fh, \
            open(cpl, "w", newline="", encoding="utf-8") as oh:
        w = csv.writer(oh)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        rows = []
        for r in csv.DictReader(fh):
            rows.append([r["Ref"], f"{float(r['PosX']):.4f}", f"{float(r['PosY']):.4f}",
                         r["Side"].capitalize(), f"{float(r['Rot']):.1f}"])
        rows.sort(key=lambda x: (len(x[0]), x[0]))
        w.writerows(rows)
    print("=== JLCPCB CPL (SMD only, Gerber frame) ===")
    print(open(cpl, encoding="utf-8").read().rstrip())
    print("\n  Verify against JLCPCB's on-screen placement preview before paying.")
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
