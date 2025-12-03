# app.py
# ---------------------------
# Streamlit UI for the mock draft simulator.

import streamlit as st
import pandas as pd
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

st.sidebar.caption("ADP source: ADP_Table.csv")

# (we'll add bot preference sliders in a later step)


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

# Allow user to restart with new settings
if st.sidebar.button("Restart draft"):
    st.session_state.draft = Draft(
        players_df=players_df,
        num_teams=num_teams,
        num_rounds=num_rounds,
        user_team_index=user_team_index,
    )
    st.session_state.recent_picks = []
    draft = st.session_state.draft

# ---------- main draft area ----------

if draft.is_finished():
    st.success("Draft complete!")
    st.subheader("Final Draft Board")
    st.dataframe(draft.summary_df().sort_values("overall_pick"))
    st.stop()

current_team_idx = draft.get_current_team_index()
current_overall = (draft.current_round - 1) * draft.num_teams + draft.current_pick_in_round

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

# ----- User or bot action -----

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
    st.markdown(f"## Team {current_team_idx + 1} (bot) is picking")

    if st.button("Advance bot pick"):
        drafted = draft.make_bot_pick()
        if drafted is None:
            st.warning("No players left to draft.")
        else:
            text = (
                f"Pick #{current_overall}: Team {current_team_idx + 1} drafted "
                f"{drafted.name} ({drafted.position} - {drafted.team}, ADP {int(drafted.adp)})"
            )
            st.session_state.recent_picks.append(text)
            st.info(text)

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
