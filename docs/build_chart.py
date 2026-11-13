#!/usr/bin/env python3
"""Build the one-page Onomichi operational-standard chart."""

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COAST = json.loads((ROOT / "coast.json").read_text())

LON0, LON1 = 133.1705, 133.2215
LAT0, LAT1 = 34.3938, 34.4132
LAT_REF = 34.403
M_PER_DEG_LAT = 111320.0
M_PER_DEG_LON = 111320.0 * math.cos(math.radians(LAT_REF))


def mx(lon: float) -> float:
    return (lon - LON0) * M_PER_DEG_LON


def my(lat: float) -> float:
    return (LAT1 - lat) * M_PER_DEG_LAT


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


# Tracks sit inside the sounded channel. Courses below are the rhumb lines
# of these vertices, which were checked against the coastline profile.
WEST = [
    ("①", "中央桟橋前面", 34.40670, 133.20242),
    ("②", "灯台東方", 34.40470, 133.19760),
    ("③", "駅前渡船沖", 34.40220, 133.19313),
    ("④", "新浜東方", 34.39910, 133.18500),
    ("⑤", "新浜桟橋前面", 34.39810, 133.17745),
]
EAST = [
    ("⑤", "新浜桟橋前面", 34.39810, 133.17745),
    ("⑥", "新浜沖・南側", 34.39655, 133.17830),
    ("⑦", "西弯の南", 34.39735, 133.18650),
    ("⑧", "灯台南西", 34.39950, 133.19180),
    ("⑨", "灯台狭部", 34.40255, 133.19430),
    ("⑩", "灯台の東", 34.40350, 133.19680),
    ("⑪", "土堂沖・南", 34.40505, 133.20020),
    ("⑫", "兼吉沖", 34.40530, 133.20230),
    ("①", "中央桟橋前面", 34.40670, 133.20242),
]

PIERS = {
    "中央桟橋": (34.407550, 133.202417),
    "新浜桟橋": (34.398801, 133.177452),
    "土堂": (34.406650, 133.200783),
    "兼吉": (34.405173, 133.202675),
    "駅前": (34.403101, 133.193126),
    "富浜": (34.400215, 133.197234),
    "灯台": (34.401780, 133.195424),
}


def legs(points):
    rows = []
    total = 0.0
    for a, b in zip(points, points[1:]):
        bearing, dist = rhumb(a[2], a[3], b[2], b[3])
        total += dist
        rows.append((a, b, bearing, dist))
    return rows, total


WEST_LEGS, WEST_M = legs(WEST)
EAST_LEGS, EAST_M = legs(EAST)


def leg_row(a, b, bearing, dist):
    nm = dist / 1852
    return (
        f"<tr><td>{a[0]} {a[1]}</td><td>{b[0]} {b[1]}</td>"
        f"<td class='num'>{bearing:.0f}°</td>"
        f"<td class='num'>{nm:.2f}</td>"
        f"<td class='num'>{dist:.0f}</td></tr>"
    )


def path_of(points):
    return " ".join(f"{mx(p[3]):.1f},{my(p[2]):.1f}" for p in points)


def coast_paths():
    parts = []
    for el in COAST["elements"]:
        if el.get("tags", {}).get("natural") != "coastline":
            continue
        geom = el.get("geometry") or []
        if len(geom) < 2:
            continue
        d = [f"M{mx(geom[0]['lon']):.1f},{my(geom[0]['lat']):.1f}"]
        for p in geom[1:]:
            d.append(f"L{mx(p['lon']):.1f},{my(p['lat']):.1f}")
        parts.append("".join(d))
    return parts


def land_polygon(side: str) -> str:
    samples = []
    lon = LON0
    while lon <= LON1 + 1e-9:
        hits = []
        for el in COAST["elements"]:
            if el.get("tags", {}).get("natural") != "coastline":
                continue
            geom = el.get("geometry") or []
            for p, q in zip(geom, geom[1:]):
                x1, y1, x2, y2 = p["lon"], p["lat"], q["lon"], q["lat"]
                if x1 == x2:
                    continue
                if (x1 - lon) * (x2 - lon) <= 0:
                    t = (lon - x1) / (x2 - x1)
                    hits.append(y1 + t * (y2 - y1))
        if hits:
            samples.append((lon, max(hits) if side == "north" else min(hits)))
        lon += 0.00035
    if len(samples) < 2:
        return ""
    if side == "north":
        pts = [(LON0, LAT1), *samples, (LON1, LAT1)]
    else:
        pts = [(LON0, LAT0), *samples, (LON1, LAT0)]
    return " ".join(f"{mx(lon):.1f},{my(lat):.1f}" for lon, lat in pts)


def grid():
    lines = []
    labels = []
    lons = [133.18, 133.19, 133.20, 133.21, 133.22]
    lats = [34.40, 34.41]
    for lon in lons:
        x = mx(lon)
        lines.append(
            f"<line x1='{x:.1f}' y1='0' x2='{x:.1f}' y2='{my(LAT0):.1f}' class='grid'/>"
        )
        labels.append(
            f"<text x='{x:.1f}' y='{my(LAT0) - 18:.1f}' class='gridlab' text-anchor='middle'>{fmt_lon(lon)}</text>"
        )
    for lat in lats:
        y = my(lat)
        lines.append(
            f"<line x1='0' y1='{y:.1f}' x2='{mx(LON1):.1f}' y2='{y:.1f}' class='grid'/>"
        )
        labels.append(
            f"<text x='28' y='{y - 8:.1f}' class='gridlab'>{fmt_lat(lat)}</text>"
        )
    return "\n".join(lines + labels)


def marker(lat, lon, label, dx, dy, anchor="start"):
    x, y = mx(lon), my(lat)
    return (
        f"<g class='place'>"
        f"<circle cx='{x:.1f}' cy='{y:.1f}' r='11'/>"
        f"<text x='{x + dx:.1f}' y='{y + dy:.1f}' text-anchor='{anchor}'>{label}</text>"
        f"</g>"
    )


W_M = mx(LON1)
H_M = my(LAT0)
west_nm = WEST_M / 1852
east_nm = EAST_M / 1852

west_rows = "\n".join(leg_row(*row) for row in WEST_LEGS)
east_rows = "\n".join(leg_row(*row) for row in EAST_LEGS)

coast_svg = "\n".join(f"<path d='{d}' class='coast'/>" for d in coast_paths())

# Ferry tracks
ferries = [
    (PIERS["土堂"], PIERS["兼吉"], "土堂―兼吉"),
    (PIERS["駅前"], PIERS["富浜"], "駅前―富浜"),
]
ferry_svg = []
for (a, b, name) in ferries:
    x1, y1, x2, y2 = mx(a[1]), my(a[0]), mx(b[1]), my(b[0])
    ferry_svg.append(
        f"<line x1='{x1:.1f}' y1='{y1:.1f}' x2='{x2:.1f}' y2='{y2:.1f}' class='ferry'/>"
    )

# Bridge span at the published bridge longitude
bridge_x = mx(133.2167)
bridge_svg = (
    f"<line x1='{bridge_x:.1f}' y1='{my(34.4112):.1f}' x2='{bridge_x:.1f}' y2='{my(34.4076):.1f}' class='bridge'/>"
    f"<text x='{bridge_x - 16:.1f}' y='{my(34.41155):.1f}' class='bridgelab' text-anchor='end'>新尾道大橋 36m</text>"
    f"<text x='{bridge_x + 16:.1f}' y='{my(34.41155):.1f}' class='bridgelab'>尾道大橋 34m</text>"
)

def arealabel(lat, lon, text, anchor="middle"):
    return (
        f"<text x='{mx(lon):.1f}' y='{my(lat):.1f}' text-anchor='{anchor}' "
        f"class='place' style='font-size:56px;font-weight:700'>{text}</text>"
    )

places = "\n".join(
    [
        arealabel(34.4102, 133.2062, "尾道市街"),
        arealabel(34.39505, 133.1992, "向島"),
        marker(*PIERS["灯台"], "尾道灯台", 18, 78),
        marker(*PIERS["中央桟橋"], "中央桟橋", 18, -36),
        marker(*PIERS["新浜桟橋"], "新浜桟橋", 18, -36),
        f"<text x='{mx(133.2036):.1f}' y='{my(34.40385):.1f}' class='ferrylab'>土堂―兼吉</text>",
        f"<text x='{mx(133.1946):.1f}' y='{my(34.39955):.1f}' class='ferrylab'>駅前―富浜</text>",
    ]
)

# Numbered turning points
nums = []
for ident, _name, lat, lon in WEST:
    nums.append(
        f"<g class='wp w'>"
        f"<circle cx='{mx(lon):.1f}' cy='{my(lat):.1f}' r='32'/>"
        f"<text x='{mx(lon):.1f}' y='{my(lat) + 6:.1f}' text-anchor='middle'>{ident}</text>"
        f"</g>"
    )
for ident, _name, lat, lon in EAST[1:-1]:
    nums.append(
        f"<g class='wp e'>"
        f"<circle cx='{mx(lon):.1f}' cy='{my(lat):.1f}' r='32'/>"
        f"<text x='{mx(lon):.1f}' y='{my(lat) + 6:.1f}' text-anchor='middle'>{ident}</text>"
        f"</g>"
    )

html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8"/>
<title>運航基準図　尾道港周辺（尾道水道）</title>
<style>
  @page {{ size: A3 landscape; margin: 0; }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; background: #cfc8bc; }}
  body {{
    font-family: "Yu Gothic", "Hiragino Sans", "Noto Sans CJK JP", "WenQuanYi Micro Hei", sans-serif;
    color: #1c1915;
  }}
  .sheet {{
    width: 420mm;
    height: 297mm;
    margin: 0 auto;
    background: #fbf8f2;
    padding: 6mm 7mm 5mm;
    display: flex;
    flex-direction: column;
    gap: 2.2mm;
  }}
  header {{
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 4mm;
    border-bottom: 0.6mm solid #1c1915;
    padding-bottom: 1.6mm;
  }}
  h1 {{
    font-size: 16pt;
    line-height: 1.15;
    margin: 0;
    letter-spacing: 0.08em;
    font-weight: 700;
  }}
  h1 span {{ display: block; font-size: 10.5pt; letter-spacing: 0.04em; font-weight: 600; margin-top: 0.6mm; }}
  .meta {{
    font-size: 8pt;
    line-height: 1.35;
    text-align: right;
  }}
  .meta b {{ font-weight: 700; }}
  .blanks {{ margin-top: 0.8mm; }}
  .mapwrap {{
    flex: 1 1 auto;
    min-height: 0;
    border: 0.35mm solid #1c1915;
    background: #d5e3ee;
    position: relative;
  }}
  svg.map {{ width: 100%; height: 100%; display: block; }}
  .coast {{ fill: none; stroke: #243038; stroke-width: 8; stroke-linejoin: round; }}
  .land {{ fill: #efe6d6; stroke: none; }}
  .grid {{ stroke: rgba(28,25,21,0.28); stroke-width: 1.5; }}
  .gridlab {{ font-size: 42px; fill: #3d4650; }}
  .route {{ fill: none; stroke-linecap: round; stroke-linejoin: round; }}
  .route.w {{ stroke: #14365c; stroke-width: 14; }}
  .route.e {{ stroke: #1d5c45; stroke-width: 12; stroke-dasharray: 28 16; }}
  .ferry {{ stroke: #b85a12; stroke-width: 7; stroke-dasharray: 18 12; }}
  .ferrylab, .bridgelab, .note {{ font-size: 46px; fill: #1c1915; stroke: #fbf8f2; stroke-width: 8; paint-order: stroke fill; }}
  .ferrylab {{ fill: #8a3e08; }}
  .bridge {{ stroke: #1c1915; stroke-width: 10; }}
  .bridgelab {{ font-size: 42px; }}
  .place circle {{ fill: #1c1915; }}
  .place text {{ font-size: 52px; font-weight: 700; fill: #1c1915; stroke: #fbf8f2; stroke-width: 10; paint-order: stroke fill; }}
  .wp circle {{ stroke: #fbf8f2; stroke-width: 4; }}
  .wp text {{ font-size: 36px; font-weight: 700; fill: #fbf8f2; }}
  .wp.w circle {{ fill: #14365c; }}
  .wp.e circle {{ fill: #1d5c45; }}
  .mapkey {{
    position: absolute;
    left: 2.5mm;
    bottom: 2.2mm;
    background: rgba(251,248,242,0.94);
    border: 0.25mm solid #1c1915;
    padding: 1.2mm 1.8mm;
    font-size: 7.4pt;
    line-height: 1.35;
  }}
  .mapkey div {{ display: flex; align-items: center; gap: 1.6mm; }}
  .swatch {{ width: 9mm; height: 0; border-top: 1.1mm solid #14365c; }}
  .swatch.e {{ border-top: 1.1mm dashed #1d5c45; }}
  .swatch.f {{ border-top: 0.9mm dashed #b85a12; }}
  .scale {{ margin-top: 0.8mm; }}
  .scale i {{
    display: inline-block; width: 18mm; height: 2mm;
    background: repeating-linear-gradient(90deg, #1c1915 0 9mm, #fbf8f2 9mm 18mm);
    border: 0.2mm solid #1c1915; vertical-align: -0.4mm; margin-right: 1.2mm;
  }}
  .cols {{
    display: grid;
    grid-template-columns: 1.15fr 1fr 1fr;
    gap: 2.4mm;
    height: 114mm;
  }}
  section {{
    border: 0.3mm solid #1c1915;
    padding: 1.5mm 1.8mm 1.3mm;
    overflow: hidden;
  }}
  h2 {{
    font-size: 9pt;
    margin: 0 0 1mm;
    letter-spacing: 0.04em;
  }}
  p, li {{ font-size: 7.15pt; line-height: 1.32; margin: 0 0 0.7mm; }}
  ul {{ margin: 0; padding-left: 3.4mm; }}
  table {{ width: 100%; border-collapse: collapse; margin: 0.6mm 0 1mm; }}
  th, td {{
    border: 0.2mm solid #1c1915;
    font-size: 6.7pt;
    padding: 0.3mm 0.6mm;
    text-align: left;
    vertical-align: top;
  }}
  th {{ background: #efe6d6; font-weight: 700; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
  .sub {{ font-weight: 700; font-size: 7.3pt; margin: 0.8mm 0 0.2mm; }}
  footer {{
    font-size: 6.5pt;
    line-height: 1.3;
    border-top: 0.35mm solid #1c1915;
    padding-top: 1mm;
  }}
</style>
</head>
<body>
<article class="sheet">
  <header>
    <div>
      <h1>運航基準図<span>尾道港周辺（尾道水道）　小型船舶による海上タクシー</span></h1>
    </div>
    <div class="meta">
      <div>常用発着場　<b>尾道中央桟橋</b>・<b>新浜桟橋</b></div>
      <div>海図 W119・W114・W1117　世界測地系　令和8年11月13日</div>
      <div class="blanks">事業者名＿＿＿＿＿＿　船舶名＿＿＿＿＿＿　航海速力＿＿kn</div>
    </div>
  </header>
  <div class="mapwrap">
    <svg class="map" viewBox="0 0 {W_M:.1f} {H_M:.1f}" xmlns="http://www.w3.org/2000/svg">
      <polygon points="{land_polygon('north')}" class="land"/>
      <polygon points="{land_polygon('south')}" class="land"/>
      {grid()}
      {coast_svg}
      {''.join(ferry_svg)}
      {bridge_svg}
      <polyline points="{path_of(WEST)}" class="route w"/>
      <polyline points="{path_of(EAST)}" class="route e"/>
      {''.join(nums)}
      {places}
      <text x="{mx(133.199):.1f}" y="{my(34.4087):.1f}" class="note">西航は実線（北側）　東航は破線（南側）</text>
      <text x="{mx(133.1926):.1f}" y="{my(34.4057):.1f}" class="note">灯台突出部は狭くなる</text>
      <text x="{mx(133.2142):.1f}" y="{my(34.4067):.1f}" class="note">東口は図の東外</text>
      <g class="scalebar">
        <rect x="{W_M - 620:.1f}" y="{H_M - 90:.1f}" width="500" height="18" fill="#fbf8f2" stroke="#1c1915" stroke-width="3"/>
        <rect x="{W_M - 620:.1f}" y="{H_M - 90:.1f}" width="250" height="18" fill="#1c1915"/>
        <text x="{W_M - 620:.1f}" y="{H_M - 108:.1f}" class="gridlab">0</text>
        <text x="{W_M - 370:.1f}" y="{H_M - 108:.1f}" class="gridlab" text-anchor="middle">250m</text>
        <text x="{W_M - 120:.1f}" y="{H_M - 108:.1f}" class="gridlab" text-anchor="end">500m</text>
      </g>
    </svg>
    <div class="mapkey">
      <div><i class="swatch"></i>西航　中央桟橋→新浜桟橋（北岸寄り）</div>
      <div><i class="swatch e"></i>東航　新浜桟橋→中央桟橋（向島寄り）</div>
      <div><i class="swatch f"></i>渡船の横断　2航路</div>
      <div>北は上。左下の白黒棒は500m。</div>
    </div>
  </div>
  <div class="cols">
    <section>
      <h2>（1）基準経路　発着場・針路・変針点</h2>
      <p>常用経路は中央桟橋と新浜桟橋の間。西航は可航水域の北側、東航は南側を通る。尾道灯台の突出部では東航も灯台を右舷に見て、北側の可航水域に寄る。桟橋を離れた直後と着桟の直前だけ航路を横断する。</p>
      <p class="sub">西航　中央桟橋 → 新浜桟橋　{west_nm:.2f}海里</p>
      <table>
        <tr><th>自</th><th>至</th><th>針路</th><th>海里</th><th>m</th></tr>
        {west_rows}
      </table>
      <p class="sub">東航　新浜桟橋 → 中央桟橋　{east_nm:.2f}海里</p>
      <table>
        <tr><th>自</th><th>至</th><th>針路</th><th>海里</th><th>m</th></tr>
        {east_rows}
      </table>
      <p>針路は真方位で、表は1度単位。距離は無流の概算で、潮流による偏位を含まない。無流・8ノットで西航約{west_nm / 8 * 60:.0f}分、東航約{east_nm / 8 * 60:.0f}分。6ノットで約{west_nm / 6 * 60:.0f}分、約{east_nm / 6 * 60:.0f}分。航海速力は船舶の速力基準による。</p>
      <p>中央桟橋（海の駅の公表位置）{fmt_lat(34.407550)} {fmt_lon(133.202417)}。新浜桟橋 {fmt_lat(34.398801)} {fmt_lon(133.177452)}。桟橋間の直線は{2488 / 1852:.2f}海里・真方位247°／067°だが、直線は灯台の突出に寄るため使わない。</p>
    </section>
    <section>
      <h2>（2）地形・水深・潮流で特に留意する箇所</h2>
      <p class="sub">潮流（水道の全域）</p>
      <p>東流の最強2.7ノット、西流の最強2.5ノット。東流は尾道の低潮の約40分後から高潮の約40分後で、最強は高潮の約2時間25分前。西流は高潮の約40分後から低潮の約40分後で、最強は低潮の約2時間25分前。転流は来島海峡より約15分遅れる。当日の推算は尾道海上保安部の発表で確認する。流れは岸にほぼ並行するので、離着桟は当て舵と増減速の余裕を持つ。</p>
      <p class="sub">水深と地形</p>
      <p>西口は約9m。東口の最狭部（戸崎瀬戸方面、本図の東外）は幅約50m、水深約4mの箇所がある。常用経路はこの最狭部を通らない。尾道灯台（小歌島）が水道へ突出する。東航は⑨で灯台を右舷に見て北側の可航水域へ寄る。両岸に係留船が続く。桟橋前面の水深は海図による。本図に等深線はない。</p>
      <p class="sub">渡船・橋梁・架空線</p>
      <p>土堂―兼吉、駅前―富浜の渡船が頻繁に水道を横断する。横断帯では減速し、渡船の進路を避ける。福本渡船は令和7年3月31日に廃止。東側へ出るときは尾道大橋（高さ34m）と新尾道大橋（高さ36m）。南西の御幸瀬戸は向島大橋（高さ約13m）と架空線（高さ28m）。水道西部（34°23.6′N 133°09.7′E付近）に架空線（高さ51m）。高さは水路誌の記載で、潮が上がると余裕は減る。</p>
    </section>
    <section>
      <h2>（3）航行の安全を確保するため必要な事項</h2>
      <ul>
        <li>総トン数20トン未満は港則法の汽艇等であり、航路を航行する義務はない。汽艇等以外の船舶の進路を避ける。</li>
        <li>20トン以上の船舶は、特定港への出入と通過に航路を用いる。やむを得ない場合を除く。</li>
        <li>航路への出入と横断は、航路を航行する船舶の進路を避ける。航路内は右側を通り、並航も追越しもせず、錨泊しない。</li>
        <li>第二航路は中心線の両側各25m。東口最狭部では、この幅が可航幅になる。法線は海図に従う。</li>
        <li>港内は、他船に危険を及ぼさない速力とする。渡船の横断帯と離着桟は微速とする。</li>
        <li>第三区では、岸壁又は桟橋に係留中の船舶の船側に係留しない。</li>
        <li>旅客船、漁船、作業船、プレジャーボート、造船所の船舶がふくそうする。航路中央の大型船を妨げない。</li>
        <li>視程が低下したときは減速し、見張りを増やす。安全な速力を保てなければ反転又は待機する。</li>
        <li>通過連絡は、①と②の間の土堂渡船横断と、③駅前渡船沖。地点名、時刻、天候、風向、風速、波浪、視程を運航管理者へ連絡する。</li>
        <li>中央ビジター桟橋は、尾道みなと祭と住吉花火大会の日は休業する。</li>
        <li>緊急通報は118。尾道海上保安部（港長）は0848-22-2108、尾道市古浜町。</li>
        <li>発航前に海図、潮汐表、水路通報、当日の潮流推算を確認し、基準経路と避険線を海図へ記入する。</li>
      </ul>
    </section>
  </div>
  <footer>
    出典：海上保安庁『瀬戸内海水路誌』追補（書誌103、令和8年1月30日）尾道水道。港則法第3条・第11条・第12条・第13条・第16条・第18条。港則法施行規則第34条・別表第二（第二航路）。中央桟橋の位置はおのみち海の駅の公表値。新浜桟橋・渡船場の位置はOpenStreetMap（令和8年11月）。岸線は同海岸線を模式化。
    本図は運航基準を示す模式図であり、航海用海図ではない。針路と距離は世界測地系の概算である。航海には最新の海図W119、潮汐表、水路通報と、船長の判断を用いる。印刷はA3横、倍率100%、余白なし。
  </footer>
</article>
</body>
</html>
"""

out = ROOT / "onomichi-unko-kijunzu.html"
out.write_text(html, encoding="utf-8")
print(f"wrote {out}")
print(f"west {west_nm:.3f} NM  east {east_nm:.3f} NM")
for label, rows in (("W", WEST_LEGS), ("E", EAST_LEGS)):
    for a, b, brg, dist in rows:
        print(f"  {label} {a[0]}->{b[0]} {brg:.1f}° {dist:.0f}m")
