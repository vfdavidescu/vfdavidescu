import argparse
import base64
import os
import random
from datetime import datetime
from zoneinfo import ZoneInfo

WIDTH, HEIGHT = 900, 200

TIMEZONE = os.environ.get("TIMEZONE", "Europe/Bucharest")
NIGHT_START_HOUR = 20  # 8pm
NIGHT_END_HOUR = 7     # 7am

PHASES = {
    "day": dict(
        sky_top="#8fc7f2",
        sky_bottom="#e6f4fb",
        grass_color="#79a15c",
        road_color="#3a3d40",
        road_edge_color="#55585b",
        lane_color="#f4f4f4",
    ),
    "night": dict(
        sky_top="#0b1226",
        sky_bottom="#2a3a5c",
        grass_color="#233626",
        road_color="#1c1d1f",
        road_edge_color="#33353a",
        lane_color="#c9c9c9",
    ),
}

SUN = dict(cx=800, cy=34, r=20, fill="#ffd85e")

CLOUDS = [
    dict(y=28, dur=26, begin=0, rx1=28, ry1=11, rx2=17, ry2=8, dx2=22, dy2=-6),
    dict(y=48, dur=34, begin=-12, rx1=20, ry1=8, rx2=13, ry2=6, dx2=16, dy2=-4),
]

GRASS_Y = 108


def _generate_stars(count=60, seed=1337):
    rng = random.Random(seed)
    return [
        dict(cx=round(rng.uniform(10, WIDTH - 10), 1),
             cy=round(rng.uniform(6, GRASS_Y - 20), 1),
             r=round(rng.uniform(0.8, 1.8), 1))
        for _ in range(count)
    ]


STARS = _generate_stars()

ROAD_Y = 142
ROAD_HEIGHT = 44
ROAD_EDGE_HEIGHT = 4

LANE_Y = ROAD_Y + ROAD_HEIGHT // 2
LANE_WIDTH = 5
LANE_DASH = "38 28"
LANE_DUR = 0.9
LANE_REVERSED = True  # flow left-to-right (matches car travel direction)

# Car
CAR_IMAGE = "assets/car.png"
CAR_ASPECT = 486 / 179  # width / height of the source image (after cropping)
CAR_DISPLAY_WIDTH = 190
CAR_DISPLAY_HEIGHT = round(CAR_DISPLAY_WIDTH / CAR_ASPECT)
CAR_ANCHOR_X = 260       # horizontal position of the car on the banner
CAR_ANCHOR_Y = LANE_Y + 1  # car "stands" on the lane line
CAR_ROCK_AMPLITUDE = 8   # px, how far it rocks forward/back
CAR_ROCK_DUR = 4.5       # seconds per full rock cycle
CAR_BOUNCE_AMPLITUDES = [0, -1, 0, -0.7, 0]  # vertical suspension bounce keyframes
CAR_BOUNCE_DUR = 0.6

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
OUTPUT_PATH = os.path.join(REPO_ROOT, "profile-banner..svg")


def car_image_data_uri():
    # Inlined as a data: URI rather than a relative href: when GitHub displays this SVG via
    # <img src="profile-banner.svg">, the browser loads it in a locked-down "image" context that
    # blocks the SVG from fetching any further external resources (a security restriction,
    # not a path bug) - so the car image has to be self-contained inside the SVG itself.
    image_path = os.path.join(REPO_ROOT, CAR_IMAGE)
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{encoded}"

def build_defs(phase):
    parts = [
        '  <defs>',
        '    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">',
        f'      <stop offset="0%" stop-color="{phase["sky_top"]}"/>',
        f'      <stop offset="100%" stop-color="{phase["sky_bottom"]}"/>',
        '    </linearGradient>',
    ]
    parts.append('  </defs>')
    return "\n".join(parts)


def build_sky_and_sun(is_night):
    parts = [f'  <rect width="{WIDTH}" height="{HEIGHT}" fill="url(#sky)"/>']
    if is_night:
        parts.append('  <g fill="#f2f0e6">')
        for s in STARS:
            parts.append(f'    <circle cx="{s["cx"]}" cy="{s["cy"]}" r="{s["r"]}"/>')
        parts.append('  </g>')
    else:
        parts.append(f'  <circle cx="{SUN["cx"]}" cy="{SUN["cy"]}" r="{SUN["r"]}" fill="{SUN["fill"]}"/>')
    return "\n".join(parts)


def build_clouds():
    parts = ['  <g fill="#ffffff" opacity="0.95">']
    for c in CLOUDS:
        parts += [
            '    <g>',
            f'      <ellipse cx="0" cy="0" rx="{c["rx1"]}" ry="{c["ry1"]}"/>',
            f'      <ellipse cx="{c["dx2"]}" cy="{c["dy2"]}" rx="{c["rx2"]}" ry="{c["ry2"]}"/>',
            f'      <animateTransform attributeName="transform" type="translate" '
            f'values="{WIDTH + 40} {c["y"]}; -120 {c["y"]}" dur="{c["dur"]}s" begin="{c["begin"]}s" repeatCount="indefinite"/>',
            '    </g>',
        ]
    parts.append('  </g>')
    return "\n".join(parts)


def build_ground(phase):
    return "\n".join([
        f'  <rect y="{GRASS_Y}" width="{WIDTH}" height="{HEIGHT - GRASS_Y}" fill="{phase["grass_color"]}"/>',
        f'  <rect y="{ROAD_Y}" width="{WIDTH}" height="{ROAD_HEIGHT}" fill="{phase["road_color"]}"/>',
        f'  <rect y="{ROAD_Y}" width="{WIDTH}" height="{ROAD_EDGE_HEIGHT}" fill="{phase["road_edge_color"]}"/>',
        f'  <rect y="{ROAD_Y + ROAD_HEIGHT - ROAD_EDGE_HEIGHT}" width="{WIDTH}" height="{ROAD_EDGE_HEIGHT}" fill="{phase["road_edge_color"]}"/>',
    ])


def build_lane(phase):
    dash_from, dash_to = ("0", "132") if LANE_REVERSED else ("0", "-132")
    return "\n".join([
        f'  <line x1="0" y1="{LANE_Y}" x2="{WIDTH}" y2="{LANE_Y}" stroke="{phase["lane_color"]}" '
        f'stroke-width="{LANE_WIDTH}" stroke-dasharray="{LANE_DASH}">',
        f'    <animate attributeName="stroke-dashoffset" from="{dash_from}" to="{dash_to}" '
        f'dur="{LANE_DUR}s" repeatCount="indefinite"/>',
        '  </line>',
    ])


def build_car():
    bounce_values = "; ".join(f"0 {v}" for v in CAR_BOUNCE_AMPLITUDES)
    return "\n".join([
        f'  <g transform="translate({CAR_ANCHOR_X},{CAR_ANCHOR_Y})">',
        '    <g>',
        f'      <animateTransform attributeName="transform" type="translate" '
        f'values="-{CAR_ROCK_AMPLITUDE} 0; {CAR_ROCK_AMPLITUDE} 0; -{CAR_ROCK_AMPLITUDE} 0" '
        f'keyTimes="0; 0.5; 1" calcMode="spline" keySplines="0.42 0 0.58 1; 0.42 0 0.58 1" '
        f'dur="{CAR_ROCK_DUR}s" repeatCount="indefinite"/>',
        '      <g>',
        f'        <animateTransform attributeName="transform" type="translate" values="{bounce_values}" '
        f'dur="{CAR_BOUNCE_DUR}s" repeatCount="indefinite" additive="sum"/>',
        f'        <image href="{car_image_data_uri()}" x="{-CAR_DISPLAY_WIDTH // 2}" y="{-CAR_DISPLAY_HEIGHT}" '
        f'width="{CAR_DISPLAY_WIDTH}" height="{CAR_DISPLAY_HEIGHT}" preserveAspectRatio="xMidYMid meet"/>',
        '      </g>',
        '    </g>',
        '  </g>',
    ])


def is_night_now():
    hour = datetime.now(ZoneInfo(TIMEZONE)).hour
    return hour >= NIGHT_START_HOUR or hour < NIGHT_END_HOUR


def build_svg(phase_name):
    is_night = phase_name == "night"
    phase = PHASES[phase_name]
    label = "Animated car on a roadside at night" if is_night else "Animated car on a roadside"
    return "\n".join([
        f'<svg viewBox="0 0 {WIDTH} {HEIGHT}" xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="{label}">',
        build_defs(phase),
        '',
        build_sky_and_sun(is_night),
        '',
        build_clouds(),
        '',
        build_ground(phase),
        '',
        build_lane(phase),
        '',
        build_car(),
        '</svg>',
        '',
    ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["day", "night", "auto"], default="auto",
                         help=f"Force day/night, or auto-detect from the current time in {TIMEZONE}")
    args = parser.parse_args()

    if args.phase == "auto":
        phase_name = "night" if is_night_now() else "day"
    else:
        phase_name = args.phase

    svg = build_svg(phase_name)
    out_path = os.path.normpath(OUTPUT_PATH)
    with open(out_path, "w") as f:
        f.write(svg)
    print(f"Wrote {out_path} (phase={phase_name})")


if __name__ == "__main__":
    main()
