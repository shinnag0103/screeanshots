#!/usr/bin/env python3
"""One-page operational chart for Onomichi, about 10 km from the port.

The two piers are independent berths. The chart does not join them.
"""

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COAST = json.loads((ROOT / "coast.json").read_text())
LINES = COAST["lines"]  # [lon, lat]
BRIDGES = COAST["bridges"]

# 10 km circle is centered on the published light, inside Onomichi port.
LIGHT_LAT, LIGHT_LON = 34.401780, 133.195424
HALF_M = 11500.0
LAT_REF = LIGHT_LAT
M_PER_DEG_LAT = 111320.0
M_PER_DEG_LON = 111320.0 * math.cos(math.radians(LAT_REF))
LON0 = LIGHT_LON - HALF_M / M_PER_DEG_LON
LON1 = LIGHT_LON + HALF_M / M_PER_DEG_LON
LAT0 = LIGHT_LAT - HALF_M / M_PER_DEG_LAT
LAT1 = LIGHT_LAT + HALF_M / M_PER_DEG_LAT

CHUO = (34.407550, 133.202417)  # おのみち海の駅「海から」
NIIHAMA = (34.398801, 133.177452)  # OSM 尾道港 新浜桟橋
# Short departure/arrival only. The channel lies south of each pier.
CHUO_OFF = (CHUO[0] - 150.0 / M_PER_DEG_LAT, CHUO[1])
NIIHAMA_OFF = (NIIHAMA[0] - 180.0 / M_PER_DEG_LAT, NIIHAMA[1])

FERRIES = [
    ((34.406650, 133.200783), (34.405173, 133.202675), "土堂―兼吉"),
    ((34.403101, 133.193126), (34.400215, 133.197234), "駅前―富浜"),
]

def fmt_lat(lat: float) -> str:
    minutes = (lat - int(lat)) * 60
    return f"{int(lat)}°{minutes:05.2f}′N"


def fmt_lon(lon: float) -> str:
    minutes = (lon - int(lon)) * 60
    return f"{int(lon)}°{minutes:05.2f}′E"


def rhumb(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlam = math.radians(lon2 - lon1)
    dpsi = math.log(math.tan(phi2 / 2 + math.pi / 4) / math.tan(phi1 / 2 + math.pi / 4))
    theta = math.atan2(dlam, dpsi if abs(dpsi) > 1e-12 else dphi)
    dist = math.hypot(dphi, dlam * math.cos((phi1 + phi2) / 2)) * 6371000.0
    return (math.degrees(theta) + 360) % 360, dist


def mx(lon: float) -> float:
    return (lon - LON0) * M_PER_DEG_LON


def my(lat: float) -> float:
    return (LAT1 - lat) * M_PER_DEG_LAT


def _cross_vertical(a, b, lon_edge):
    if (a[0] - lon_edge) * (b[0] - lon_edge) > 0:
        return None
    if b[0] == a[0]:
        return None
    t = (lon_edge - a[0]) / (b[0] - a[0])
    if t < 0 or t > 1:
        return None
    return (lon_edge, a[1] + t * (b[1] - a[1]))


def land_polygons(lines):
    """Closed island rings, plus mainland closed along the north edge of the view.

    Coastline rings are kept with land on the left, so a positive area is an island.
    """
    polys = []
    for line in lines:
        gap = math.hypot(line[0][0] - line[-1][0], line[0][1] - line[-1][1])
        if gap < 1e-4:
            area = 0.0
            for a, b in zip(line, line[1:]):
                area += a[0] * b[1] - b[0] * a[1]
            if area > 0:
                polys.append(line)
            continue
        hits = []
        for i, (a, b) in enumerate(zip(line, line[1:])):
            for edge in (LON0, LON1):
                point = _cross_vertical(a, b, edge)
                if point is not None:
                    hits.append((i, edge, point))
        if len(hits) < 2:
            continue
        # The mainland enters the west edge and leaves the east edge.
        west = [h for h in hits if h[1] == LON0]
        east = [h for h in hits if h[1] == LON1]
        if len(west) == 1 and len(east) == 1 and west[0][0] < east[0][0]:
            i0, _, p0 = west[0]
            i1, _, p1 = east[0]
            polys.append(
                [p0] + line[i0 + 1 : i1 + 1] + [p1, (LON1, LAT1), (LON0, LAT1), p0]
            )
        elif len(hits) == 2 and hits[0][1] == hits[1][1] and hits[0][0] < hits[1][0]:
            # An island clipped by one side of the view. Close along that edge.
            i0, _, p0 = hits[0]
            i1, _, p1 = hits[1]
            polys.append([p0] + line[i0 + 1 : i1 + 1] + [p1, p0])
    return polys


def raster_land(polygons, lon0, lat0, lon1, lat1, cell):
    width = (lon1 - lon0) * M_PER_DEG_LON
    height = (lat1 - lat0) * M_PER_DEG_LAT
    nx = max(1, int(round(width / cell)))
    ny = max(1, int(round(height / cell)))
    mask = bytearray(nx * ny)

    def px(lon):
        return (lon - lon0) * M_PER_DEG_LON / cell

    def py(lat):
        return (lat1 - lat) * M_PER_DEG_LAT / cell

    for poly in polygons:
        buckets = [[] for _ in range(ny)]
        for a, b in zip(poly, poly[1:]):
            x1, y1 = px(a[0]), py(a[1])
            x2, y2 = px(b[0]), py(b[1])
            if y1 == y2:
                continue
            if y1 > y2:
                x1, y1, x2, y2 = x2, y2, x1, y1
            y_start = max(0, math.ceil(y1 - 1e-9))
            y_end = min(ny, math.ceil(y2 - 1e-9))
            span = y2 - y1
            for y in range(y_start, y_end):
                if y < y1 or y >= y2:
                    continue
                buckets[y].append(x1 + (y - y1) / span * (x2 - x1))
        for y, row in enumerate(buckets):
            if len(row) < 2:
                continue
            row.sort()
            base = y * nx
            for i in range(0, len(row) - 1, 2):
                xa, xb = row[i], row[i + 1]
                i0 = max(0, math.ceil(xa - 0.5))
                i1 = min(nx, math.floor(xb - 0.5) + 1)
                for x in range(i0, i1):
                    mask[base + x] = 1
    return mask, nx, ny


def land_path(mask, nx, ny, cell):
    parts = []
    for y in range(ny):
        x = 0
        row = y * nx
        while x < nx:
            if not mask[row + x]:
                x += 1
                continue
            x2 = x + 1
            while x2 < nx and mask[row + x2]:
                x2 += 1
            parts.append(
                f"M{x * cell:.0f},{y * cell:.0f}h{(x2 - x) * cell:.0f}v{cell:.0f}h{-(x2 - x) * cell:.0f}z"
            )
            x = x2
    return "".join(parts)


def is_land_at(lat, lon, mask, nx, ny, lon0, lat1, cell):
    x = int((lon - lon0) * M_PER_DEG_LON / cell)
    y = int((lat1 - lat) * M_PER_DEG_LAT / cell)
    if not (0 <= x < nx and 0 <= y < ny):
        return False
    return mask[y * nx + x] == 1


def coast_d(project):
    parts = []
    for line in LINES:
        x, y = project(line[0][0], line[0][1])
        parts.append(f"M{x:.0f},{y:.0f}")
        for lon, lat in line[1:]:
            x, y = project(lon, lat)
            parts.append(f"L{x:.0f},{y:.0f}")
    return "".join(parts)


def bridge_d(project):
    parts = []
    for bridge in BRIDGES:
        pts = bridge["pts"]
        x, y = project(pts[0][0], pts[0][1])
        seg = [f"M{x:.0f},{y:.0f}"]
        for lon, lat in pts[1:]:
            x, y = project(lon, lat)
            seg.append(f"L{x:.0f},{y:.0f}")
        parts.append("".join(seg))
    return parts


def is_water_at(lat, lon, water, blocked, nx, gx, gy):
    x, y = gx(lon), gy(lat)
    if not (0 <= x < nx and 0 <= y < len(water) // nx):
        return False
    return water[y * nx + x] == 1


def leg_row(name_a, lat_a, lon_a, name_b, lat_b, lon_b):
    bearing, dist = rhumb(lat_a, lon_a, lat_b, lon_b)
    return bearing, dist, (
        f"<tr><td>{name_a}</td><td>{name_b}</td>"
        f"<td class='num'>{bearing:.0f}°</td>"
        f"<td class='num'>{dist / 1852:.2f}</td>"
        f"<td class='num'>{dist:.0f}</td></tr>"
    )


def inset(title, lon0, lat0, lon1, lat1, route, ferry, note, polygons):
    """route: [(lat, lon), ...]. Local user unit is 1 m."""

    def project(lon, lat):
        return (lon - lon0) * M_PER_DEG_LON, (lat1 - lat) * M_PER_DEG_LAT

    width = (lon1 - lon0) * M_PER_DEG_LON
    height = (lat1 - lat0) * M_PER_DEG_LAT
    cell = 6.0
    mask, nx, ny = raster_land(polygons, lon0, lat0, lon1, lat1, cell)
    for lat, lon in route[1:]:
        if is_land_at(lat, lon, mask, nx, ny, lon0, lat1, cell):
            print(f"INSET POINT ON LAND {title} {lat:.5f},{lon:.5f}", file=sys.stderr)
    land = land_path(mask, nx, ny, cell)
    coast = coast_d(project)
    x1, y1 = project(route[0][1], route[0][0])
    x2, y2 = project(route[1][1], route[1][0])
    ang = math.atan2(y2 - y1, x2 - x1)
    head = 22
    spread = 2.55
    h1 = (x2 - head * math.cos(ang - spread), y2 - head * math.sin(ang - spread))
    h2 = (x2 - head * math.cos(ang + spread), y2 - head * math.sin(ang + spread))
    bearing, dist = rhumb(route[0][0], route[0][1], route[1][0], route[1][1])
    ferry_svg = ""
    if ferry:
        (a, b, _name) = ferry
        fx1, fy1 = project(a[1], a[0])
        fx2, fy2 = project(b[1], b[0])
        ferry_svg = (
            f"<line x1='{fx1:.0f}' y1='{fy1:.0f}' x2='{fx2:.0f}' y2='{fy2:.0f}' class='iferry'/>"
            f"<text x='{(fx1+fx2)/2 - 8:.0f}' y='{(fy1+fy2)/2 - 8:.0f}' class='itext' "
            f"text-anchor='end'>渡船</text>"
        )
    scale = 200
    return f"""<svg class="inset" viewBox="0 0 {width:.0f} {height:.0f}" xmlns="http://www.w3.org/2000/svg">
      <rect width="{width:.0f}" height="{height:.0f}" fill="#d5e3ee"/>
      <path d="{land}" class="land"/>
      <path d="{coast}" class="icoast"/>
      {ferry_svg}
      <line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" class="iroute"/>
      <polygon points="{x2:.0f},{y2:.0f} {h1[0]:.0f},{h1[1]:.0f} {h2[0]:.0f},{h2[1]:.0f}" class="iroute"/>
      <circle cx="{x1:.0f}" cy="{y1:.0f}" r="16" class="ipier"/>
      <circle cx="{x2:.0f}" cy="{y2:.0f}" r="11" class="iturn"/>
      <text x="{x1 + 18:.0f}" y="{y1 - 10:.0f}" class="itext">①</text>
      <text x="{x2 + 16:.0f}" y="{y2 + 28:.0f}" class="itext">② {bearing:.0f}° {dist:.0f}m</text>
      <text x="8" y="28" class="ititle">{title}</text>
      <text x="8" y="{height - 10:.0f}" class="itext">{note}</text>
      <rect x="{width - scale - 16:.0f}" y="{height - 28:.0f}" width="{scale}" height="8" fill="#fbf8f2" stroke="#1c1915" stroke-width="1.5"/>
      <rect x="{width - scale - 16:.0f}" y="{height - 28:.0f}" width="{scale / 2}" height="8" fill="#1c1915"/>
      <text x="{width - 16:.0f}" y="{height - 32:.0f}" class="itext" text-anchor="end">200m</text>
    </svg>"""


def main():
    cell = 22.0
    polygons = land_polygons(LINES)
    print(f"land polygons {len(polygons)}")
    mask, nx, ny = raster_land(polygons, LON0, LAT0, LON1, LAT1, cell)

    def wet(lat, lon):
        return not is_land_at(lat, lon, mask, nx, ny, LON0, LAT1, cell)

    print(f"view {fmt_lat(LAT0)}–{fmt_lat(LAT1)}  {fmt_lon(LON0)}–{fmt_lon(LON1)}")
    print(f"chuo off {CHUO_OFF[0]:.5f},{CHUO_OFF[1]:.5f} water={wet(*CHUO_OFF)}")
    print(f"niihama off {NIIHAMA_OFF[0]:.5f},{NIIHAMA_OFF[1]:.5f} water={wet(*NIIHAMA_OFF)}")
    checks = [
        ("bridge channel", 34.4090, 133.2170, True),
        ("tosaki", 34.4000, 133.2450, True),
        ("miyuki", 34.3820, 133.1720, True),
        ("mekari", 34.3520, 133.1780, True),
        ("hills", 34.4400, 133.2000, False),
        ("mukaijima", 34.3950, 133.2000, False),
        ("innoshima", 34.3400, 133.1700, False),
        ("momoshima", 34.3720, 133.2700, False),
        ("lighthouse point", LIGHT_LAT, LIGHT_LON, False),
    ]
    failed = False
    for name, lat, lon, expect in checks:
        got = wet(lat, lon)
        flag = "OK" if got == expect else "FAIL"
        if got != expect:
            failed = True
        print(f"  {flag} {name} water={got}")
    if not wet(*CHUO_OFF) or not wet(*NIIHAMA_OFF):
        failed = True
    # ASCII so label placement can be checked in the log.
    print("    " + "".join(f"{v:5.2f}"[-4:] for v in [133.08 + i * 0.02 for i in range(13)]))
    for lat in [34.48, 34.46, 34.44, 34.42, 34.40, 34.38, 34.36, 34.34, 34.32]:
        row = []
        for i in range(26):
            lon = 133.08 + i * 0.01
            row.append("~" if wet(lat, lon) else "#")
        print(f"{lat:.2f} {''.join(row)}")
    if failed:
        sys.exit(1)

    w_m = mx(LON1)
    h_m = my(LAT0)
    land = land_path(mask, nx, ny, cell)
    coast = coast_d(lambda lon, lat: (mx(lon), my(lat)))
    bridges = bridge_d(lambda lon, lat: (mx(lon), my(lat)))
    bridge_svg = "\n".join(f"<path d='{d}' class='bridge'/>" for d in bridges)

    def grid():
        lines = []
        labels = []
        for lon in (133.10, 133.15, 133.20, 133.25, 133.30):
            x = mx(lon)
            lines.append(
                f"<line x1='{x:.0f}' y1='0' x2='{x:.0f}' y2='{h_m:.0f}' class='grid'/>"
            )
            labels.append(
                f"<text x='{x:.0f}' y='{h_m - 80:.0f}' class='gridlab' text-anchor='middle'>{fmt_lon(lon)}</text>"
            )
        for lat in (34.35, 34.40, 34.45):
            y = my(lat)
            lines.append(
                f"<line x1='0' y1='{y:.0f}' x2='{w_m:.0f}' y2='{y:.0f}' class='grid'/>"
            )
            labels.append(
                f"<text x='90' y='{y - 40:.0f}' class='gridlab'>{fmt_lat(lat)}</text>"
            )
        return "\n".join(lines + labels)

    def label(lat, lon, text, dx=0, dy=0, anchor="middle", css="place"):
        return (
            f"<text x='{mx(lon) + dx:.0f}' y='{my(lat) + dy:.0f}' text-anchor='{anchor}' "
            f"class='{css}'>{text}</text>"
        )

    def pier_mark(lat, lon, text, dy):
        x, y = mx(lon), my(lat)
        return (
            f"<circle cx='{x:.0f}' cy='{y:.0f}' r='110' class='pier'/>"
            + label(lat, lon, text, dy=dy, css="pierlab")
        )

    cx, cy = mx(LIGHT_LON), my(LIGHT_LAT)
    ferry_svg = []
    for a, b, name in FERRIES:
        x1, y1, x2, y2 = mx(a[1]), my(a[0]), mx(b[1]), my(b[0])
        ferry_svg.append(
            f"<line x1='{x1:.0f}' y1='{y1:.0f}' x2='{x2:.0f}' y2='{y2:.0f}' class='ferry'/>"
        )

    b_chuo, d_chuo, row_chuo = leg_row(
        "① 中央桟橋", *CHUO, "② 桟橋前面", *CHUO_OFF
    )
    b_nii, d_nii, row_nii = leg_row(
        "① 新浜桟橋", *NIIHAMA, "② 桟橋前面", *NIIHAMA_OFF
    )
    print(f"chuo leg {b_chuo:.1f}° {d_chuo:.0f}m")
    print(f"niihama leg {b_nii:.1f}° {d_nii:.0f}m")

    # Insets are wider than tall (the side-by-side boxes are about 3:2).
    def window(center_lat, center_lon, height_m, south_bias=0.55):
        width_m = height_m * 1.55
        lat1 = center_lat + (1 - south_bias) * height_m / M_PER_DEG_LAT
        lat0 = lat1 - height_m / M_PER_DEG_LAT
        lon0 = center_lon - width_m / 2 / M_PER_DEG_LON
        lon1 = center_lon + width_m / 2 / M_PER_DEG_LON
        return lon0, lat0, lon1, lat1

    nii_box = window(34.3979, 133.17745, 560)
    chuo_box = window(34.4066, 133.2022, 560)
    inset_nii = inset(
        "新浜桟橋　離着のみ",
        *nii_box,
        [NIIHAMA, NIIHAMA_OFF],
        None,
        "矢印は離着だけ。先の針路は仕向地による",
        polygons,
    )
    inset_chuo = inset(
        "中央桟橋　離着のみ",
        *chuo_box,
        [CHUO, CHUO_OFF],
        FERRIES[0],
        "矢印は離着だけ。直前を渡船が横断する",
        polygons,
    )

    scale = 5000
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8"/>
<title>運航基準図　尾道港から約10km</title>
<style>
  @page {{ size: A3 landscape; margin: 0; }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; background: #fff; }}
  body {{
    font-family: "Yu Gothic", "Hiragino Sans", "Noto Sans CJK JP", "WenQuanYi Micro Hei", sans-serif;
    color: #1c1915;
  }}
  .sheet {{
    width: 420mm;
    height: 297mm;
    padding: 5mm 6mm 4.5mm;
    display: flex;
    flex-direction: column;
    gap: 1.8mm;
    overflow: hidden;
  }}
  header {{
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 4mm;
    border-bottom: 0.55mm solid #1c1915;
    padding-bottom: 1.3mm;
  }}
  h1 {{
    font-size: 15.5pt;
    line-height: 1.12;
    margin: 0;
    letter-spacing: 0.06em;
    font-weight: 700;
  }}
  h1 span {{ display: block; font-size: 10pt; letter-spacing: 0.03em; font-weight: 600; margin-top: 0.5mm; }}
  .meta {{ font-size: 8pt; line-height: 1.35; text-align: right; }}
  .meta b {{ font-weight: 700; }}
  .blanks {{ margin-top: 0.6mm; }}
  .main {{
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    gap: 2.4mm;
  }}
  .mapwrap {{
    flex: 1 1 auto;
    min-width: 0;
    border: 0.35mm solid #1c1915;
    background: #d5e3ee;
    position: relative;
  }}
  svg.map {{ width: 100%; height: 100%; display: block; }}
  .land {{ fill: #efe6d6; }}
  .coast {{ fill: none; stroke: #243038; stroke-width: 55; stroke-linejoin: round; stroke-linecap: round; }}
  .grid {{ stroke: rgba(28,25,21,0.22); stroke-width: 12; }}
  .gridlab {{ font-size: 250px; fill: #3d4650; }}
  .ring {{ fill: none; stroke: #14365c; stroke-width: 28; stroke-dasharray: 180 120; }}
  .ferry {{ stroke: #b85a12; stroke-width: 80; stroke-dasharray: 90 70; }}
  .bridge {{ fill: none; stroke: #1c1915; stroke-width: 46; stroke-linecap: round; }}
  .pier {{ fill: #14365c; stroke: #fbf8f2; stroke-width: 16; }}
  .pierlab, .place, .note {{
    font-size: 340px;
    font-weight: 700;
    fill: #1c1915;
    stroke: #fbf8f2;
    stroke-width: 70;
    paint-order: stroke fill;
  }}
  .note {{ font-size: 280px; font-weight: 600; }}
  .caution {{ font-size: 300px; font-weight: 700; fill: #7a2e0b; stroke: #fbf8f2; stroke-width: 70; paint-order: stroke fill; }}
  .light {{ fill: #1c1915; stroke: #fbf8f2; stroke-width: 12; }}
  .banner {{
    position: absolute;
    left: 0; right: 0; top: 0;
    background: rgba(251,248,242,0.94);
    border-bottom: 0.25mm solid #1c1915;
    font-size: 7.6pt;
    line-height: 1.3;
    padding: 0.7mm 2mm;
  }}
  .side {{
    width: 158mm;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 1.8mm;
  }}
  section {{
    border: 0.3mm solid #1c1915;
    padding: 1.3mm 1.6mm 1.1mm;
    min-height: 0;
    overflow: hidden;
  }}
  section.route {{ flex: 1.35 1 0; }}
  section.caution {{ flex: 1.05 1 0; }}
  section.other {{ flex: 1 1 0; }}
  h2 {{ font-size: 9pt; margin: 0 0 0.7mm; letter-spacing: 0.03em; }}
  p, li {{ font-size: 7.05pt; line-height: 1.28; margin: 0 0 0.55mm; }}
  ul {{ margin: 0; padding-left: 3.2mm; }}
  table {{ width: 100%; border-collapse: collapse; margin: 0.4mm 0 0.7mm; }}
  th, td {{
    border: 0.18mm solid #1c1915;
    font-size: 6.6pt;
    padding: 0.25mm 0.55mm;
    text-align: left;
    vertical-align: top;
  }}
  th {{ background: #efe6d6; font-weight: 700; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
  .sub {{ font-weight: 700; font-size: 7.2pt; margin: 0.5mm 0 0.15mm; }}
  .insets {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.4mm;
    height: 46mm;
    margin: 0.4mm 0 0.6mm;
  }}
  svg.inset {{ width: 100%; height: 100%; border: 0.2mm solid #1c1915; display: block; }}
  .icoast {{ fill: none; stroke: #243038; stroke-width: 5; stroke-linejoin: round; }}
  .iroute {{ stroke: #14365c; stroke-width: 6; fill: #14365c; }}
  .iferry {{ stroke: #b85a12; stroke-width: 4; stroke-dasharray: 10 7; }}
  .ipier {{ fill: #14365c; stroke: #fbf8f2; stroke-width: 2; }}
  .iturn {{ fill: #fbf8f2; stroke: #14365c; stroke-width: 2.5; }}
  .itext, .ititle {{
    font-size: 22px;
    fill: #1c1915;
    stroke: #fbf8f2;
    stroke-width: 4;
    paint-order: stroke fill;
    font-weight: 700;
  }}
  .ititle {{ font-size: 24px; }}
  footer {{
    font-size: 6.35pt;
    line-height: 1.28;
    border-top: 0.35mm solid #1c1915;
    padding-top: 0.8mm;
  }}
</style>
</head>
<body>
<article class="sheet">
  <header>
    <div>
      <h1>運航基準図<span>尾道港から約10km　小型船舶による海上タクシー</span></h1>
    </div>
    <div class="meta">
      <div>発着場は独立　<b>尾道中央桟橋</b>・<b>新浜桟橋</b></div>
      <div>海図 W119・W114・W1117・W1118　世界測地系　令和8年11月13日</div>
      <div class="blanks">事業者名＿＿＿＿＿＿　船舶名＿＿＿＿＿＿　航海速力＿＿kn</div>
    </div>
  </header>
  <div class="main">
    <div class="mapwrap">
      <svg class="map" viewBox="0 0 {w_m:.0f} {h_m:.0f}" xmlns="http://www.w3.org/2000/svg">
        <path d="{land}" class="land"/>
        {grid()}
        <circle cx="{cx:.0f}" cy="{cy:.0f}" r="10000" class="ring"/>
        <path d="{coast}" class="coast"/>
        {bridge_svg}
        {''.join(ferry_svg)}
        <circle cx="{cx:.0f}" cy="{cy:.0f}" r="55" class="light"/>
        {pier_mark(*CHUO, "中央桟橋", -160)}
        {pier_mark(*NIIHAMA, "新浜桟橋", -160)}
        {label(LIGHT_LAT, LIGHT_LON, "尾道灯台", dx=80, dy=280, anchor="start")}
        {label(34.4185, 133.1980, "尾道")}
        {label(34.3860, 133.2100, "向島")}
        {label(34.3480, 133.1680, "因島")}
        {label(34.3822, 133.1580, "岩子島")}
        {label(34.3735, 133.2720, "百島")}
        {label(34.4048, 133.1865, "尾道水道", css="note")}
        {label(34.3845, 133.1665, "御幸瀬戸", css="note")}
        {label(34.3500, 133.1830, "布刈瀬戸", css="note")}
        {label(34.3680, 133.1150, "三原瀬戸", css="note")}
        {label(34.3683, 133.2067, "高見山", css="note")}
        {label(34.3450, 133.2767, "横島", css="note")}
        {label(34.4145, 133.2260, "尾道大橋 高さ34m", css="caution", anchor="start")}
        {label(34.4145, 133.2260, "新尾道大橋 高さ36m", dy=340, css="caution", anchor="start")}
        {label(34.3595, 133.1680, "因島大橋 航路限界50m", css="caution", anchor="end")}
        {label(34.3728, 133.1765, "向島大橋 約13m", css="caution", anchor="start")}
        {label(34.3933, 133.1555, "架空線 高さ51m", css="caution", anchor="start")}
        {label(34.4008, 133.2485, "戸崎瀬戸・渡船", css="caution", anchor="start")}
        {label(34.3088, 133.1485, "生口橋 航路限界26m（圏外）", css="caution", anchor="end")}
        {label(34.3520, 133.2550, "定置網・のり養殖に注意", css="caution")}
        {label(LIGHT_LAT, LIGHT_LON + 10000 / M_PER_DEG_LON, "10km", dx=120, dy=80, anchor="start", css="note")}
        {label(LIGHT_LAT - 10000 / M_PER_DEG_LAT, LIGHT_LON, "10km", dx=280, dy=-220, anchor="start", css="note")}
        <g>
          <rect x="{w_m - scale - 700:.0f}" y="{h_m - 520:.0f}" width="{scale}" height="90" fill="#fbf8f2" stroke="#1c1915" stroke-width="16"/>
          <rect x="{w_m - scale - 700:.0f}" y="{h_m - 520:.0f}" width="{scale / 2:.0f}" height="90" fill="#1c1915"/>
          <text x="{w_m - scale - 700:.0f}" y="{h_m - 580:.0f}" class="gridlab">0</text>
          <text x="{w_m - scale / 2 - 700:.0f}" y="{h_m - 580:.0f}" class="gridlab" text-anchor="middle">2.5km</text>
          <text x="{w_m - 700:.0f}" y="{h_m - 580:.0f}" class="gridlab" text-anchor="end">5km</text>
        </g>
      </svg>
      <div class="banner">黒点は発着場。円は尾道灯台から10km。橙の破線は渡船。橋の位置に黒線。北が上。離着の針路は右の差し込み図で、二つの桟橋は結ばない。</div>
    </div>
    <div class="side">
      <section class="route">
        <h2>（1）基準経路　発着場の位置、針路、変針点</h2>
        <p>中央桟橋と新浜桟橋は、それぞれ独立した発着場である。桟橋の間に基準経路は定めない。各桟橋から②桟橋前面までが離着の針路で、②の先は仕向地による。航路を航行する船舶と、渡船の進路を避ける。</p>
        <div class="insets">
          {inset_nii}
          {inset_chuo}
        </div>
        <p class="sub">新浜桟橋　{fmt_lat(NIIHAMA[0])} {fmt_lon(NIIHAMA[1])}</p>
        <table>
          <tr><th>自</th><th>至</th><th>針路</th><th>海里</th><th>m</th></tr>
          {row_nii}
        </table>
        <p class="sub">中央桟橋　{fmt_lat(CHUO[0])} {fmt_lon(CHUO[1])}　土堂二丁目、海の駅</p>
        <table>
          <tr><th>自</th><th>至</th><th>針路</th><th>海里</th><th>m</th></tr>
          {row_chuo}
        </table>
        <p>針路は真方位で、1度単位。距離は無流の概算で、潮流の偏位を含まない。航海速力は船舶の速力基準による。中央桟橋の②の南を、土堂―兼吉の渡船が横断する。</p>
      </section>
      <section class="caution">
        <h2>（2）地形・水深・潮流で特に留意する箇所</h2>
        <p class="sub">尾道水道の潮流</p>
        <p>東流の最強は2.7ノット、西流の最強は2.5ノット。東流は尾道の低潮の約40分後から高潮の約40分後までで、最強は高潮の約2時間25分前。西流は高潮の約40分後から低潮の約40分後までで、最強は低潮の約2時間25分前。転流は来島海峡より約15分遅れる。当日の推算で確認する。流れは岸にほぼ並行するので、離着桟は当て舵と増減速の余裕を持つ。</p>
        <p class="sub">水深と狭い水面</p>
        <p>水道の西口は約9m。東口の最狭部は幅約50m、水深約4mの箇所がある。尾道灯台が水道へ突出する。第二航路は中心線の両側各25mで、東口最狭部ではこの幅が可航幅になる。法線は海図W119に従う。本図に等深線はない。</p>
        <p class="sub">橋、架空線、渡船、漁具</p>
        <p>尾道大橋は高さ34m、新尾道大橋は高さ36m。御幸瀬戸の向島大橋は高さ約13m、南口の架空線は高さ28m。水道西部（34°23.6′N 133°09.7′E）の架空線は高さ51m。高さは潮が上がると余裕が減る。因島大橋の航路限界は50mで、布刈瀬戸（幅約800m）は三原瀬戸航路の東口にあたり、大型船が多く潮流が強い。流速は推算で確認する。生口橋の航路限界26mは灯台から約11km、内海大橋の高さ30mは約12kmで、いずれも10km圏の外。</p>
        <p>水道の渡船は土堂―兼吉と駅前―富浜の2航路。福本渡船は令和7年3月31日に廃止。戸崎瀬戸にも横断するフェリーと渡船がある。横島・百島方面には定置網とのり養殖があり、水路誌は距岸約3海里に及ぶものがある、と記す。</p>
      </section>
      <section class="other">
        <h2>（3）航行の安全を確保するため必要な事項</h2>
        <ul>
          <li>総トン数20トン未満は港則法の汽艇等であり、航路を航行する義務はない。汽艇等以外の船舶の進路を避ける。</li>
          <li>20トン以上の船舶は、特定港への出入と通過に航路を用いる。やむを得ない場合を除く。</li>
          <li>航路への出入と横断は、航路を航行する船舶の進路を避ける。航路内は右側を通り、並航も追越しもせず、錨泊しない。</li>
          <li>港内は、他船に危険を及ぼさない速力とする。渡船の横断帯と離着桟は微速とする。</li>
          <li>第三区では、岸壁又は桟橋に係留中の船舶の船側に係留しない。区界は海図W119で確認する。</li>
          <li>旅客船、漁船、作業船、プレジャーボートがふくそうする。大型船の通航を妨げない。</li>
          <li>視程が低下したときは減速し、見張りを増やす。安全な速力を保てなければ反転又は待機する。</li>
          <li>離桟時と着桟時に、地点名、時刻、天候、風向、風速、波浪、視程を運航管理者へ連絡する。</li>
          <li>中央桟橋は、尾道みなと祭と住吉花火大会の日は休業する。</li>
          <li>緊急通報は118。尾道海上保安部（港長）0848-22-2108、尾道市古浜町。</li>
          <li>発航前に海図、潮汐表、水路通報、当日の潮流推算を確認する。</li>
        </ul>
      </section>
    </div>
  </div>
  <footer>
    出典：海上保安庁『瀬戸内海水路誌』追補（書誌103、令和8年1月30日）の尾道水道、阿伏兎瀬戸～戸崎瀬戸。港則法第3条・第11条・第12条・第13条・第16条・第18条。港則法施行規則第34条・別表第二。因島大橋・生口橋の航路限界は各橋の諸元。中央桟橋の位置はおのみち海の駅の公表値。新浜桟橋、渡船場、岸線はOpenStreetMap（令和8年11月）を模式化。
    本図は運航基準の模式図であり、航海用海図ではない。半径10kmの中心は尾道灯台。針路と距離は世界測地系の概算。航海には最新の海図W119、W114、W1117、W1118、潮汐表、水路通報と、船長の判断を用いる。印刷はA3横、倍率100%、余白なし。
  </footer>
</article>
</body>
</html>
"""
    out = ROOT / "onomichi-unko-kijunzu.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} bytes={out.stat().st_size}")


if __name__ == "__main__":
    main()
