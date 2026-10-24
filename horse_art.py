"""レース画面で使う馬のイラスト(SVG)を生成する。

このプロジェクト用に描き下ろしたオリジナルのイラストで、外部の素材は使っていない。
毛色は馬の名前から決まり、騎手の勝負服は脚質の色、鞍の布には馬番が入る。
走っている2コマ分(脚の開き/たたみ)を作り、画面側で交互に切り替えて走って見せる。
"""
from __future__ import annotations

import base64
import hashlib

# 脚質ごとの勝負服の色
SILK = {
    "逃げ": "#e8453c",
    "先行": "#ff9f1c",
    "差し": "#2fb35f",
    "追い込み": "#3d8fe0",
}

# 毛色: (体, 奥側の脚, たてがみ・しっぽ)
COATS = [
    ("#8b5a2b", "#6a421d", "#2b1a0e"),  # 鹿毛
    ("#a65f2e", "#82461f", "#3b2212"),  # 栗毛
    ("#5b3a29", "#432716", "#1c1109"),  # 青鹿毛
    ("#c9a27a", "#a7835d", "#6b4a2b"),  # 河原毛
    ("#9aa0a6", "#7c8288", "#3d4146"),  # 芦毛
    ("#2b2b2e", "#1c1c1e", "#0d0d0e"),  # 黒鹿毛
    ("#b5733a", "#935726", "#e8d9bf"),  # 栗毛(白いたてがみ)
]


def coat_for(name: str):
    h = hashlib.sha1(name.encode("utf-8")).digest()[0]
    return COATS[h % len(COATS)]


def _leg(points, color, width):
    d = "M" + " L".join(f"{x},{y}" for x, y in points)
    hx, hy = points[-1]
    return (
        f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<ellipse cx="{hx}" cy="{hy}" rx="3.4" ry="2.6" fill="#1b1b1b"/>'
    )


def horse_svg(no: int, coat, silk: str, frame: int) -> str:
    body, shade, dark = coat
    if frame == 0:  # 脚をのばした瞬間
        far = [[(74, 48), (92, 57), (102, 60)], [(36, 48), (19, 55), (9, 58)]]
        near = [[(70, 50), (86, 63), (97, 68)], [(40, 50), (25, 62), (14, 67)]]
    else:  # 脚をたたんだ瞬間
        far = [[(72, 50), (68, 63), (77, 68)], [(38, 50), (47, 61), (41, 69)]]
        near = [[(76, 50), (77, 65), (86, 69)], [(34, 50), (35, 64), (28, 71)]]
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 80" width="120" height="80">',
        # しっぽ
        f'<path d="M33,33 C20,29 9,36 4,52 C13,45 21,45 31,42 Z" fill="{dark}"/>',
    ]
    parts += [_leg(p, shade, 5) for p in far]
    parts += [
        # 胴・首・頭
        f'<ellipse cx="55" cy="40" rx="27" ry="14" fill="{body}"/>',
        f'<ellipse cx="72" cy="40" rx="10" ry="13" fill="{body}"/>',
        f'<path d="M72,34 L85,13 L97,22 L84,49 Z" fill="{body}"/>',
        f'<path d="M89,13 C100,11 112,23 115,32 C114,37 108,37 104,34 C98,31 94,28 89,23 Z" fill="{body}"/>',
        f'<ellipse cx="112" cy="33" rx="3.6" ry="2.8" fill="{dark}" opacity=".85"/>',
        f'<path d="M88,14 L90,5 L95,12 Z" fill="{body}"/>',
        '<circle cx="99" cy="20" r="1.6" fill="#111"/>',
        # たてがみ
        f'<path d="M72,31 C77,21 83,13 89,8 L92,16 C86,20 82,28 80,37 Z" fill="{dark}"/>',
    ]
    parts += [_leg(p, body, 5.5) for p in near]
    parts += [
        # 鞍の布と馬番
        f'<rect x="43" y="27" width="22" height="16" rx="2.5" fill="{silk}" stroke="#fff" stroke-width="1.5"/>',
        f'<text x="54" y="40" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" '
        f'font-size="13" font-weight="700" fill="#fff" stroke="#222" stroke-width="2.2" '
        f'paint-order="stroke">{no}</text>',
        # 騎手(前かがみ)
        f'<path d="M51,27 L69,16" stroke="{silk}" stroke-width="10" stroke-linecap="round"/>',
        f'<path d="M66,19 L82,26" stroke="{silk}" stroke-width="4" stroke-linecap="round"/>',
        '<path d="M82,26 L97,22" stroke="#222" stroke-width="1"/>',
        '<circle cx="75" cy="11" r="5.6" fill="#f1c9a5"/>',
        f'<path d="M69.2,11.5 A6,6 0 0 1 81,9.5 L75,11.2 Z" fill="{silk}" stroke="#fff" stroke-width="1"/>',
        "</svg>",
    ]
    return "".join(parts)


def data_uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def horse_images(no: int, name: str, style: str) -> tuple[str, str]:
    coat = coat_for(name)
    silk = SILK[style]
    return tuple(data_uri(horse_svg(no, coat, silk, f)) for f in (0, 1))
