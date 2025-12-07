# app.py
# ---------------------------
# Streamlit UI for the mock draft simulator.

import time
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import streamlit as st

from draft_engine import Draft

st.set_page_config(page_title="Fantasy Football Mock Draft Simulator", layout="wide")

st.title("Fantasy Football Mock Draft Simulator")

# ---------- load ADP table ----------


@st.cache_data
def load_adp_table(path: str = "ADP_Table.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    expected = {"ADP", "Position", "Player", "Team"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"ADP_Table.csv missing columns: {missing}")
    return df


players_df = load_adp_table()

# ---------- draft board visual ----------


def render_draft_board(draft: Draft):
    """
    Sleeper-style draft board:
      - Teams as columns (with bot personality under name)
      - Rounds as rows
      - Each tile: player, position, NFL team, and round.pick (e.g. 3.04)
      - Red background, gray cards, position-colored text
    """
    teams = draft.teams
    num_teams = draft.num_teams
    num_rounds = draft.num_rounds

    # Bot profiles for labeling personalities
    if "bot_profiles" in st.session_state:
        bot_profiles = st.session_state.bot_profiles
    else:
        bot_profiles = [None] * num_teams

    # Position text colors
    pos_colors = {
        "QB": "#ffb347",  # orange-ish
        "RB": "#77dd77",  # green
        "WR": "#aec6cf",  # blue-ish
        "TE": "#cba4ff",  # purple
        "DEF": "#ff6961",  # red-ish
        "K": "#fdfd96",  # yellow
    }
    default_color = "#ffffff"

    board_html = f"""
<style>
.draft-board-wrapper {{
  background-color: #8b0000; /* dark red board background */
  padding: 12px;
  border-radius: 8px;
  margin-top: 8px;
}}
.draft-board {{
  display: grid;
  grid-template-columns: 120px repeat({num_teams}, 1fr);
  gap: 6px;
}}
.draft-board-header {{
  font-weight: 700;
  text-align: center;
  color: #ffffff;
  font-size: 0.85rem;
}}
.draft-board-bot-label {{
  display: block;
  font-weight: 400;
  font-size: 0.70rem;
  color: #dddddd;
  margin-top: 2px;
}}
.draft-board-round-label {{
  font-weight: 600;
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.85rem;
}}
.draft-card {{
  background-color: #333333; /* gray cards */
  border-radius: 6px;
  padding: 4px;
  min-height: 42px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}}
.draft-card-empty {{
  opacity: 0.15;
}}
.draft-card-player {{
  font-size: 0.80rem;
  font-weight: 600;
}}
.draft-card-meta {{
  font-size: 0.70rem;
}}
</style>
<div class="draft-board-wrapper">
  <div class="draft-board">
    <div></div>
"""

    # ----- Header row: team names + personalities -----
    for idx, team in enumerate(teams):
        if idx == draft.user_team_index:
            top_label = "You"
            sub_label = "(manual)"
        else:
            prof = bot_profiles[idx]
            if prof is not None:
                top_label = f"Team {idx+1}"
                sub_label = prof.name
            else:
                top_label = f"Team {idx+1}"
                sub_label = "General bot"

        board_html += (
            '<div class="draft-board-header">'
            f"{top_label}"
            f'<span class="draft-board-bot-label">{sub_label}</span>'
            "</div>"
        )

    # ----- Rows: rounds -----
    for rnd in range(1, num_rounds + 1):
        board_html += f'<div class="draft-board-round-label">Round {rnd}</div>'

        order = draft._get_pick_order(rnd)  # snake order for this round

        for team_idx, team in enumerate(teams):
            if len(team.picks) >= rnd:
                p = team.picks[rnd - 1]

                pick_in_round = order.index(team_idx) + 1  # 1-based
                pick_label = f"{rnd}.{pick_in_round:02d}"

                pos_color = pos_colors.get(p.position, default_color)
                player_name = p.name
                pos = p.position
                nfl_team = p.team
                try:
                    adp_int = int(p.adp)
                except Exception:
                    adp_int = p.adp

                board_html += f"""
<div class="draft-card">
  <div class="draft-card-player" style="color:{pos_color};">
    {player_name} ({pos})
  </div>
  <div class="draft-card-meta">
    {nfl_team} • Pick {pick_label} • ADP {adp_int}
  </div>
</div>
"""
            else:
                board_html += """
<div class="draft-card draft-card-empty">
</div>
"""

    board_html += """
  </div>
</div>
"""

    st.markdown(board_html, unsafe_allow_html=True)


# ---------- Bot profile definitions (for advanced mode) ----------


@dataclass
class BotProfile:
    name: str
    qb_pref: int            # -5..+5
    rb_pref: int            # -5..+5
    rookie_pref: int        # -5..+5
    team_pref: int          # -5..+5
    stack_weight: float     # how much this bot cares about stacking
    randomness_factor: float = 1.0  # >1 = more chaotic, <1 = more disciplined
    fav_team: Optional[str] = None  # set per-bot in UI if applicable


BOT_PRESETS = {
    "Balanced": BotProfile(
        name="Balanced",
        rb_pref=0,
        qb_pref=0,
        rookie_pref=0,
        team_pref=0,
        stack_weight=1.5,
        randomness_factor=1.0,
    ),
    "Team Super Fan": BotProfile(
        name="Team Super Fan",
        rb_pref=0,
        qb_pref=0,
        rookie_pref=0,
        team_pref=5,
        stack_weight=2.0,
        randomness_factor=1.0,
    ),
    "RB Enthusiast": BotProfile(
        name="RB Enthusiast",
        rb_pref=4,
        qb_pref=-2,
        rookie_pref=0,
        team_pref=0,
        stack_weight=1.2,
        randomness_factor=1.0,
    ),
    "Elite Onesie Drafter": BotProfile(
        name="Elite Onesie Drafter",
        rb_pref=1,
        qb_pref=2,
        rookie_pref=0,
        team_pref=0,
        stack_weight=1.5,
        randomness_factor=0.9,
    ),
    "Upside Drafter": BotProfile(
        name="Upside Drafter",
        rb_pref=0,
        qb_pref=0,
        rookie_pref=5,
        team_pref=0,
        stack_weight=2.0,
        randomness_factor=1.2,
    ),
    "Chaos Bot": BotProfile(
        name="Chaos Bot",
        rb_pref=0,
        qb_pref=0,
        rookie_pref=2,
        team_pref=0,
        stack_weight=1.5,
        randomness_factor=2.5,
    ),
}

# ---------- sidebar: draft settings ----------

st.sidebar.header("Draft Settings")
num_teams = st.sidebar.slider("Number of teams", 4, 14, 12)
num_rounds = st.sidebar.slider("Number of rounds", 5, 20, 15)
user_slot = st.sidebar.number_input(
    "Your draft slot (1 = first pick)",
    min_value=1,
    max_value=num_teams,
    value=6,
)
user_team_index = user_slot - 1

st.sidebar.caption("Adjust settings, then start the draft.")

# ---------- bot configuration mode ----------

st.sidebar.subheader("Bot Configuration Mode")
bot_mode = st.sidebar.radio(
    "How should bots be configured?",
    ["General (global sliders)", "Advanced (per-team bots)"],
    index=0,
    key="bot_mode",
)

# Defaults for general mode
fav_team: Optional[str] = None
team_pref = 0
rb_pref = 0
qb_pref = 0
rookie_pref = 0

# ensure bot_profiles list exists and matches num_teams
if "bot_profiles" not in st.session_state or len(st.session_state.bot_profiles) != num_teams:
    st.session_state.bot_profiles = [None] * num_teams

if bot_mode.startswith("General"):
    st.sidebar.subheader("Bot Preferences (Global)")

    qb_pref = st.sidebar.slider(
        "QB preference (-5 to +5)",
        min_value=-5,
        max_value=5,
        value=0,
        help="Negative = bots avoid QBs; positive = bots favor QBs.",
    )

    rb_pref = st.sidebar.slider(
        "RB preference (-5 to +5)",
        min_value=-5,
        max_value=5,
        value=0,
        help="Negative = bots avoid RBs; positive = bots favor RBs.",
    )

    rookie_pref = st.sidebar.slider(
        "Rookie preference (-5 to +5)",
        min_value=-5,
        max_value=5,
        value=0,
        help="Negative = avoid rookies; positive = prefer rookies.",
    )

    # global team preference
    st.sidebar.subheader("Team Preference (Global)")

    if "use_team_pref" not in st.session_state:
        st.session_state.use_team_pref = False

    if st.sidebar.button("Add team preference"):
        st.session_state.use_team_pref = True

    if st.session_state.use_team_pref:
        team_options = sorted(players_df["Team"].unique())
        fav_team_choice = st.sidebar.selectbox(
            "Team for bots to favor",
            ["None"] + team_options,
        )
        team_pref = st.sidebar.slider(
            "Team preference (-5 to +5)",
            min_value=-5,
            max_value=5,
            value=3,
            help="Negative = bots avoid this team; positive = bots favor this team.",
        )
        if fav_team_choice != "None":
            fav_team = fav_team_choice

    # in general mode we don't use per-team profiles for logic,
    # so mark them None
    for i in range(num_teams):
        st.session_state.bot_profiles[i] = None

else:
    # ---------- advanced mode: per-team bot profiles ----------
    st.sidebar.subheader("Per-Team Bot Profiles")

    preset_names = list(BOT_PRESETS.keys())
    team_codes = sorted(players_df["Team"].unique())

    for idx in range(num_teams):
        if idx == user_team_index:
            st.sidebar.markdown(f"**Team {idx + 1}: You (manual drafter)**")
            st.session_state.bot_profiles[idx] = None
            continue

        st.sidebar.markdown(f"**Team {idx + 1} Bot**")
        preset_name = st.sidebar.selectbox(
            f"Profile for Team {idx + 1}",
            preset_names,
            key=f"bot_profile_{idx}",
        )

        base_profile = BOT_PRESETS[preset_name]
        profile = BotProfile(
            name=base_profile.name,
            rb_pref=base_profile.rb_pref,
            qb_pref=base_profile.qb_pref,
            rookie_pref=base_profile.rookie_pref,
            team_pref=base_profile.team_pref,
            stack_weight=base_profile.stack_weight,
            randomness_factor=base_profile.randomness_factor,
            fav_team=base_profile.fav_team,
        )

        if preset_name == "Team Super Fan":
            fav = st.sidebar.selectbox(
                f"Favorite NFL team (Team {idx + 1})",
                ["None"] + team_codes,
                key=f"fav_team_{idx}",
            )
            if fav != "None":
                profile.fav_team = fav

        st.session_state.bot_profiles[idx] = profile

# ---------- session state: draft + flags ----------

if "draft" not in st.session_state:
    st.session_state.draft = Draft(
        players_df=players_df,
        num_teams=num_teams,
        num_rounds=num_rounds,
        user_team_index=user_team_index,
    )
    st.session_state.recent_picks = []

draft: Draft = st.session_state.draft

if "draft_started" not in st.session_state:
    st.session_state.draft_started = False

# restart button
if st.sidebar.button("Restart draft"):
    st.session_state.draft = Draft(
        players_df=players_df,
        num_teams=num_teams,
        num_rounds=num_rounds,
        user_team_index=user_team_index,
    )
    st.session_state.recent_picks = []
    st.session_state.draft_started = False
    st.session_state.use_team_pref = False
    st.session_state.bot_profiles = [None] * num_teams
    draft = st.session_state.draft

# ---------- main draft area ----------

if not st.session_state.draft_started:
    st.header("Set up your mock draft")

    st.markdown(
        f"**Number of teams:** {num_teams}  \n"
        f"**Number of rounds:** {num_rounds}  \n"
        f"**Your draft slot:** {user_slot}"
    )
    st.markdown(
        "Adjust the settings in the sidebar, then click **Start Draft** when you're ready."
    )

    if st.button("Start Draft"):
        st.session_state.draft_started = True
    else:
        st.stop()

# ---------- after start: live pick + board ----------

live_pick_box = st.empty()
board_container = st.empty()

# auto-advance bots to your pick
while (
    not draft.is_finished()
    and draft.get_current_team_index() != draft.user_team_index
):
    current_overall = (
        (draft.current_round - 1) * draft.num_teams
        + draft.current_pick_in_round
    )
    bot_team_idx = draft.get_current_team_index()

    if bot_mode.startswith("Advanced") and st.session_state.bot_profiles[bot_team_idx] is not None:
        cfg = st.session_state.bot_profiles[bot_team_idx]
        drafted = draft.make_bot_pick_with_prefs(
            rb_pref=cfg.rb_pref,
            qb_pref=cfg.qb_pref,
            rookie_pref=cfg.rookie_pref,
            fav_team=cfg.fav_team,
            team_pref=cfg.team_pref,
            stack_weight=cfg.stack_weight,
            randomness_factor=cfg.randomness_factor,
        )
    else:
        drafted = draft.make_bot_pick_with_prefs(
            rb_pref=rb_pref,
            qb_pref=qb_pref,
            rookie_pref=rookie_pref,
            fav_team=fav_team,
            team_pref=team_pref,
            stack_weight=1.5,
            randomness_factor=1.0,
        )

    if drafted is None:
        break

    text = (
        f"Pick #{current_overall}: Team {bot_team_idx + 1} drafted "
        f"{drafted.name} ({drafted.position} - {drafted.team}, ADP {int(drafted.adp)})"
    )
    st.session_state.recent_picks.append(text)

    with board_container:
        render_draft_board(draft)

    live_pick_box.info(text)
    time.sleep(0.4)

# ensure board rendered at least once
with board_container:
    render_draft_board(draft)

# finished?
if draft.is_finished():
    st.success("Draft complete!")
    st.subheader("Final Draft Board")
    render_draft_board(draft)
    st.stop()

# your pick
current_team_idx = draft.get_current_team_index()
current_overall = (
    (draft.current_round - 1) * draft.num_teams
    + draft.current_pick_in_round
)
user_on_clock = current_team_idx == draft.user_team_index

st.markdown(
    f"### Draft Status  \n"
    f"**Round:** {draft.current_round} &nbsp;&nbsp;|&nbsp;&nbsp; "
    f"**Pick in round:** {draft.current_pick_in_round} of {draft.num_teams} &nbsp;&nbsp;|&nbsp;&nbsp; "
    f"**Overall pick:** #{current_overall} &nbsp;&nbsp;|&nbsp;&nbsp; "
    f"**Your slot:** {user_slot}"
)

if user_on_clock:
    st.success("🧠 Your pick is **on the clock!**")

    available = draft.get_available_players()
    
    # make filter more user-friendly
    POSITION_ORDER = ["QB", "RB", "WR", "TE", "DEF", "K"]
    raw_positions = {p.position for p in available}
    pos_options = [pos for pos in POSITION_ORDER if pos in raw_positions]
    pos_choice = st.selectbox("Filter by position", ["All"] + pos_options)

    if pos_choice != "All":
        filtered = [p for p in available if p.position == pos_choice]
    else:
        filtered = available

    top_n = 60
    filtered = filtered[:top_n]

    if not filtered:
        st.warning("No players left for this filter.")
    else:
        option_labels = [
            f"{p.name} ({p.position} - {p.team}, ADP {int(p.adp)})"
            for p in filtered
        ]
        choice = st.selectbox("Select your player:", option_labels)

        if st.button("Draft Player"):
            name = choice.split(" (")[0]
            drafted = draft.make_user_pick(name)
            if drafted is None:
                st.error("Player not found or already drafted.")
            else:
                text = (
                    f"Pick #{current_overall}: Team {draft.user_team_index + 1} drafted "
                    f"{drafted.name} ({drafted.position} - {drafted.team}, ADP {int(drafted.adp)})"
                )
                st.session_state.recent_picks.append(text)
                st.rerun()
else:
    # Normally we shouldn't land here because bots auto-advance
    st.info("Advancing bots to your next pick...")
