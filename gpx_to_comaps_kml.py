#!/usr/bin/env python3
"""Convert GaiaGPS GPX export to CoMaps-compatible KML.

Why KML instead of enriched GPX?
  The CoMaps GPX parser never sets the track-level timestamp used for
  sorting in the UI. The KML parser does read <TimeStamp><when> and uses
  it for sort-by-date. Colors and folder names also require KML.

What the output KML provides:
  - Unique color per track (golden-ratio hue distribution)
  - <TimeStamp><when> from the first trkpt → enables sort-by-date in CoMaps
  - Track name prefixed with recording date: "YYYY-MM-DD Original name"
  - <Document><name>Gaia GPS import</name> → folder name in CoMaps
  - Point-level timestamps preserved via <gx:Track> for speed graphs
  - Tracks without any timestamps fall back to <LineString>

Usage:
  python3 gpx_to_comaps_kml.py input.gpx              # writes input.kml
  python3 gpx_to_comaps_kml.py input.gpx output.kml
"""

import sys
import math
import colorsys
from datetime import datetime
from xml.etree import ElementTree as ET

GPX_NS = "http://www.topografix.com/GPX/1/1"


def gpx(tag):
    return f"{{{GPX_NS}}}{tag}"


def parse_time(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def to_abgr(r, g, b, a=255):
    """RGB (0-255) → KML ABGR hex string."""
    return f"{a:02X}{b:02X}{g:02X}{r:02X}"


def distinct_colors(n):
    """n visually distinct fully-opaque colors via golden-ratio hue spacing."""
    if n == 0:
        return []
    golden = (1 + math.sqrt(5)) / 2
    colors = []
    h = 0.0
    for _ in range(n):
        r, g, b = colorsys.hsv_to_rgb(h % 1.0, 0.85, 0.90)
        colors.append(to_abgr(int(r * 255), int(g * 255), int(b * 255)))
        h += 1.0 / golden
    return colors


def escape_xml(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def first_time_in_track(trksegs):
    for seg in trksegs:
        for pt in seg.findall(gpx("trkpt")):
            t_el = pt.find(gpx("time"))
            if t_el is not None and t_el.text:
                return parse_time(t_el.text)
    return None


def point_data(pt):
    lon = pt.get("lon", "0")
    lat = pt.get("lat", "0")
    ele_el = pt.find(gpx("ele"))
    ele = ele_el.text.strip() if ele_el is not None and ele_el.text else "0"
    return lon, lat, ele


def render_gx_track(seg_pts, indent):
    out = [f"{indent}<gx:Track>"]
    for pt in seg_pts:
        t_el = pt.find(gpx("time"))
        t_str = t_el.text.strip() if t_el is not None and t_el.text else ""
        out.append(f"{indent}  <when>{t_str}</when>")
    for pt in seg_pts:
        lon, lat, ele = point_data(pt)
        out.append(f"{indent}  <gx:coord>{lon} {lat} {ele}</gx:coord>")
    out.append(f"{indent}</gx:Track>")
    return "\n".join(out)


def render_linestring(seg_pts, indent):
    coords = " ".join(f"{lon},{lat},{ele}" for lon, lat, ele in (point_data(p) for p in seg_pts))
    return f"{indent}<LineString><coordinates>{coords}</coordinates></LineString>"


def convert(gpx_path, kml_path):
    tree = ET.parse(gpx_path)
    root = tree.getroot()
    tracks = root.findall(gpx("trk"))
    colors = distinct_colors(len(tracks))

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://earth.google.com/kml/2.2"'
        ' xmlns:gx="http://www.google.com/kml/ext/2.2">',
        "<Document>",
        "  <name>Gaia GPS import</name>",
    ]

    for i, trk in enumerate(tracks):
        name_el = trk.find(gpx("name"))
        name = name_el.text.strip() if name_el is not None and name_el.text else f"Track {i + 1}"

        desc_el = trk.find(gpx("desc"))
        desc = desc_el.text.strip() if desc_el is not None and desc_el.text else ""

        trksegs = trk.findall(gpx("trkseg"))
        first_t = first_time_in_track(trksegs)

        if first_t:
            date_str = first_t.strftime("%Y-%m-%d")
            display_name = f"{date_str} {name}"
            ts_when = first_t.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            display_name = name
            ts_when = None

        out += [
            "",
            "  <Placemark>",
            f"    <name>{escape_xml(display_name)}</name>",
        ]

        if desc:
            out.append(f"    <description>{escape_xml(desc)}</description>")

        if ts_when:
            out += [
                "    <TimeStamp>",
                f"      <when>{ts_when}</when>",
                "    </TimeStamp>",
            ]

        out += [
            "    <Style>",
            "      <LineStyle>",
            f"        <color>{colors[i]}</color>",
            "        <width>3</width>",
            "      </LineStyle>",
            "    </Style>",
        ]

        # Split segments by timestamp presence
        segs_with_ts = []
        segs_without_ts = []
        for seg in trksegs:
            pts = seg.findall(gpx("trkpt"))
            if not pts:
                continue
            has_ts = any(pt.find(gpx("time")) is not None for pt in pts)
            (segs_with_ts if has_ts else segs_without_ts).append(pts)

        # Segments without timestamps → <LineString>
        if segs_without_ts:
            if len(segs_without_ts) > 1:
                out.append("    <MultiGeometry>")
                for pts in segs_without_ts:
                    out.append(render_linestring(pts, indent="      "))
                out.append("    </MultiGeometry>")
            else:
                out.append(render_linestring(segs_without_ts[0], indent="    "))

        # Segments with timestamps → <gx:Track>
        if segs_with_ts:
            if len(segs_with_ts) > 1:
                out.append("    <gx:MultiTrack>")
                for pts in segs_with_ts:
                    out.append(render_gx_track(pts, indent="      "))
                out.append("    </gx:MultiTrack>")
            else:
                out.append(render_gx_track(segs_with_ts[0], indent="    "))

        out.append("  </Placemark>")

    out += ["</Document>", "</kml>"]

    with open(kml_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")

    no_date = sum(1 for trk in tracks if first_time_in_track(trk.findall(gpx("trkseg"))) is None)
    print(f"Converted {len(tracks)} track(s) → {kml_path}")
    if no_date:
        print(f"  Note: {no_date} track(s) had no timestamps — they appear without a date prefix")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} input.gpx [output.kml]")
        sys.exit(1)

    gpx_path = sys.argv[1]
    if len(sys.argv) > 2:
        kml_path = sys.argv[2]
    elif gpx_path.endswith(".gpx"):
        kml_path = gpx_path[:-4] + ".kml"
    else:
        kml_path = gpx_path + ".kml"

    convert(gpx_path, kml_path)
