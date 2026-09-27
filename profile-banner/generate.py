"""Renders the animated profile banner. Every tunable value lives in config.toml; this file
holds the drawing logic and the values derived from that config."""

import argparse
import base64
import json
import os
import random
import tomllib
from datetime import datetime
from string import Template
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

with open(os.path.join(BASE_DIR, "config.toml"), "rb") as _f:
    CFG = tomllib.load(_f)

WIDTH = CFG["canvas"]["width"]
HEIGHT = CFG["canvas"]["height"]
OUTPUT_PATH = os.path.join(BASE_DIR, CFG["output"]["file"])

TIMEZONE = os.environ.get("TIMEZONE", CFG["phase"]["timezone"])
NIGHT_START_HOUR = CFG["phase"]["night_start_hour"]
NIGHT_END_HOUR = CFG["phase"]["night_end_hour"]

PHASES = CFG["colors"]
SUN = CFG["sun"]
CLOUDS = CFG["clouds"]
MOUNTAINS = CFG["mountains"]
SIGNS = CFG["signs"]
SCENERY = CFG["scenery"]
GROVE = CFG["scenery"]["grove"]
CAR = CFG["car"]

GRASS_Y = CFG["layout"]["grass_y"]
ROAD_Y = CFG["layout"]["road_y"]
ROAD_HEIGHT = CFG["layout"]["road_height"]
ROAD_EDGE_HEIGHT = CFG["layout"]["road_edge_height"]

LANE_DASH_SHIFT = CFG["road"]["dash_shift"]
LANE_DUR = CFG["road"]["dash_dur"]
LANE_Y = ROAD_Y + ROAD_HEIGHT // 2
# The apparent speed of the road surface. Anything meant to be standing still on the roadside
# travels at exactly this speed, or it visually slides against the tarmac.
ROAD_SPEED = LANE_DASH_SHIFT / LANE_DUR  # px per second

SIGN_BASE_Y = ROAD_Y + SIGNS["post_base_offset"]
SCENERY_BASE_Y = ROAD_Y + SCENERY["base_offset"]
SIGN_PASS_DUR = (WIDTH + 2 * SIGNS["travel_margin"]) / ROAD_SPEED

CAR_DISPLAY_WIDTH = CAR["display_width"]
CAR_DISPLAY_HEIGHT = round(CAR_DISPLAY_WIDTH / CAR["aspect"])
CAR_ANCHOR_Y = LANE_Y + 1  # car "stands" on the lane line

_template_cache = {}


def load_template(name):
    if name not in _template_cache:
        with open(os.path.join(TEMPLATES_DIR, f"{name}.tpl")) as f:
            _template_cache[name] = Template(f.read())
    return _template_cache[name]


def render(name, **kwargs):
    return load_template(name).substitute(**kwargs).rstrip("\n")


def generate_stars():
    rng = random.Random(CFG["stars"]["seed"])
    return [
        dict(cx=round(rng.uniform(10, WIDTH - 10), 1),
             cy=round(rng.uniform(6, GRASS_Y - 20), 1),
             r=round(rng.uniform(0.8, 1.8), 1))
        for _ in range(CFG["stars"]["count"])
    ]


STARS = generate_stars()


def car_image_data_uri():
    # Inlined as a data: URI rather than a relative href: when GitHub displays this SVG via
    # <img src="...">, the browser loads it in a locked-down "image" context that blocks the
    # SVG from fetching any further external resources (a security restriction, not a path
    # bug) - so the car image has to be self-contained inside the SVG itself.
    with open(os.path.join(BASE_DIR, CAR["image"]), "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def build_defs(phase):
    return render("defs", sky_top=phase["sky_top"], sky_bottom=phase["sky_bottom"])


def build_sky_and_sun(is_night):
    if is_night:
        stars = "\n".join(render("star", cx=s["cx"], cy=s["cy"], r=s["r"]) for s in STARS)
        return render("sky_night", width=WIDTH, height=HEIGHT, stars=stars)
    return render("sky_day", width=WIDTH, height=HEIGHT,
                  cx=SUN["cx"], cy=SUN["cy"], r=SUN["r"], fill=SUN["fill"])


def build_mountains(phase):
    rng = random.Random(MOUNTAINS["seed"])
    range_width, step = MOUNTAINS["range_width"], MOUNTAINS["step"]
    base_y = GRASS_Y + 2  # feet sit just under the horizon, so the grass hides them
    # Both ranges share one cycle and start together, so they arrive as a single event and
    # the horizon is genuinely empty between appearances. Independent cycles per layer would
    # overlap and keep a range on screen almost permanently. The nearer range still crosses
    # faster and pulls ahead of the far one, which is what keeps the parallax visible.
    passes = [(WIDTH + range_width) / (ROAD_SPEED * layer["speed"])
              for layer in MOUNTAINS["layers"]]
    cycle_dur = max(passes) / MOUNTAINS["visible_share"]

    layers = []
    for layer, pass_dur in zip(MOUNTAINS["layers"], passes):
        xs = list(range(0, range_width + 1, step))
        # Alternate valley/peak for triangular ridges rather than a soft zigzag; both ends
        # drop to ground level so the range rises out of the horizon instead of being cut off.
        heights = [0.0 if i in (0, len(xs) - 1)
                   else rng.uniform(*(layer["peak"] if i % 2 else layer["valley"]))
                   for i in range(len(xs))]
        layers.append(render(
            "mountain_range",
            x_start=WIDTH, x_end=-range_width,
            move_end=round(pass_dur / cycle_dur, 6),
            dur=round(cycle_dur, 2), begin=0,
            points=" ".join(f"{x},{base_y - h:.1f}" for x, h in zip(xs, heights)),
            color=phase[layer["color"]],
        ))
    return render("mountains", layers="\n".join(layers))


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
        grass_y=GRASS_Y, grass_height=HEIGHT - GRASS_Y, grass_color=phase["grass"],
        road_y=ROAD_Y, road_height=ROAD_HEIGHT,
        road_edge_height=ROAD_EDGE_HEIGHT,
        road_bottom_edge_y=ROAD_Y + ROAD_HEIGHT - ROAD_EDGE_HEIGHT,
        road_color=phase["road"], road_edge_color=phase["road_edge"],
        width=WIDTH,
    )


def build_lane(phase):
    shift = LANE_DASH_SHIFT if CFG["road"]["lane_reversed"] else -LANE_DASH_SHIFT
    return render(
        "lane",
        lane_y=LANE_Y, width=WIDTH, lane_color=phase["lane"],
        lane_width=CFG["road"]["lane_width"], lane_dash=CFG["road"]["lane_dash"],
        dash_from="0", dash_to=str(shift), lane_dur=LANE_DUR,
    )


def load_messages():
    # Each message is either a single line of text, or a list of lines to stack on the board.
    with open(os.path.join(BASE_DIR, SIGNS["messages_file"])) as f:
        messages = json.load(f)["messages"]

    resolved = []
    for message in messages:
        lines = [message] if isinstance(message, str) else message
        cleaned = []
        for line in lines:
            line = " ".join(line.split())
            if len(line) > SIGNS["max_chars"]:
                line = line[:SIGNS["max_chars"] - 1].rstrip() + "…"
            cleaned.append(line)
        resolved.append(cleaned)
    return resolved


def build_pine_grove(rng, colors):
    tree = render("pine", **colors)
    spread = GROVE["spread"]
    count = rng.randint(*GROVE["size"])
    step = (2 * spread) / (count - 1)
    trees = [
        (round(-spread + i * step + rng.uniform(-4, 4), 1),
         round(rng.uniform(*GROVE["scale_range"]), 2))
        for i in range(count)
    ]
    # Smallest first, so the larger trees overlap them and the cluster reads as having depth;
    # the smaller ones also sit slightly higher, as though further back up the verge.
    trees.sort(key=lambda t: t[1])
    return "\n".join(
        render("grove_tree", dx=dx, dy=round(-(1 - scale) * 7, 1), scale=scale, tree=tree)
        for dx, scale in trees
    )


def build_scenery(phase):
    shape_colors = {
        "pine": dict(foliage=phase["tree_foliage"], trunk=phase["tree_trunk"]),
        "sheep": dict(light=phase["animal_light"], dark=phase["animal_dark"]),
    }
    rng = random.Random(SCENERY["seed"])
    count, jitter = SCENERY["count"], SCENERY["gap_jitter"]
    gaps = [SCENERY["gap"] + rng.uniform(-jitter, jitter) for _ in range(count)]
    # The cycle is the sum of the gaps, so the last object is one gap behind the first
    # when the loop restarts and the roadside scrolls past seamlessly.
    cycle_dur = max(sum(gaps), SIGN_PASS_DUR)

    kinds = SCENERY["kinds"]
    deck = (kinds * (count // len(kinds) + 1))[:count]
    rng.shuffle(deck)

    items = []
    begin = 0.0
    for gap, kind in zip(gaps, deck):
        items.append(render(
            "scenery_item",
            x_start=WIDTH + SIGNS["travel_margin"], x_end=-SIGNS["travel_margin"],
            move_end=round(SIGN_PASS_DUR / cycle_dur, 6),
            dur=round(cycle_dur, 3), begin=round(begin, 3),
            base_y=SCENERY_BASE_Y + rng.randint(*SCENERY["base_jitter"]),
            scale=round(rng.uniform(*SCENERY["scale_range"]), 2),
            shape=(build_pine_grove(rng, shape_colors["pine"]) if kind == "grove"
                   else render(kind, **shape_colors[kind])),
        ))
        begin += gap
    return render("scenery", items="\n".join(items))


def build_signs(phase):
    messages = load_messages()
    font_size, line_height = SIGNS["font_size"], SIGNS["line_height"]
    pad_x, pad_y = SIGNS["pad_x"], SIGNS["pad_y"]
    bottom_y, post_inset = SIGNS["board_bottom_y"], SIGNS["post_inset"]
    # Signs are released every `spacing` seconds and each takes SIGN_PASS_DUR to cross, so
    # SIGN_PASS_DUR / spacing of them are in flight at once. The cycle can never be shorter
    # than a single pass, or a sign would still be crossing when it is due to restart.
    cycle_dur = max(SIGNS["spacing"] * len(messages), SIGN_PASS_DUR)

    items = []
    for index, lines in enumerate(messages):
        widest = max(len(line) for line in lines)
        board_width = min(
            max(round(widest * (SIGNS["char_width"] + SIGNS["letter_spacing"])) + 2 * pad_x,
                SIGNS["board_min_width"]),
            SIGNS["board_max_width"])
        board_height = len(lines) * line_height + 2 * pad_y
        board_y = bottom_y - board_height
        half_width = board_width / 2

        # Each line is centred in its own line box, so the stack sits centred in the board
        # with pad_y of clear space above and below it.
        rendered_lines = "\n".join(
            render(
                "sign_line",
                y=round(board_y + pad_y + line_index * line_height
                        + line_height / 2 + font_size * 0.35, 1),
                font_family=SIGNS["font_family"], font_size=font_size,
                letter_spacing=SIGNS["letter_spacing"],
                text_color=phase["sign_text"], text=escape(line),
            )
            for line_index, line in enumerate(lines)
        )

        items.append(render(
            "sign",
            x_start=WIDTH + SIGNS["travel_margin"], x_end=-SIGNS["travel_margin"],
            move_end=round(SIGN_PASS_DUR / cycle_dur, 6),
            dur=round(cycle_dur, 3), begin=round(SIGNS["spacing"] * index, 3),
            board_x=round(-half_width, 1), board_y=board_y,
            board_w=board_width, board_h=board_height,
            board_color=phase["sign_board"], border_color=phase["sign_border"],
            post_color=phase["sign_post"],
            post1_x=round(-half_width + post_inset, 1),
            post2_x=round(half_width - post_inset - SIGNS["post_width"], 1),
            post_y=bottom_y, post_w=SIGNS["post_width"],
            post_h=SIGN_BASE_Y - bottom_y,
            lines=rendered_lines,
        ))
    return render("signs", items="\n".join(items))


def build_car():
    return render(
        "car",
        anchor_x=CAR["anchor_x"], anchor_y=CAR_ANCHOR_Y,
        rock_amplitude=CAR["rock_amplitude"], rock_dur=CAR["rock_dur"],
        bounce_values="; ".join(f"0 {v}" for v in CAR["bounce_amplitudes"]),
        bounce_dur=CAR["bounce_dur"],
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
        mountains=build_mountains(phase),
        clouds=build_clouds(),
        ground=build_ground(phase),
        lane=build_lane(phase),
        scenery=build_scenery(phase),
        signs=build_signs(phase),
        car=build_car(),
    ) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["day", "night", "auto"], default="auto",
                        help=f"Force day/night, or auto-detect from the current time in {TIMEZONE}")
    args = parser.parse_args()

    phase_name = args.phase
    if phase_name == "auto":
        phase_name = "night" if is_night_now() else "day"

    with open(OUTPUT_PATH, "w") as f:
        f.write(build_svg(phase_name))
    print(f"Wrote {OUTPUT_PATH} (phase={phase_name})")


if __name__ == "__main__":
    main()
