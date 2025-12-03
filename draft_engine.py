# draft_engine.py
# ---------------------------
# Core draft logic for your mock draft app.

from dataclasses import dataclass, field
from typing import List, Optional
import pandas as pd


@dataclass
class Player:
    """Represents a single player in the draft pool."""
    name: str
    position: str   # "QB", "RB", "WR", "TE", etc.
    team: str       # NFL team abbreviation
    adp: float      # lower = earlier pick


@dataclass
class Team:
    """Represents a team (bot or human) in the draft."""
    name: str
    picks: List[Player] = field(default_factory=list)

    def add_player(self, player: Player) -> None:
        self.picks.append(player)


class Draft:
    """
    Core draft model (no UI).

    Expects a DataFrame with columns:
      - 'ADP'
      - 'Position' (like 'WR-01' -> we keep 'WR')
      - 'Player'
      - 'Team'
    """

    def __init__(
        self,
        players_df: pd.DataFrame,
        num_teams: int = 12,
        num_rounds: int = 15,
        user_team_index: int = 0,  # 0-based slot of the human drafter
    ):
        self.num_teams = num_teams
        self.num_rounds = num_rounds
        self.user_team_index = user_team_index
        self.teams: List[Team] = [Team(name=f"Team {i+1}") for i in range(num_teams)]

       df = players_df.copy()

# Optional: mark rookies if a 'Rookie' column exists (1 = rookie, 0 = not)
if "Rookie" in df.columns:
    # store a set of player names who are rookies
    self.rookie_names = set(
        df.loc[df["Rookie"] == 1, "Player"].astype(str)
    )
else:
    self.rookie_names = set()

# "WR-01" -> "WR"
df["pos_group"] = df["Position"].astype(str).str.split("-").str[0]

# Sort by ADP ascending (1 is earliest)
df = df.sort_values("ADP", ascending=True)


        # Build the player pool
        self.player_pool: List[Player] = [
            Player(
                name=row["Player"],
                position=row["pos_group"],
                team=row["Team"],
                adp=row["ADP"],
            )
            for _, row in df.iterrows()
        ]

        self.current_round = 1
        self.current_pick_in_round = 1  # 1..num_teams

    # ---------- basic mechanics ----------

    def _get_pick_order(self, rnd: int) -> List[int]:
        """Snake draft: odd rounds 0..N-1, even rounds reversed."""
        order = list(range(self.num_teams))
        if rnd % 2 == 0:
            order.reverse()
        return order

    def get_current_team_index(self) -> int:
        order = self._get_pick_order(self.current_round)
        return order[self.current_pick_in_round - 1]

    def _advance_pick(self) -> None:
        if self.current_pick_in_round < self.num_teams:
            self.current_pick_in_round += 1
        else:
            self.current_pick_in_round = 1
            self.current_round += 1

    def is_finished(self) -> bool:
        return self.current_round > self.num_rounds

    # ---------- picking ----------

    def _pop_best_available(self) -> Optional[Player]:
        if not self.player_pool:
            return None
        return self.player_pool.pop(0)
        
    def _score_player_for_prefs(self, player: Player,
                            rb_pref: int, qb_pref: int, rookie_pref: int) -> float:
    """
    Compute a score for a player given bot preferences.
    Higher score = more attractive to the bot.

    - Base: prefer lower ADP (earlier ranked players)
    - Add bonus if RB / QB based on sliders
    - Add bonus if rookie based on slider
    - Multiply by a small random factor to introduce draft variability
    """
    # Base: lower ADP -> higher score, so we take negative
    score = -player.adp

    # Position bonuses
    if player.position == "RB":
        score += rb_pref
    if player.position == "QB":
        score += qb_pref

    # Rookie bonus (if we know who rookies are)
    is_rookie = player.name in getattr(self, "rookie_names", set())
    if is_rookie:
        score += rookie_pref

    # Controlled randomness: 0.8–1.2 multiplier
    randomness_factor = random.uniform(0.8, 1.2)
    score *= randomness_factor

    return score


    
    def make_bot_pick(self) -> Optional[Player]:
        """
        Basic bot: always takes best ADP.
        We'll later factor in RB/QB/rookie sliders here.
        """
        player = self._pop_best_available()
        team_idx = self.get_current_team_index()
        if player is not None:
            self.teams[team_idx].add_player(player)
        self._advance_pick()
        return player

    def make_user_pick(self, player_name: str) -> Optional[Player]:
        """User picks by player name from remaining pool."""
        team_idx = self.get_current_team_index()
        if team_idx != self.user_team_index:
            raise ValueError("It's not the user's turn!")

        for i, p in enumerate(self.player_pool):
            if p.name == player_name:
                player = self.player_pool.pop(i)
                self.teams[team_idx].add_player(player)
                self._advance_pick()
                return player

        return None  # not found

    def get_available_players(self) -> List[Player]:
        """Return the current remaining player pool."""
        return self.player_pool

    # ---------- reporting ----------

    def summary_df(self) -> pd.DataFrame:
        """Return a DataFrame of all picks in draft order."""
        rows = []
        for rnd in range(1, self.num_rounds + 1):
            order = self._get_pick_order(rnd)
            for pick_num_in_round, team_idx in enumerate(order, start=1):
                overall_pick = (rnd - 1) * self.num_teams + pick_num_in_round
                team = self.teams[team_idx]
                if len(team.picks) >= rnd:
                    p = team.picks[rnd - 1]
                    rows.append(
                        {
                            "overall_pick": overall_pick,
                            "round": rnd,
                            "pick_in_round": pick_num_in_round,
                            "team": team.name,
                            "player": p.name,
                            "position": p.position,
                            "nfl_team": p.team,
                            "adp": p.adp,
                        }
                    )
        return pd.DataFrame(rows)

