# draft_engine.py
# ---------------------------
# Core draft logic for your mock draft app.

from dataclasses import dataclass, field
from typing import List, Optional
import pandas as pd
import random


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
      - optional: 'Rookie' (1 = rookie, 0 = not)
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

    # ---------- basic picking (pure ADP) ----------

    def _pop_best_available(self) -> Optional[Player]:
        if not self.player_pool:
            return None
        return self.player_pool.pop(0)

    def make_bot_pick(self) -> Optional[Player]:
        """
        Basic bot: always takes best ADP.
        (Not used once we use make_bot_pick_with_prefs, but kept as a fallback.)
        """
        player = self._pop_best_available()
        team_idx = self.get_current_team_index()
        if player is not None:
            self.teams[team_idx].add_player(player)
        self._advance_pick()
        return player

    # ---------- preference-based bot picking ----------

    def _score_player_for_prefs(
        self,
        player: Player,
        rb_pref: int,
        qb_pref: int,
        rookie_pref: int,
        fav_team: Optional[str],
        team_pref: int,
        stack_weight: float,
        randomness_factor: float,
        **kwargs,
    ) -> float:
        """
        Compute a score for a player given bot preferences.
        Higher score = more attractive to the bot.

        - Base: prefer lower ADP (earlier ranked players)
        - Add bonus/penalty if RB / QB based on sliders (-5..+5)
        - Add bonus/penalty if rookie based on slider (-5..+5)
        - Add bonus/penalty if on favorite team (-5..+5)
        - Enforce positional value rules for QB/TE and RB/WR balance
        - Add stacking bonus for QB–WR/TE pairs (scaled by stack_weight)
        - Add additive randomness scaled by randomness_factor
        """
        # Base: lower ADP -> higher score, so we take negative
        score = -player.adp

        # ----- current team context (for roster-aware behavior) -----
        team_idx = self.get_current_team_index()
        team = self.teams[team_idx]
        qb_count = sum(1 for p in team.picks if p.position == "QB")
        te_count = sum(1 for p in team.picks if p.position == "TE")
        rb_count = sum(1 for p in team.picks if p.position == "RB")
        wr_count = sum(1 for p in team.picks if p.position == "WR")

        # For stacking: which NFL teams does this roster already have at QB vs WR/TE?
        qb_teams = {p.team for p in team.picks if p.position == "QB"}
        receiver_teams = {p.team for p in team.picks if p.position in ("WR", "TE")}

        # We will use round_index both for "early rounds" logic and noise.
        overall_pick = (self.current_round - 1) * self.num_teams + self.current_pick_in_round
        round_index = (overall_pick - 1) // self.num_teams + 1  # 1-based round

        # ----- position preference sliders -----
        if player.position == "RB":
            score += rb_pref
        if player.position == "QB":
            score += qb_pref
        # TE: no slider yet (you could add one later)

        # ----- rookie preference slider -----
        is_rookie = player.name in self.rookie_names
        if is_rookie:
            score += rookie_pref

        # ----- team preference (favorite NFL team) -----
        if fav_team is not None and player.team == fav_team:
            score += team_pref

        # ----- positional value rules for QB / TE -----
        HARD_CAP = 2
        HUGE_PENALTY = 1e6  # effectively "do not draft"

        if player.position == "QB":
            if qb_count >= HARD_CAP:
                score -= HUGE_PENALTY
            else:
                EARLY_ROUND_LIMIT_QB = 6
                if qb_count >= 1 and round_index <= EARLY_ROUND_LIMIT_QB:
                    # Strong penalty for drafting a 2nd QB early.
                    score -= 8.0

        if player.position == "TE":
            if te_count >= HARD_CAP:
                score -= HUGE_PENALTY
            else:
                EARLY_ROUND_LIMIT_TE = 6
                if te_count >= 1 and round_index <= EARLY_ROUND_LIMIT_TE:
                    # Strong penalty for drafting a 2nd TE early.
                    score -= 8.0

        # ----- RB/WR balance rules -----
        # Don't go completely insane with 5 WR before any RB, etc.
        if player.position == "WR":
            if wr_count >= 4 and rb_count == 0:
                score -= 12.0
            elif wr_count >= 4 and rb_count <= 1 and round_index <= 8:
                score -= 6.0

        if player.position == "RB":
            if rb_count >= 4 and wr_count == 0:
                score -= 12.0
            elif rb_count >= 4 and wr_count <= 1 and round_index <= 8:
                score -= 6.0

        # ----- stacking bonus (QB <-> WR/TE on same NFL team) -----
        # stack_weight controls how strong stacking is for this bot.
        if player.position in ("WR", "TE") and player.team in qb_teams:
            score += stack_weight

        if player.position == "QB" and player.team in receiver_teams:
            score += stack_weight

        # ----- controlled randomness (additive) -----
        # Earlier rounds: small noise, later rounds: larger.
        noise_scale = min(1.0 + 0.5 * (round_index - 1), 4.0)
        noise = random.uniform(-noise_scale, noise_scale) * randomness_factor
        score += noise

        return score

    def make_bot_pick_with_prefs(
        self,
        rb_pref: int,
        qb_pref: int,
        rookie_pref: int,
        fav_team: Optional[str] = None,
        team_pref: int = 0,
        stack_weight: float = 1.5,
        randomness_factor: float = 1.0,
        lookahead: int = 30,
        **kwargs,
    ) -> Optional[Player]:
        """
        Bot pick that takes into account position / rookie / team preferences.

        - Look at the top `lookahead` players by ADP (e.g., top 30)
        - Score them using the sliders + randomness
        - Draft the one with the highest score
        """
        if not self.player_pool:
            return None

        # Limit to top N by ADP so bot still behaves reasonably
        candidates = self.player_pool[:lookahead]

        # Choose the player with the highest preference-based score
        best_player = max(
            candidates,
            key=lambda p: self._score_player_for_prefs(
                p,
                rb_pref,
                qb_pref,
                rookie_pref,
                fav_team,
                team_pref,
                stack_weight,
                randomness_factor,
            ),
        )

        # Remove that specific player from the pool
        idx = self.player_pool.index(best_player)
        player = self.player_pool.pop(idx)

        # Assign to current team and advance the draft
        team_idx = self.get_current_team_index()
        self.teams[team_idx].add_player(player)
        self._advance_pick()
        return player

    # ---------- user picks ----------

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
