#!/usr/bin/env python3
"""Apply review fixes 1-3 to pc-volume-controller.kicad_pcb.

  1. GP-002 / VS-002 : GND pours on F.Cu and B.Cu, plus validated ground
                       stitching vias.
  2. VP-001          : move the six via-in-pad vias off the capacitor pads
                       and stub them back to the pad with a short F.Cu trace.
  3. FD-001          : three fiducials on F.Cu.

Every new via position is validated against pads, tracks, holes, the board
edge and the other new vias before placement. Same-net copper is excluded
from the clearance test — it is a connection, not a conflict.
"""
import math
import sys

import pcbnew

PCB = "/home/hermes/engineering/pc-volume-controller/pc-volume-controller.kicad_pcb"
FID_LIB = "/usr/share/kicad/footprints/Fiducial.pretty"
FID_NAME = "Fiducial_1mm_Mask2mm"

EDGE = 0.5          # copper-to-board-edge inset for the pours
CLR = 0.30          # minimum clearance demanded of any new via
VIA_D = 0.8         # via diameter (JLCPCB min 0.45; well inside)
VIA_DRILL = 0.4     # drill (JLCPCB min 0.2)
STUB_W = 0.40       # width of the pad->via stub
BOARD_W, BOARD_H = 98.0, 54.0


def MM(v):
    return float(pcbnew.ToMM(v))


def IU(v):
    return int(pcbnew.FromMM(v))


board = pcbnew.LoadBoard(PCB)
GND = board.GetNetInfo().GetNetItem("GND").GetNetCode()


# ---------------------------------------------------------------- obstacles
def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


discs = []      # (label, x, y, radius, net)
segs = []       # (label, ax, ay, bx, by, half_width, net)

for fp in board.GetFootprints():
    for p in fp.Pads():
        pos, sz = p.GetPosition(), p.GetSize()
        discs.append((f"{fp.GetReference()}:{p.GetNumber()}", MM(pos.x), MM(pos.y),
                      max(MM(sz.x), MM(sz.y)) / 2.0, p.GetNetCode()))

for t in board.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        pos = t.GetPosition()
        discs.append((f"via:{t.GetNetname()}", MM(pos.x), MM(pos.y),
                      MM(t.GetWidth(pcbnew.F_Cu)) / 2.0, t.GetNetCode()))
    else:
        s, e = t.GetStart(), t.GetEnd()
        segs.append((f"{board.GetLayerName(t.GetLayer())}:{t.GetNetname()}",
                     MM(s.x), MM(s.y), MM(e.x), MM(e.y),
                     MM(t.GetWidth()) / 2.0, t.GetNetCode()))


def clearance(x, y, net):
    """Smallest gap from the new via's edge to foreign copper."""
    best = 1e9
    for lbl, ox, oy, r, onet in discs:
        if onet == net and net != 0:
            continue
        best = min(best, math.hypot(x - ox, y - oy) - r - VIA_D / 2.0)
    for lbl, ax, ay, bx, by, hw, onet in segs:
        if onet == net and net != 0:
            continue
        best = min(best, seg_dist(x, y, ax, ay, bx, by) - hw - VIA_D / 2.0)
    best = min(best, x - EDGE - VIA_D / 2.0, BOARD_W - EDGE - x - VIA_D / 2.0,
               y - EDGE - VIA_D / 2.0, BOARD_H - EDGE - y - VIA_D / 2.0)
    return best


def on_own_bus(x, y, net):
    """True if a same-net B.Cu vertical bus passes through (x, y)."""
    return any(net == net_ and lbl.startswith("B.Cu")
               and abs(ax - x) < 0.01 and abs(bx - x) < 0.01
               and min(ay, by) - 0.01 <= y <= max(ay, by) + 0.01
               for lbl, ax, ay, bx, by, _, net_ in segs)


# ------------------------------------------------------- 2. via-in-pad fix
print("=" * 68)
print("2. VP-001  move the six via-in-pad vias off their pads")
print("=" * 68)
MOVED = 0
for v in [t for t in board.GetTracks()
          if t.Type() == pcbnew.PCB_VIA_T and abs(MM(t.GetPosition().y) - 23.5) < 0.01]:
    p = v.GetPosition()
    x, y = MM(p.x), MM(p.y)
    new_y = 21.5
    bus = on_own_bus(x, new_y, v.GetNetCode())
    gap = clearance(x, new_y, v.GetNetCode())
    if not bus or gap < CLR:
        print(f"  SKIP  ({x:6.2f},{y:5.2f}) net={v.GetNetname():6} "
              f"on_bus={bus} gap={gap:.2f}mm")
        continue

    stub = pcbnew.PCB_TRACK(board)
    stub.SetStart(pcbnew.VECTOR2I(IU(x), IU(y)))
    stub.SetEnd(pcbnew.VECTOR2I(IU(x), IU(new_y)))
    stub.SetWidth(IU(STUB_W))
    stub.SetLayer(pcbnew.F_Cu)
    stub.SetNetCode(v.GetNetCode())
    board.Add(stub)
    segs.append((f"F.Cu:{v.GetNetname()}", x, y, x, new_y,
                 STUB_W / 2.0, v.GetNetCode()))

    v.SetPosition(pcbnew.VECTOR2I(IU(x), IU(new_y)))
    discs.append((f"via:{v.GetNetname()}", x, new_y, VIA_D / 2.0, v.GetNetCode()))
    print(f"  MOVED ({x:6.2f},{y:5.2f}) -> ({x:6.2f},{new_y:5.2f}) "
          f"net={v.GetNetname():6} gap={gap:.2f}mm  +F.Cu stub")
    MOVED += 1
print(f"  moved: {MOVED}/6")


# ------------------------------------------------------------ 3. fiducials
print("=" * 68)
print("3. FD-001  three fiducials on F.Cu")
print("=" * 68)
for ref, x, y in (("FID1", 12.0, 4.0), ("FID2", 86.0, 4.0), ("FID3", 86.0, 51.0)):
    gap = clearance(x, y, 0)
    if gap < 0.4:
        print(f"  SKIP  {ref} ({x},{y}) gap={gap:.2f}mm")
        continue
    fp = pcbnew.FootprintLoad(FID_LIB, FID_NAME)
    if fp is None:
        print(f"  FAIL  cannot load {FID_NAME}")
        sys.exit(1)
    fp.SetReference(ref)
    fp.SetValue(FID_NAME)
    fp.SetPosition(pcbnew.VECTOR2I(IU(x), IU(y)))
    fp.Reference().SetVisible(False)      # no silkscreen clutter
    fp.Value().SetVisible(False)
    board.Add(fp)
    discs.append((ref, x, y, 1.0, 0))
    print(f"  ADDED {ref} at ({x},{y}) gap={gap:.2f}mm")
print()


# ---------------------------------------------------------------- 1. pours
print("=" * 68)
print("1. GP-002  GND pours on both copper layers")
print("=" * 68)
for layer, name in ((pcbnew.F_Cu, "F.Cu"), (pcbnew.B_Cu, "B.Cu")):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNetCode(GND)
    z.SetLocalClearance(IU(0.25))
    z.SetMinThickness(IU(0.25))
    z.SetIsFilled(False)
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    poly = z.Outline()
    poly.NewOutline()
    for cx, cy in ((EDGE, EDGE), (BOARD_W - EDGE, EDGE),
                   (BOARD_W - EDGE, BOARD_H - EDGE), (EDGE, BOARD_H - EDGE)):
        poly.Append(IU(cx), IU(cy))
    board.Add(z)
    print(f"  {name}: outline {EDGE}..{BOARD_W-EDGE} x {EDGE}..{BOARD_H-EDGE} mm  "
          f"clr 0.25mm  thermal reliefs")

print("-" * 68)
print("1b. VS-002  ground stitching vias")
cands = [("top", x, 4.0) for x in (14, 24, 34, 44, 54, 64, 74, 84)]
cands += [("bot", x, 51.0) for x in (14, 24, 34, 44, 54, 64, 74, 84)]
for y in (12, 20, 28, 36, 44):
    cands.append(("lft", 2.5, y))
    cands.append(("rgt", 95.5, y))

placed = skipped = 0
for side, x, y in cands:
    gap = clearance(x, y, GND)
    if gap < CLR:
        skipped += 1
        continue
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(IU(x), IU(y)))
    v.SetWidth(IU(VIA_D))
    v.SetDrill(IU(VIA_DRILL))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNetCode(GND)
    board.Add(v)
    discs.append(("via:GND", x, y, VIA_D / 2.0, GND))
    placed += 1
print(f"  placed: {placed}   skipped (too close): {skipped}")

print("=" * 68)
filler = pcbnew.ZONE_FILLER(board)
filler.Fill(board.Zones())
print(f"  zones: {len(board.Zones())}  filled: {all(z.IsFilled() for z in board.Zones())}")
pcbnew.SaveBoard(PCB, board)
print(f"  saved: {PCB}")
