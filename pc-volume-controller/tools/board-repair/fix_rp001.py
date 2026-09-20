#!/usr/bin/env python3
"""Close RP-001: a ground stitching via adjacent to every signal layer
transition.

RP-001 fires when a net changes reference layer with no ground via within
`search_radius = max(dielectric_height * 2, 1.0)` — 1.0 mm on this stackup.
Each /VOL net has TWO transitions (one at the capacitor pad, one at the Nano),
so ten adjacent ground vias are needed, not five.

Geometry, checked against the board's own rules rather than assumed:
  netclass Default  clearance 0.2 mm, via 0.6 mm / drill 0.3 mm
  board rules       min_hole_to_hole 0.25 mm, min_via_diameter 0.5 mm,
                    min_copper_edge_clearance 0.5 mm

A 0.6 mm ground via at 0.95 mm centre-to-centre from a 0.8 mm signal via gives
a 0.25 mm copper gap and a 0.60 mm hole-to-hole gap — both inside the rules.
Each candidate is additionally validated against every foreign-net pad, track
and via, and against the board edge.
"""
import math

import pcbnew

PCB = "/home/hermes/engineering/pc-volume-controller/pc-volume-controller.kicad_pcb"

RADIUS = 0.95          # centre distance to the signal via (must be <= 1.0)
VIA_D = 0.6            # netclass Default via diameter
VIA_DRILL = 0.3
MIN_CLR = 0.25         # demanded copper gap (rule is 0.2)
MIN_H2H = 0.30         # demanded hole-to-hole (rule is 0.25)
EDGE = 0.5             # min_copper_edge_clearance

SIGNAL_VIAS = [
    (33.02, 30.00), (11.43, 21.50),      # /VOL1
    (30.48, 28.00), (29.21, 21.50),      # /VOL2
    (46.99, 21.50), (27.94, 32.00),      # /VOL3
    (25.40, 34.00), (64.77, 21.50),      # /VOL4
    (82.55, 21.50), (22.86, 36.00),      # /VOL5
]

board = pcbnew.LoadBoard(PCB)


def MM(v):
    return float(pcbnew.ToMM(v))


def IU(v):
    return int(pcbnew.FromMM(v))


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


# --- read everything before mutating (board.Remove is never called, but the
#     habit keeps this script safe if it ever is) ---
GND = next(t.GetNetCode() for t in board.GetTracks() if t.GetNetname() == "GND")

foreign_discs = []      # pads and vias not on GND
foreign_segs = []       # tracks not on GND
for fp in board.GetFootprints():
    for p in fp.Pads():
        if p.GetNetCode() == GND:
            continue
        pos, sz = p.GetPosition(), p.GetSize()
        drill = MM(p.GetDrillSize().x)
        foreign_discs.append((f"{fp.GetReference()}:{p.GetNumber()}", MM(pos.x),
                              MM(pos.y), max(MM(sz.x), MM(sz.y)) / 2.0, drill))
for t in board.GetTracks():
    if t.GetNetCode() == GND:
        continue
    if t.Type() == pcbnew.PCB_VIA_T:
        p = t.GetPosition()
        foreign_discs.append((f"via:{t.GetNetname()}", MM(p.x), MM(p.y),
                              MM(t.GetWidth(pcbnew.F_Cu)) / 2.0,
                              MM(t.GetDrillValue())))
    else:
        s, e = t.GetStart(), t.GetEnd()
        foreign_segs.append((f"{board.GetLayerName(t.GetLayer())}:{t.GetNetname()}",
                             MM(s.x), MM(s.y), MM(e.x), MM(e.y),
                             MM(t.GetWidth()) / 2.0))

gnd_pts = [(MM(t.GetPosition().x), MM(t.GetPosition().y), MM(t.GetDrillValue()) / 2.0)
           for t in board.GetTracks()
           if t.Type() == pcbnew.PCB_VIA_T and t.GetNetCode() == GND]
print(f"foreign discs {len(foreign_discs)}  foreign segs {len(foreign_segs)}  "
      f"existing GND vias {len(gnd_pts)}")


def evaluate(x, y):
    """Worst-case copper gap and hole gap for a GND via at (x, y)."""
    clr, h2h = 1e9, 1e9
    for lbl, ox, oy, r, drill in foreign_discs:
        d = math.hypot(x - ox, y - oy)
        clr = min(clr, d - r - VIA_D / 2.0)
        if drill > 0:
            h2h = min(h2h, d - VIA_DRILL / 2.0 - drill / 2.0)
    for lbl, ax, ay, bx, by, hw in foreign_segs:
        clr = min(clr, seg_dist(x, y, ax, ay, bx, by) - hw - VIA_D / 2.0)
    for gx, gy, gr in gnd_pts:
        h2h = min(h2h, math.hypot(x - gx, y - gy) - VIA_DRILL / 2.0 - gr)
    clr = min(clr, x - EDGE - VIA_D / 2.0, 98 - EDGE - x - VIA_D / 2.0,
              y - EDGE - VIA_D / 2.0, 54 - EDGE - y - VIA_D / 2.0)
    return clr, h2h


placed = 0
for sx, sy in SIGNAL_VIAS:
    chosen = None
    for radius in (RADIUS, 0.90, 0.85, 0.80):
        for step in range(16):
            ang = math.radians(step * 22.5)
            cx, cy = sx + radius * math.cos(ang), sy + radius * math.sin(ang)
            clr, h2h = evaluate(cx, cy)
            if clr >= MIN_CLR and h2h >= MIN_H2H:
                chosen = (cx, cy, radius, clr, h2h, step * 22.5)
                break
        if chosen:
            break
    if not chosen:
        print(f"  NO VALID POSITION within 1.0mm of signal via ({sx},{sy})")
        continue
    cx, cy, radius, clr, h2h, ang = chosen
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(IU(cx), IU(cy)))
    v.SetWidth(IU(VIA_D))
    v.SetDrill(IU(VIA_DRILL))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNetCode(GND)
    board.Add(v)
    gnd_pts.append((cx, cy, VIA_DRILL / 2.0))
    placed += 1
    print(f"  signal ({sx:6.2f},{sy:5.2f})  GND via ({cx:6.2f},{cy:5.2f})  "
          f"r={radius:.2f} ang={ang:5.1f}  clr={clr:.2f}mm  h2h={h2h:.2f}mm")

print(f"\nground vias placed: {placed}/10")
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(PCB, board)
print(f"saved: {PCB}")
