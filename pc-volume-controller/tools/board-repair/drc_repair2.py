#!/usr/bin/env python3
"""Correction pass: fix the two defects the earlier passes left behind.

  1. `Missing connection between items` (+5V, C6:1). drc_repair.py retargeted
     BOTH endpoints sitting at y=23.50 — including the F.Cu stub's PAD-SIDE
     end — collapsing the stub to zero length and severing C6 pad 1 from the
     +5V bus.

  2. `Silkscreen clipped by solder mask` (RV1 reference). FID1 sat at (12, 4),
     where its 2 mm mask aperture overlaps RV1's reference text
     (x 9.90..12.96, y 4.65..6.35).

NOTE: `board.Remove()` invalidates the SWIG proxy — every later
`GetTracks()`/`GetNetInfo()` call raises. So this pass never removes
anything; clashing stitching vias are *moved* to spare verified positions.
The GND netcode is read before any mutation for the same reason.
"""
import pcbnew

PCB = "/home/hermes/engineering/pc-volume-controller/pc-volume-controller.kicad_pcb"
TARGETS = {"FID1": (14.0, 50.5), "FID2": (84.0, 50.5), "FID3": (94.0, 34.0)}
SPARE = [(20.0, 50.5), (34.0, 50.5), (48.0, 50.5), (62.0, 50.5),
         (74.0, 50.5), (90.0, 50.5), (95.5, 20.0), (95.5, 40.0)]

board = pcbnew.LoadBoard(PCB)


def MM(v):
    return float(pcbnew.ToMM(v))


def IU(v):
    return int(pcbnew.FromMM(v))


# --- read everything up front, before any mutation ---
GND = next(t.GetNetCode() for t in board.GetTracks() if t.GetNetname() == "GND")
all_tracks = list(board.GetTracks())
text_boxes = []
for fp in board.GetFootprints():
    if fp.GetReference().startswith("FID"):
        continue
    for txt in (fp.Reference(), fp.Value()):
        if txt.IsVisible():
            bb = txt.GetBoundingBox()
            text_boxes.append((fp.GetReference(), MM(bb.GetX()), MM(bb.GetY()),
                               MM(bb.GetX()) + MM(bb.GetWidth()),
                               MM(bb.GetY()) + MM(bb.GetHeight())))
fid_pos = {fp.GetReference(): (MM(fp.GetPosition().x), MM(fp.GetPosition().y))
           for fp in board.GetFootprints() if fp.GetReference().startswith("FID")}
print(f"read: {len(all_tracks)} tracks, GND netcode {GND}")

# ---- 1. restore the +5V F.Cu stub's pad-side end
fixed = 0
for t in all_tracks:
    if t.Type() == pcbnew.PCB_VIA_T:
        continue
    s, e = t.GetStart(), t.GetEnd()
    if (board.GetLayerName(t.GetLayer()) == "F.Cu" and t.GetNetname() == "+5V"
            and abs(MM(s.x) - MM(e.x)) < 0.01 and abs(MM(s.y) - MM(e.y)) < 0.01
            and abs(MM(s.x) - 3.55) < 0.02):
        t.SetStart(pcbnew.VECTOR2I(IU(3.55), IU(23.50)))
        fixed += 1
        print(f"1. restored +5V stub: ({MM(t.GetStart().x):.2f},{MM(t.GetStart().y):.2f})"
              f" -> ({MM(t.GetEnd().x):.2f},{MM(t.GetEnd().y):.2f})")
print(f"   stubs restored: {fixed}")

# ---- 2. relocate the fiducials clear of silkscreen
print("2. relocating fiducials")
for fp in board.GetFootprints():
    ref = fp.GetReference()
    if ref not in TARGETS:
        continue
    nx, ny = TARGETS[ref]
    clash = [r for r, x0, y0, x1, y1 in text_boxes
             if x0 - 1.2 <= nx <= x1 + 1.2 and y0 - 1.2 <= ny <= y1 + 1.2]
    fp.SetPosition(pcbnew.VECTOR2I(IU(nx), IU(ny)))
    print(f"   {ref}: ({fid_pos[ref][0]:.1f},{fid_pos[ref][1]:.1f}) -> ({nx},{ny})"
          f"  silkscreen clash: {clash or 'none'}")

# ---- 3. move stitching vias that now clash with a fiducial
#         (never Remove(): it invalidates the board proxy)
print("3. relocating clashing stitching vias")
spare_iter = iter(SPARE)
moved = 0
for t in all_tracks:
    if t.Type() != pcbnew.PCB_VIA_T or t.GetNetname() != "GND":
        continue
    p = t.GetPosition()
    x, y = MM(p.x), MM(p.y)
    if not any(((x - fx) ** 2 + (y - fy) ** 2) ** 0.5 < 3.5
               for fx, fy in TARGETS.values()):
        continue
    for sx, sy in spare_iter:
        if any(((sx - fx) ** 2 + (sy - fy) ** 2) ** 0.5 < 3.5
               for fx, fy in TARGETS.values()):
            continue
        t.SetPosition(pcbnew.VECTOR2I(IU(sx), IU(sy)))
        print(f"   via ({x:.2f},{y:.2f}) -> ({sx},{sy})")
        moved += 1
        break
print(f"   vias relocated: {moved}")

pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(PCB, board)
print(f"saved: {PCB}")
