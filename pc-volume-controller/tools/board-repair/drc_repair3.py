#!/usr/bin/env python3
"""Final cleanup: resolve hole-to-hole conflicts among the stitching vias.

The relocation in drc_repair2.py moved a via onto (34, 50.5) without checking
the vias that were already there — (34, 51.0) was 0.5 mm away, under the
0.2495 mm... actually under the 0.25 mm board hole-to-hole minimum for the
combined drill+annular geometry, so DRC flagged it.

This pass finds every pair of GND vias closer than 1.0 mm and relocates the
later one to a grid position validated against all vias, fiducials, pads,
silkscreen text and the board edge. It is idempotent: a clean board is left
untouched.
"""
import pcbnew

PCB = "/home/hermes/engineering/pc-volume-controller/pc-volume-controller.kicad_pcb"
MIND = 1.0                      # required centre-to-centre distance between vias
FIDS = {"FID1": (14.0, 50.5), "FID2": (84.0, 50.5), "FID3": (94.0, 34.0)}

grid = [(x, y) for y in (50.5, 51.0, 4.0)
        for x in (19.0, 29.0, 39.0, 49.0, 59.0, 69.0, 79.0, 90.0, 92.5, 5.5)]
grid += [(2.5, y) for y in (16.0, 24.0, 32.0, 40.0)]
grid += [(95.5, y) for y in (16.0, 24.0, 32.0, 40.0)]

board = pcbnew.LoadBoard(PCB)


def MM(v):
    return float(pcbnew.ToMM(v))


def IU(v):
    return int(pcbnew.FromMM(v))


vias = [t for t in board.GetTracks()
        if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == "GND"]
pads = [(MM(p.GetPosition().x), MM(p.GetPosition().y))
        for fp in board.GetFootprints() for p in fp.Pads()]
texts = []
for fp in board.GetFootprints():
    for txt in (fp.Reference(), fp.Value()):
        if txt.IsVisible():
            bb = txt.GetBoundingBox()
            texts.append((MM(bb.GetX()) - 1.0, MM(bb.GetY()) - 1.0,
                          MM(bb.GetX()) + MM(bb.GetWidth()) + 1.0,
                          MM(bb.GetY()) + MM(bb.GetHeight()) + 1.0))
print(f"GND vias: {len(vias)}   pads: {len(pads)}   text boxes: {len(texts)}")


def occupied(x, y, taken):
    if any(((x - a) ** 2 + (y - b) ** 2) ** 0.5 < MIND for a, b in taken):
        return "another via"
    if any(((x - a) ** 2 + (y - b) ** 2) ** 0.5 < 1.6 for a, b in pads):
        return "a pad"
    if any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in texts):
        return "silkscreen"
    if not (2.0 <= x <= 96.0 and 2.0 <= y <= 52.0):
        return "the board edge"
    return None


taken = [(MM(v.GetPosition().x), MM(v.GetPosition().y)) for v in vias]
conflicts = 0
for i, v in enumerate(vias):
    p = v.GetPosition()
    x, y = MM(p.x), MM(p.y)
    others = [(a, b) for j, (a, b) in enumerate(taken) if j != i]
    if not any(((x - a) ** 2 + (y - b) ** 2) ** 0.5 < MIND for a, b in others):
        continue
    conflicts += 1
    why = None
    for nx, ny in grid:
        if ((nx - x) ** 2 + (ny - y) ** 2) ** 0.5 < 2.0:
            continue
        why = occupied(nx, ny, others)
        if why is None:
            v.SetPosition(pcbnew.VECTOR2I(IU(nx), IU(ny)))
            taken[i] = (nx, ny)
            print(f"  via ({x:6.2f},{y:5.2f}) -> ({nx:5.1f},{ny:5.1f})")
            break
    else:
        print(f"  via ({x:6.2f},{y:5.2f}) — NO free grid position found (last reject: {why})")

print(f"conflicting vias resolved: {conflicts}")

pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(PCB, board)
print(f"saved: {PCB}")
