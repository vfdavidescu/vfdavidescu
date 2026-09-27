import argparse
import base64
import os
import random
from datetime import datetime
from string import Template
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
OUTPUT_PATH = os.path.join(REPO_ROOT, "profile-banner.svg")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

_template_cache = {}


def load_template(name):
    if name not in _template_cache:
        path = os.path.join(TEMPLATES_DIR, f"{name}.tpl")
        with open(path) as f:
            _template_cache[name] = Template(f.read())
    return _template_cache[name]


def render(name, **kwargs):
    return load_template(name).substitute(**kwargs).rstrip("\n")


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
    return render("defs", sky_top=phase["sky_top"], sky_bottom=phase["sky_bottom"])


def build_sky_and_sun(is_night):
    if is_night:
        stars = "\n".join(render("star", cx=s["cx"], cy=s["cy"], r=s["r"]) for s in STARS)
        return render("sky_night", width=WIDTH, height=HEIGHT, stars=stars)
    return render("sky_day", width=WIDTH, height=HEIGHT, cx=SUN["cx"], cy=SUN["cy"], r=SUN["r"], fill=SUN["fill"])


def build_clouds():
    items = "\n".join(
        render(
            "cloud",
            rx1=c["rx1"], ry1=c["ry1"], rx2=c["rx2"], ry2=c["ry2"],
            dx2=c["dx2"], dy2=c["dy2"],
            x_from=WIDTH + 40, x_to=-120, y=c["y"], dur=c["dur"], begin=c["begin"],
        )
        for c in CLOUDS
    )
    return render("clouds", items=items)


def build_ground(phase):
    return render(
        "ground",
        grass_y=GRASS_Y, grass_height=HEIGHT - GRASS_Y,
        grass_color=phase["grass_color"],
        road_y=ROAD_Y, road_height=ROAD_HEIGHT,
        road_edge_height=ROAD_EDGE_HEIGHT,
        road_bottom_edge_y=ROAD_Y + ROAD_HEIGHT - ROAD_EDGE_HEIGHT,
        road_color=phase["road_color"], road_edge_color=phase["road_edge_color"],
        width=WIDTH,
    )


def build_lane(phase):
    dash_from, dash_to = ("0", "132") if LANE_REVERSED else ("0", "-132")
    return render(
        "lane",
        lane_y=LANE_Y, width=WIDTH, lane_color=phase["lane_color"],
        lane_width=LANE_WIDTH, lane_dash=LANE_DASH,
        dash_from=dash_from, dash_to=dash_to, lane_dur=LANE_DUR,
    )


def build_car():
    bounce_values = "; ".join(f"0 {v}" for v in CAR_BOUNCE_AMPLITUDES)
    return render(
        "car",
        anchor_x=CAR_ANCHOR_X, anchor_y=CAR_ANCHOR_Y,
        rock_amplitude=CAR_ROCK_AMPLITUDE, rock_dur=CAR_ROCK_DUR,
        bounce_values=bounce_values, bounce_dur=CAR_BOUNCE_DUR,
        image_uri=car_image_data_uri(),
        img_x=-CAR_DISPLAY_WIDTH // 2, img_y=-CAR_DISPLAY_HEIGHT,
        img_width=CAR_DISPLAY_WIDTH, img_height=CAR_DISPLAY_HEIGHT,
    )


def is_night_now():
    hour = datetime.now(ZoneInfo(TIMEZONE)).hour
    return hour >= NIGHT_START_HOUR or hour < NIGHT_END_HOUR


def build_svg(phase_name):
    is_night = phase_name == "night"
    phase = PHASES[phase_name]
    label = "Animated car on a roadside at night" if is_night else "Animated car on a roadside"
    return render(
        "banner",
        width=WIDTH, height=HEIGHT, label=label,
        defs=build_defs(phase),
        sky=build_sky_and_sun(is_night),
        clouds=build_clouds(),
        ground=build_ground(phase),
        lane=build_lane(phase),
        car=build_car(),
    ) + "\n"


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
