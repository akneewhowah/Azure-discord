import json
import logging
import os
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("azure_bot.economy")

ECONOMY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "economy.json")
STARTING_BALANCE = 1000
DAILY_REWARD = 250
DAILY_COOLDOWN = 86400  # 24 hours in seconds


class EconomyManager:
    def __init__(self, filepath: str = ECONOMY_FILE):
        self.filepath = filepath
        self.data: Dict[str, dict] = {}
        self.load()

    def load(self):
        """Load user economy data from JSON file."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception as e:
                logger.error(f"Error loading economy file: {e}. Starting fresh.")
                self.data = {}
        else:
            self.data = {}

    def save(self):
        """Save user economy data to JSON file atomically."""
        try:
            temp_file = f"{self.filepath}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            os.replace(temp_file, self.filepath)
        except Exception as e:
            logger.error(f"Failed to save economy data: {e}")

    def get_user(self, user_id: int | str) -> dict:
        """Get user profile or initialize new one with default balance."""
        uid = str(user_id)
        if uid not in self.data:
            self.data[uid] = {
                "balance": STARTING_BALANCE,
                "last_daily": 0.0,
                "wins": 0,
                "losses": 0,
                "total_bet": 0,
                "net_profit": 0,
            }
            self.save()
        return self.data[uid]

    def get_balance(self, user_id: int | str) -> int:
        """Return the current coin balance of a user."""
        return self.get_user(user_id)["balance"]

    def adjust_balance(self, user_id: int | str, amount: int) -> int:
        """Add or subtract balance from a user and return the new balance."""
        user = self.get_user(user_id)
        user["balance"] = max(0, user["balance"] + amount)
        self.save()
        return user["balance"]

    def record_bet(self, user_id: int | str, bet: int, won: bool) -> Tuple[int, int]:
        """
        Record a gambling game result.
        If won: user receives +bet.
        If lost: user loses -bet.
        Returns (net_change, new_balance).
        """
        user = self.get_user(user_id)
        user["total_bet"] += bet

        if won:
            user["wins"] += 1
            user["balance"] += bet
            user["net_profit"] += bet
            net_change = bet
        else:
            user["losses"] += 1
            user["balance"] = max(0, user["balance"] - bet)
            user["net_profit"] -= bet
            net_change = -bet

        self.save()
        return net_change, user["balance"]

    def claim_daily(self, user_id: int | str) -> Tuple[bool, int, int]:
        """
        Attempt to claim daily reward.
        Returns:
            (success, amount_awarded_or_0, seconds_remaining_if_cooldown)
        """
        user = self.get_user(user_id)
        now = time.time()
        elapsed = now - user.get("last_daily", 0.0)

        if elapsed < DAILY_COOLDOWN:
            remaining = int(DAILY_COOLDOWN - elapsed)
            return False, 0, remaining

        user["balance"] += DAILY_REWARD
        user["last_daily"] = now
        self.save()
        return True, DAILY_REWARD, 0

    def transfer(self, sender_id: int | str, receiver_id: int | str, amount: int) -> Tuple[bool, str]:
        """Transfer coins from one user to another."""
        sender_id = str(sender_id)
        receiver_id = str(receiver_id)

        if sender_id == receiver_id:
            return False, "You cannot send coins to yourself!"

        if amount <= 0:
            return False, "Transfer amount must be at least 1 coin."

        sender_bal = self.get_balance(sender_id)
        if sender_bal < amount:
            return False, f"Insufficient funds! You only have **{sender_bal:,}** coins."

        self.adjust_balance(sender_id, -amount)
        self.adjust_balance(receiver_id, amount)
        return True, f"Successfully sent **{amount:,}** coins!"

    def get_leaderboard(self, limit: int = 10) -> List[Tuple[str, int, int, int]]:
        """
        Return top users by balance.
        List of tuples: (user_id, balance, wins, losses)
        """
        users = []
        for uid, stats in self.data.items():
            users.append((
                uid,
                stats.get("balance", 0),
                stats.get("wins", 0),
                stats.get("losses", 0),
            ))
        # Sort descending by balance
        users.sort(key=lambda x: x[1], reverse=True)
        return users[:limit]


# Global economy instance
economy = EconomyManager()
