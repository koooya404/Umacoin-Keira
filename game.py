"""ゲームのルール部分(画面には依存しない)。

- 馬データの読み込み(Googleスプレッドシート / 同梱CSV)
- 出走馬の抽選、オッズの計算、着順の決定、払い戻しの計算
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

STYLES = ("逃げ", "先行", "差し", "追い込み")
FIELD_SIZE = 18
START_COINS = 1000
PAYBACK = 0.8  # 控除率。オッズ = 0.8 / 的中確率
MIN_ODDS = 1.1
DATA_CSV = Path(__file__).parent / "data" / "horses.csv"


# ---------- データ読み込み ----------
def normalize_style(value) -> str | None:
    s = re.sub(r"[\s　]", "", str(value))
    if s == "追込":
        s = "追い込み"
    return s if s in STYLES else None


def parse_horses(raw: pd.DataFrame) -> pd.DataFrame:
    """A列=馬の名前、C列=脚質、D列=勝率 の表から馬データを取り出す。

    見出し行や空行は読み飛ばす。列が3つしかない場合は A,B,C を 名前,脚質,勝率 とみなす。
    """
    cols = [0, 2, 3] if raw.shape[1] >= 4 else [0, 1, 2]
    df = raw.iloc[:, cols].copy()
    df.columns = ["name", "style", "weight"]
    df["name"] = df["name"].astype(str).str.strip()
    df["style"] = df["style"].map(normalize_style)
    df["weight"] = pd.to_numeric(df["weight"], errors="coerce")
    df = df[(df["name"] != "") & (df["name"].str.lower() != "nan")]
    df = df.dropna(subset=["style", "weight"])
    df = df[df["weight"] > 0]
    return df.reset_index(drop=True)


def sheet_csv_url(source: str) -> str:
    """スプレッドシートのURL(またはID)を CSV 書き出し用のURLに直す。"""
    source = source.strip()
    m = re.search(r"/spreadsheets/d/([\w-]+)", source)
    sheet_id = m.group(1) if m else source
    gid = re.search(r"[#&?]gid=(\d+)", source)
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    return url + (f"&gid={gid.group(1)}" if gid else "")


def load_horses(source: str | None = None) -> tuple[pd.DataFrame, str]:
    """(馬データ, 読み込み元の説明) を返す。シートが読めなければ同梱CSVに切り替える。"""
    note = ""
    if source and source.strip():
        try:
            raw = pd.read_csv(sheet_csv_url(source), header=None, dtype=str, keep_default_na=False)
            df = parse_horses(raw)
            if len(df) >= 2:
                return df, f"スプレッドシートから {len(df)} 頭を読み込みました。"
            note = "スプレッドシートに有効な馬が2頭未満だったため、同梱データを使っています。"
        except Exception as e:  # ネットワーク不通・非公開シートなど
            note = f"スプレッドシートを読めなかったため同梱データを使っています({type(e).__name__})。リンクを知っている全員に閲覧を許可しているか確認してください。"
    raw = pd.read_csv(DATA_CSV, header=None, dtype=str, keep_default_na=False)
    df = parse_horses(raw)
    return df, note or f"同梱データ(data/horses.csv)から {len(df)} 頭を読み込みました。"


# ---------- レース ----------
def make_field(horses: pd.DataFrame, rng: np.random.Generator, size: int = FIELD_SIZE) -> pd.DataFrame:
    n = min(size, len(horses))
    idx = rng.choice(len(horses), size=n, replace=False)
    field = horses.iloc[idx].reset_index(drop=True)
    field.insert(0, "no", np.arange(1, n + 1))
    return field


def finishing_order(weights, rng: np.random.Generator) -> np.ndarray:
    """重みに比例して勝ちやすい着順を決める(先頭が1着の馬の位置)。

    各馬に「勝率に比例する速さ」の指数乱数をふり、早い順に並べる。
    重み2の馬は重み1の馬の2倍1着になりやすい。
    """
    w = np.asarray(weights, dtype=float)
    return np.argsort(rng.exponential(size=len(w)) / w)


def calc_odds(weights, rng: np.random.Generator, sims: int = 4000) -> pd.DataFrame:
    """同じ抽選を何千回も試して、単勝・複勝の的中確率とオッズを求める。"""
    w = np.asarray(weights, dtype=float)
    n = len(w)
    keys = rng.exponential(size=(sims, n)) / w
    order = np.argsort(keys, axis=1)
    p_win = np.bincount(order[:, 0], minlength=n) / sims
    p_top3 = np.bincount(order[:, : min(3, n)].ravel(), minlength=n) / sims
    odds_win = np.maximum(MIN_ODDS, np.round(PAYBACK / np.maximum(p_win, 0.004), 1))
    odds_place = np.maximum(MIN_ODDS, np.round(PAYBACK / np.maximum(p_top3, 0.01), 1))
    return pd.DataFrame({"odds_win": odds_win, "odds_place": odds_place})


def finish_times(n: int) -> list[float]:
    """着順ごとのゴール時刻(秒)。1着が11秒、以降0.2秒ずつ遅れる。"""
    return [round(11 + 0.2 * r, 2) for r in range(n)]


def settle(field: pd.DataFrame, bets: pd.DataFrame, ranks: dict[int, int]) -> tuple[list[dict], int]:
    """払い戻しを計算する。ranks は {馬番: 着順}。(明細, 払い戻し合計) を返す。"""
    lines, payout = [], 0
    for _, h in field.iterrows():
        b = bets[bets["no"] == h["no"]].iloc[0]
        rank = ranks[int(h["no"])]
        for kind, amount, odds, hit in (
            ("単勝", int(b["win"]), float(h["odds_win"]), rank == 1),
            ("複勝", int(b["place"]), float(h["odds_place"]), rank <= 3),
        ):
            if amount <= 0:
                continue
            got = int(amount * odds) if hit else 0
            payout += got
            lines.append({"馬番": int(h["no"]), "馬名": h["name"], "種類": kind, "ベット": amount,
                          "結果": "的中" if hit else "ハズレ", "払い戻し": got})
    return lines, payout
