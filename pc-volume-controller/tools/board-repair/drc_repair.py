#!/usr/bin/env python3
"""DRC repair pass for pc-volume-controller after fix_review_items.py.

Two defects introduced by the first pass, both caught by `kicad-cli pcb drc`:

  1. `Front solder mask aperture bridges items with different nets` on
     FID1/FID2/FID3 — each fiducial's 2 mm mask aperture exposes the GND
     pour beneath it, and the fiducial pads carried no net. Binding the
     fiducials to GND makes the aperture and the pour the same net.

  2. `Track has unconnected end` on B.Cu [+5V] — the +5V vertical
     (3.55, 23.50) -> (3.55, 13.00) had the via as its ONLY connection at
     the 23.50 end. Moving the via off the pad left that end dangling.
     Retarget it to the via's new position.

Any track endpoint that sat exactly on a moved via is retargeted generally,
so this also covers the other nets if they ever acquire the same shape.
"""
import pcbnew

PCB = "/home/hermes/engineering/pc-volume-controller/pc-volume-controller.kicad_pcb"
OLD_Y = 23.50
NEW_Y = 21.50
VTOL = pcbnew.FromMM(0.02)


def MM(v):
    return float(pcbnew.ToMM(v))


board = pcbnew.LoadBoard(PCB)
GND = board.GetNetInfo().GetNetItem("GND").GetNetCode()

# ---- 1. fiducials onto the GND net
fixed = 0
for fp in board.GetFootprints():
    if not fp.GetReference().startswith("FID"):
        continue
    for p in fp.Pads():
        if p.GetNetCode() != GND:
            p.SetNetCode(GND)
            fixed += 1
print(f"1. fiducial pads bound to GND: {fixed}")

# ---- 2. retarget tracks whose endpoint was the old via position
retargeted = 0
for t in board.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        continue
    for getter, setter in ((t.GetStart, t.SetStart), (t.GetEnd, t.SetEnd)):
        pt = getter()
        if abs(MM(pt.y) - OLD_Y) < 0.02 and abs(MM(pt.x) - 3.55) < 0.02:
            setter(pcbnew.VECTOR2I(pcbnew.FromMM(MM(pt.x)),
                                   pcbnew.FromMM(NEW_Y)))
            retargeted += 1
            print(f"   retargeted {board.GetLayerName(t.GetLayer())} "
                  f"[{t.GetNetname()}] end {MM(pt.x):.2f},{MM(pt.y):.2f} -> "
                  f"{MM(pt.x):.2f},{NEW_Y}")
print(f"2. track endpoints retargeted: {retargeted}")

# ---- 3. check for any remaining dangling ends on the moved nets
dangling = []
for t in board.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        continue
    for pt in (t.GetStart(), t.GetEnd()):
        near = False
        for other in board.GetTracks():
            if other is t:
                continue
            if other.Type() == pcbnew.PCB_VIA_T:
                op = other.GetPosition()
                if abs(op.x - pt.x) < VTOL and abs(op.y - pt.y) < VTOL:
                    near = True
                    break
            else:
                for op in (other.GetStart(), other.GetEnd()):
                    if abs(op.x - pt.x) < VTOL and abs(op.y - pt.y) < VTOL:
                        near = True
                        break
            if near:
                break
        if not near:
            for fp in board.GetFootprints():
                for pad in fp.Pads():
                    pp = pad.GetPosition()
                    if abs(pp.x - pt.x) < VTOL and abs(pp.y - pt.y) < VTOL:
                        near = True
                        break
                if near:
                    break
        if not near:
            dangling.append((t.GetNetname(), MM(pt.x), MM(pt.y)))
if dangling:
    print("3. WARNING still-dangling track ends:")
    for net, x, y in dangling:
        print(f"   {net} at ({x:.2f},{y:.2f})")
else:
    print("3. no dangling track ends")

filler = pcbnew.ZONE_FILLER(board)
filler.Fill(board.Zones())
pcbnew.SaveBoard(PCB, board)
print(f"saved: {PCB}")
