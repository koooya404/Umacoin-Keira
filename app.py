"""馬コイン競馬 - Streamlit 版

起動: streamlit run app.py
"""
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import game
from render import build_race_html, frame_height

st.set_page_config(page_title="馬コイン競馬", page_icon="🏇", layout="centered")


# ---------- 馬データ ----------
@st.cache_data(ttl=300, show_spinner="馬のデータを読み込み中…")
def cached_horses(source: str):
    return game.load_horses(source)


def default_source() -> str:
    try:
        return str(st.secrets.get("SHEET_URL", ""))
    except Exception:  # secrets.toml が無い場合
        return ""


# ---------- 状態 ----------
def ss_init():
    ss = st.session_state
    ss.setdefault("coins", game.START_COINS)
    ss.setdefault("race_no", 0)
    ss.setdefault("phase", "bet")  # bet → race → result
    ss.setdefault("rng", np.random.default_rng())


def new_race(horses: pd.DataFrame):
    ss = st.session_state
    rng = ss["rng"]
    field = game.make_field(horses, rng)
    field = pd.concat([field, game.calc_odds(field["weight"], rng)], axis=1)
    ss["field"] = field
    ss["race_no"] += 1
    ss["phase"] = "bet"
    ss.pop("race", None)


ss_init()
ss = st.session_state

with st.sidebar:
    st.header("馬のデータ")
    source = st.text_input(
        "スプレッドシートのURL",
        value=default_source(),
        placeholder="空欄なら同梱の data/horses.csv を使います",
        help="リンクを知っている全員が閲覧できる設定にしてください。A列=馬の名前、C列=脚質、D列=勝率。",
    )
    if st.button("読み込み直す"):
        cached_horses.clear()
        ss.pop("field", None)
        ss["phase"] = "bet"
        st.rerun()
    if st.button("所持金を1000に戻す"):
        ss["coins"] = game.START_COINS
        ss["phase"] = "bet"
        ss.pop("field", None)
        st.rerun()

horses, note = cached_horses(source)
if len(horses) < 2:
    st.error("馬のデータが足りません。")
    st.stop()
if "field" not in ss:
    new_race(horses)
with st.sidebar:
    st.caption(note)
    st.caption(f"登録 {len(horses)} 頭から毎回 {min(game.FIELD_SIZE, len(horses))} 頭が出走します。")

field: pd.DataFrame = ss["field"]
n = len(field)

# ---------- 画面 ----------
st.title("馬コイン競馬")
st.caption("実際のお金は使いません。賭けるのは馬コインだけです。")
c1, c2 = st.columns(2)
c1.metric("所持金", f"{ss['coins']:,} 馬コイン")
c2.metric("レース", f"第{ss['race_no']}レース")

# ===== ベット =====
if ss["phase"] == "bet":
    if ss["coins"] <= 0:
        st.warning("馬コインがなくなりました。")
        if st.button("1000馬コインで出直す", type="primary"):
            ss["coins"] = game.START_COINS
            new_race(horses)
            st.rerun()
        st.stop()

    st.subheader("出走表とベット")
    st.caption("単勝は1着、複勝は3着以内で払い戻し。金額は馬コイン(100単位で増減)。")
    table = pd.DataFrame({
        "馬番": field["no"],
        "馬名": field["name"],
        "脚質": field["style"],
        "単勝倍率": field["odds_win"],
        "複勝倍率": field["odds_place"],
        "単勝ベット": 0,
        "複勝ベット": 0,
    })
    edited = st.data_editor(
        table,
        key=f"bets_{ss['race_no']}",
        hide_index=True,
        disabled=["馬番", "馬名", "脚質", "単勝倍率", "複勝倍率"],
        column_config={
            "馬番": st.column_config.NumberColumn(format="%d", width="small"),
            "単勝倍率": st.column_config.NumberColumn(format="%.1f 倍"),
            "複勝倍率": st.column_config.NumberColumn(format="%.1f 倍"),
            "単勝ベット": st.column_config.NumberColumn(min_value=0, max_value=int(ss["coins"]), step=100, format="%d"),
            "複勝ベット": st.column_config.NumberColumn(min_value=0, max_value=int(ss["coins"]), step=100, format="%d"),
        },
    )
    bets = pd.DataFrame({
        "no": edited["馬番"],
        "win": pd.to_numeric(edited["単勝ベット"], errors="coerce").fillna(0).astype(int).clip(lower=0),
        "place": pd.to_numeric(edited["複勝ベット"], errors="coerce").fillna(0).astype(int).clip(lower=0),
    })
    total = int((bets["win"] + bets["place"]).sum())
    over = total > ss["coins"]
    st.write(f"ベット合計 **{total:,}** / 所持金 {ss['coins']:,} → 残り **{ss['coins'] - total:,}**")
    if over:
        st.error("ベット合計が所持金を超えています。")
    label = f"{total:,} 馬コインでレース開始" if total else "ベットなしで観戦する"
    if st.button(label, type="primary", disabled=over):
        order = game.finishing_order(field["weight"], ss["rng"])
        ranks = {int(field.loc[pos, "no"]): r + 1 for r, pos in enumerate(order)}
        lines, payout = game.settle(field, bets, ranks)
        ss["coins"] -= total
        ss["race"] = {"order": [int(p) for p in order], "ranks": ranks, "lines": lines,
                      "payout": payout, "total": total}
        ss["phase"] = "race"
        st.rerun()

# ===== レース中 =====
elif ss["phase"] == "race":
    race = ss["race"]
    st.subheader(f"第{ss['race_no']}レース")
    components.html(build_race_html(field, race["order"], f"第{ss['race_no']}レース"),
                    height=frame_height(n))
    st.caption("ゴールしたら結果を見ましょう。(結果を見ると払い戻しが反映されます)")
    if st.button("結果を見る", type="primary"):
        ss["coins"] += race["payout"]
        ss["phase"] = "result"
        st.rerun()

# ===== 結果 =====
else:
    race = ss["race"]
    st.subheader(f"第{ss['race_no']}レース 結果")
    order = race["order"]
    result = pd.DataFrame({
        "着順": [f"{r + 1}着" for r in range(len(order))],
        "馬番": [int(field.loc[p, "no"]) for p in order],
        "馬名": [field.loc[p, "name"] for p in order],
        "脚質": [field.loc[p, "style"] for p in order],
    })
    st.dataframe(result, hide_index=True)
    if race["lines"]:
        st.dataframe(pd.DataFrame(race["lines"]), hide_index=True)
        net = race["payout"] - race["total"]
        (st.success if net >= 0 else st.error)(f"収支 {net:+,} 馬コイン(払い戻し {race['payout']:,} − ベット {race['total']:,})")
    else:
        st.info("ベットなしの観戦でした。")
    label = "1000馬コインで出直す" if ss["coins"] <= 0 else "次のレースへ"
    if st.button(label, type="primary"):
        if ss["coins"] <= 0:
            ss["coins"] = game.START_COINS
        new_race(horses)
        st.rerun()

st.divider()
st.caption("馬のイラストはこのプロジェクト用に描き下ろしたオリジナル(MIT)。")
