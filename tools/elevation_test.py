#!/usr/bin/env python3
"""
Симулира стария и новия алгоритъм за изчисляване на изкачване/спускане
върху KML треков, за да провери ефекта от threshold филтъра.

Употреба:
    python3 elevation_test.py track.kml
    python3 elevation_test.py *.kml
"""

import re
import sys
import math
from pathlib import Path


EARTH_RADIUS_M = 6_371_000.0
THRESHOLD_M = 8  # kElevationThresholdMeters от C++ кода


def haversine(lat1, lon1, lat2, lon2):
    """Разстояние между две GPS точки в метри."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def parse_kml_coords(kml_text):
    """
    Извлича всички координатни сегменти от KML файл.
    Връща списък от сегменти; всеки сегмент е списък от (lon, lat, alt).
    """
    segments = []
    pattern = re.compile(r'<coordinates>(.*?)</coordinates>', re.DOTALL | re.IGNORECASE)

    for match in pattern.finditer(kml_text):
        points = []
        for token in match.group(1).split():
            parts = token.split(',')
            if len(parts) >= 3:
                try:
                    lon, lat, alt = float(parts[0]), float(parts[1]), float(parts[2])
                    points.append((lon, lat, alt))
                except ValueError:
                    continue
            elif len(parts) == 2:
                try:
                    lon, lat = float(parts[0]), float(parts[1])
                    points.append((lon, lat, None))
                except ValueError:
                    continue
        if len(points) > 1:
            segments.append(points)

    return segments


def calc_old(segments):
    """Стар алгоритъм: сумира ВСЯКА разлика (без филтър)."""
    ascent = descent = length = 0.0
    alts = []

    for seg in segments:
        prev = None
        for lon, lat, alt in seg:
            if alt is None:
                continue
            alt_i = round(alt)  # int16_t truncation като в C++
            alts.append(alt_i)
            if prev is not None:
                delta = alt_i - prev[2]
                if delta > 0:
                    ascent += delta
                else:
                    descent -= delta
                length += haversine(prev[1], prev[0], lat, lon)
            prev = (lon, lat, alt_i)

    return ascent, descent, length, alts


def calc_new(segments, threshold=THRESHOLD_M):
    """Нов алгоритъм: threshold филтър (dead-band), reset на baseline при всеки сегмент."""
    ascent = descent = length = 0.0
    alts = []

    for seg in segments:
        last_confirmed = None
        prev_point = None

        for i, (lon, lat, alt) in enumerate(seg):
            if alt is None:
                continue
            alt_i = round(alt)
            alts.append(alt_i)

            if i == 0:
                last_confirmed = alt_i
                prev_point = (lon, lat, alt_i)
                continue

            delta = alt_i - last_confirmed
            if delta >= threshold:
                ascent += delta
                last_confirmed = alt_i
            elif delta <= -threshold:
                descent -= delta
                last_confirmed = alt_i

            length += haversine(prev_point[1], prev_point[0], lat, lon)
            prev_point = (lon, lat, alt_i)

    return ascent, descent, length, alts


def elevation_profile_stats(alts):
    if not alts:
        return None, None, 0
    return min(alts), max(alts), len(alts)


def analyze_noise(alts):
    """Изчислява стандартното отклонение на последователните разлики — мярка за GPS шум."""
    if len(alts) < 2:
        return 0.0
    diffs = [abs(alts[i] - alts[i - 1]) for i in range(1, len(alts))]
    mean = sum(diffs) / len(diffs)
    variance = sum((d - mean) ** 2 for d in diffs) / len(diffs)
    return math.sqrt(variance), mean, max(diffs)


def report(kml_path):
    text = Path(kml_path).read_text(encoding='utf-8', errors='replace')
    segments = parse_kml_coords(text)

    if not segments:
        print(f"[!] {kml_path}: няма намерени координати.")
        return

    total_points = sum(len(s) for s in segments)
    with_alt = sum(1 for s in segments for p in s if p[2] is not None)

    old_asc, old_desc, length_m, alts_old = calc_old(segments)
    new_asc, new_desc, length_m, alts_new = calc_new(segments)

    min_alt, max_alt, _ = elevation_profile_stats(alts_new)

    print(f"\n{'=' * 60}")
    print(f"  Файл     : {Path(kml_path).name}")
    print(f"  Сегменти : {len(segments)}")
    print(f"  Точки    : {total_points}  (с altitude: {with_alt})")
    print(f"  Дължина  : {length_m / 1000:.2f} km")
    if min_alt is not None:
        print(f"  Altitude : {min_alt} — {max_alt} м")
    print(f"{'=' * 60}")
    print(f"  {'':30} {'Стар':>8}   {'Нов':>8}   {'Разлика':>8}")
    print(f"  {'-' * 58}")
    print(f"  {'Изкачване (ascent)':30} {old_asc:>8.0f} м {new_asc:>8.0f} м "
          f"{new_asc - old_asc:>+8.0f} м")
    print(f"  {'Спускане (descent)':30} {old_desc:>8.0f} м {new_desc:>8.0f} м "
          f"{new_desc - old_desc:>+8.0f} м")

    if old_asc > 0:
        ratio_asc = old_asc / new_asc if new_asc > 0 else float('inf')
        print(f"\n  Старото изкачване е {ratio_asc:.1f}x по-голямо от новото.")

    if alts_old and len(alts_old) >= 2:
        noise_std, noise_mean, noise_max = analyze_noise(alts_old)
        print(f"\n  GPS шум (последователни разлики):")
        print(f"    средно: {noise_mean:.1f} м | σ: {noise_std:.1f} м | макс: {noise_max} м")
        if noise_mean < THRESHOLD_M / 2:
            print(f"    → Типичен GPS шум. Threshold {THRESHOLD_M} м е подходящ.")
        else:
            print(f"    → Данните имат по-едри промени. Може да се обмисли по-висок threshold.")

    print()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    for arg in sys.argv[1:]:
        paths = list(Path('.').glob(arg)) if '*' in arg else [Path(arg)]
        for p in paths:
            if p.suffix.lower() == '.kml':
                report(p)
            else:
                print(f"[!] Пропуснат {p} — не е .kml файл.")


if __name__ == '__main__':
    main()
