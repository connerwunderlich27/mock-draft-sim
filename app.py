# app.py
# ---------------------------
# Streamlit UI for the mock draft simulator.

import streamlit as st
import pandas as pd
from draft_engine import Draft
from dataclasses import dataclass
from typing import Optional
import time  # for simple pick animation

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

# ---------- Bot profile definitions (for advanced mode) ----------

@dataclass
class BotProfile:
    name: str
    rb_pref: int            # -5..+5
    qb_pref: int            # -5..+5
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
        team_pref=5,         # big preference for one team
        stack_weight=2.0,    # likes stacking with that team
        randomness_factor=1.0,
        # fav_team will be chosen in the UI
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
        qb_pref=2,           # a bit more QB-friendly
        rookie_pref=0,
        team_pref=0,
        stack_weight=1.5,
        randomness_factor=0.9,  # slightly more disciplined
    ),
    "Upside Drafter": BotProfile(
        name="Upside Drafter",
        rb_pref=0,
        qb_pref=0,
        rookie_pref=5,       # loves rookies
        team_pref=0,
        stack_weight=2.0,
        randomness_factor=1.2,
    ),
    "Chaos Bot": BotProfile(
        name="Chaos Bot",
        rb_pref=0,
        qb_pref=0,
        rookie_pref=2,       # mild rookie lean
        team_pref=0,
        stack_weight=1.5,    # normal stacking
        randomness_factor=2.5,  # BIG variance: reaches and weird picks
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

# ---------- bot configuration mode + preferences ----------

st.sidebar.subheader("Bot Configuration Mode")
bot_mode = st.sidebar.radio(
    "How should bots be configured?",
    ["General (global sliders)", "Advanced (per-team bots)"],
    index=0,
    key="bot_mode",
)

# Defaults used in general mode (and as fallback)
fav_team = None
team_pref = 0
rb_pref = 0
qb_pref = 0
rookie_pref = 0

# Ensure we always have a bot_profiles list matching num_teams
if "bot_profiles" not in st.session_state or len(st.session_state.bot_profiles) != num_teams:
    st.session_state.bot_profiles = [None] * num_teams  # index = team_idx


if bot_mode.startswith("General"):
    # ---------- general mode: global sliders for all bots ----------

    st.sidebar.subheader("Bot Preferences (Global)")

    rb_pref = st.sidebar.slider(
        "RB preference (-5 to +5)",
        min_value=-5,
        max_value=5,
        value=0,
        help="Negative = bots avoid RBs; positive = bots favor RBs."
    )

    qb_pref = st.sidebar.slider(
        "QB preference (-5 to +5)",
        min_value=-5,
        max_value=5,
        value=0,
        help="Negative = bots avoid QBs; positive = bots favor QBs."
    )

    rookie_pref = st.sidebar.slider(
        "Rookie preference (-5 to +5)",
        min_value=-5,
        max_value=5,
        value=0,
        help="Negative = avoid rookies; positive = prefer rookies."
    )

    # ---------- team preference toggle (global) ----------

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
            help="Negative = bots avoid this team; positive = bots favor this team."
        )

        if fav_team_choice != "None":
            fav_team = fav_team_choice

    # In general mode, we don't use per-team profiles for logic yet,
    # but they will be shown as "General bot" in the UI.
    for i in range(num_teams):
        st.session_state.bot_profiles[i] = None

else:
    # ---------- advanced mode: per-team bot profiles ----------

    st.sidebar.subheader("Per-Team Bot Profiles")

    preset_names = list(BOT_PRESETS.keys())
    team_codes = sorted(players_df["Team"].unique())

    for idx in range(num_teams):
        if idx == user_team_index:
            st.sidebar.markdown(f"**Team {idx+1}: You (manual drafter)**")
            st.session_state.bot_profiles[idx] = None
            continue

        st.sidebar.markdown(f"**Team {idx+1} Bot**")

        preset_name = st.sidebar.selectbox(
            f"Profile for Team {idx+1}",
            preset_names,
            key=f"bot_profile_{idx}",
        )

        base_profile = BOT_PRESETS[preset_name]

        # Create a copy so we can customize per-team
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

        # If this bot is a Team Super Fan, let the user pick a favorite team
        if preset_name == "Team Super Fan":
            fav = st.sidebar.selectbox(
                f"Favorite NFL team (Team {idx+1})",
                ["None"] + team_codes,
                key=f"fav_team_{idx}",
            )
            if fav != "None":
                profile.fav_team = fav

        st.session_state.bot_profiles[idx] = profile

# ---------- session state: draft + recent picks ----------

if "draft" not in st.session_state:
    st.session_state.draft = Draft(
        players_df=players_df,
        num_teams=num_teams,
        num_rounds=num_rounds,
        user_team_index=user_team_index,
    )
    st.session_state.recent_picks = []

draft: Draft = st.session_state.draft

# Track whether the draft has actually started yet
if "draft_started" not in st.session_state:
    st.session_state.draft_started = False

# Allow user to restart with new settings
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

# If the draft hasn't started yet, show a setup screen and wait
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

    clicked = st.button("Start Draft")

    if clicked:
        # Mark as started and immediately continue into the draft
        st.session_state.draft_started = True
    else:
        # Still not started: stop here, don't run picks yet
        st.stop()

# ---------- main draft area (after start) ----------

# Box to show the most recent pick as it happens
live_pick_box = st.empty()

# Auto-advance bots until it's the user's turn or the draft ends
while (
    not draft.is_finished()
    and draft.get_current_team_index() != draft.user_team_index
):
    current_overall = (draft.current_round - 1) * draft.num_teams + draft.current_pick_in_round
    bot_team_idx = draft.get_current_team_index()

    # Decide which bot config to use for this team
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
        # General mode (or no profile available): use global sliders
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


    # Show this pick in a live "animation" box and pause briefly
    live_pick_box.info(text)
    time.sleep(0.4)  # tweak this delay for faster/slower animation

# If the draft finished during auto-advance, show final results
if draft.is_finished():
    st.success("Draft complete!")
    st.subheader("Final Draft Board")
    st.dataframe(draft.summary_df().sort_values("overall_pick"))
    st.stop()

# At this point, either it's your turn or the draft is over
current_team_idx = draft.get_current_team_index()
current_overall = (
    (draft.current_round - 1) * draft.num_teams
    + draft.current_pick_in_round
)

st.subheader(
    f"Round {draft.current_round} - Pick {draft.current_pick_in_round} of {draft.num_teams} "
    f"(Overall Pick #{current_overall})"
)

# ----- Recent picks section -----

st.markdown("### Recent Bot Picks")
if st.session_state.recent_picks:
    # show last 5, newest on top
    for text in st.session_state.recent_picks[-5:][::-1]:
        st.info(text)
else:
    st.caption("No picks yet.")

user_on_clock = current_team_idx == draft.user_team_index

# ----- User action (should always be your pick here) -----

if user_on_clock:
    st.markdown("## Your pick is on the clock!")

    # position filter options from current pool
    available = draft.get_available_players()
    pos_options = sorted({p.position for p in available})
    pos_choice = st.selectbox("Filter by position", ["All"] + pos_options)

    if pos_choice != "All":
        filtered = [p for p in available if p.position == pos_choice]
    else:
        filtered = available

    # limit dropdown length
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
                # Log your pick
                text = (
                    f"Pick #{current_overall}: Team {draft.user_team_index + 1} drafted "
                    f"{drafted.name} ({drafted.position} - {drafted.team}, ADP {int(drafted.adp)})"
                )
                st.session_state.recent_picks.append(text)

                # Force a rerun so bots immediately pick and UI updates
                st.rerun()

# ---------- Teams & Bot Profiles Overview ----------

st.markdown("### Teams & Bots")

for idx, team in enumerate(draft.teams):
    if idx == draft.user_team_index:
        st.write(f"Team {idx+1}: **You (manual)**")
    else:
        if bot_mode.startswith("Advanced") and st.session_state.bot_profiles[idx] is not None:
            st.write(f"Team {idx+1}: {st.session_state.bot_profiles[idx].name}")
        else:
            st.write(f"Team {idx+1}: General bot")

# ---------- Your roster + draft summary ----------

col1, col2 = st.columns(2)

with col1:
    st.markdown("### Your Roster")
    user_team = draft.teams[draft.user_team_index]
    if user_team.picks:
        roster_df = pd.DataFrame(
            {
                "player": [p.name for p in user_team.picks],
                "position": [p.position for p in user_team.picks],
                "team": [p.team for p in user_team.picks],
                "adp": [p.adp for p in user_team.picks],
            }
        )
        st.table(roster_df)
    else:
        st.caption("You haven't drafted anyone yet.")

with col2:
    st.markdown("### Draft Summary (so far)")
    summary = draft.summary_df()
    if not summary.empty:
        st.dataframe(summary.sort_values("overall_pick"))
    else:
        st.caption("No picks recorded yet.")

