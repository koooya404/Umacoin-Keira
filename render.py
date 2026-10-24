"""レース画面(HTML)を組み立てる。"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from game import finish_times
from horse_art import horse_images

TEMPLATE = Path(__file__).parent / "race.html"
LANE_PX = 30
CHROME_PX = 92 + 5 + 5 + 80 + 46  # 空+ラチ+実況欄+ボタン欄(余白込み)


def frame_height(n_horses: int) -> int:
    return CHROME_PX + LANE_PX * n_horses


def _stand_windows() -> str:
    cells = []
    for row in range(2):
        for col in range(40):
            cells.append(f'<rect x="{col * 10 + 2}" y="{30 + row * 12}" width="6" height="7"/>')
    return "".join(cells)


def build_race_html(field: pd.DataFrame, order: list[int], title: str = "") -> str:
    """field: 出走馬(no, name, style ...)。order: 着順どおりに並べた field の行位置。"""
    times = finish_times(len(order))
    rank_of, time_of = {}, {}
    for rank, pos in enumerate(order):
        rank_of[pos] = rank + 1
        time_of[pos] = times[rank]
    horses = []
    for pos, h in field.reset_index(drop=True).iterrows():
        img0, img1 = horse_images(int(h["no"]), h["name"], h["style"])
        horses.append({"no": int(h["no"]), "name": h["name"], "style": h["style"],
                       "rank": rank_of[pos], "T": time_of[pos], "img0": img0, "img1": img1})
    payload = json.dumps({"title": title, "horses": horses}, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8")
    return html.replace("/*DATA*/null", payload).replace("<!--STAND_WINDOWS-->", _stand_windows())
