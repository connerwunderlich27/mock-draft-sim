# app.py
# ---------------------------
# Streamlit UI for the mock draft simulator.

import streamlit as st
import pandas as pd
from draft_engine import Draft
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

# ---------- bot preference sliders ----------

st.sidebar.subheader("Bot Preferences")

rb_pref = st.sidebar.slider(
    "RB preference",
    min_value=0,
    max_value=10,
    value=5,
    help="Higher = bots more likely to take RBs when choosing between similar players.",
)

qb_pref = st.sidebar.slider(
    "QB preference",
    min_value=0,
    max_value=10,
    value=3,
    help="Higher = bots more likely to take QBs.",
)

rookie_pref = st.sidebar.slider(
    "Rookie preference",
    min_value=0,
    max_value=10,
    value=4,
    help="Higher = bots more likely to take rookies (based on Rookie column).",
)

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

# Auto-advance bots until it's the user's turn or the draft ends
live_pick_box = st.empty()  # placeholder for simple "current pick" animation

while (
    not draft.is_finished()
    and draft.get_current_team_index() != draft.user_team_index
):
    # Compute overall pick BEFORE advancing (this is the pick they're about to make)
    current_overall = (
        (draft.current_round - 1) * draft.num_teams
        + draft.current_pick_in_round
    )
    bot_team_idx = draft.get_current_team_index()

    drafted = draft.make_bot_pick_with_prefs(
        rb_pref=rb_pref,
        qb_pref=qb_pref,
        rookie_pref=rookie_pref,
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
                st.success(
                    f"You drafted {drafted.name} "
                    f"({drafted.position} - {drafted.team}, ADP {int(drafted.adp)})"
                )
else:
    # This should basically never happen, but it's a safety net
    st.markdown("## Bots are drafting…")
    st.info("Bots have been auto-advanced to your next pick. Try rerunning the app if this persists.")

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

