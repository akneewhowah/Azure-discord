import asyncio
import logging
import platform
import random
import time
from typing import Literal, Optional, Tuple

import discord
from discord import app_commands
from discord.ext import commands
from aiohttp import web

import config
from economy import economy, DAILY_REWARD, DAILY_COOLDOWN
from health_server import create_health_app, get_uptime_formatted

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("azure_bot")

intents = discord.Intents.default()
intents.message_content = True


# ---------------------------------------------------------
# Helper Functions: Parsing & Result Embeds
# ---------------------------------------------------------

def parse_choice(choice_str: str) -> Optional[str]:
    """Normalize input into 'heads' or 'tails'."""
    c = choice_str.lower().strip()
    if c in ("h", "head", "heads", "👑", "headz"):
        return "heads"
    if c in ("t", "tail", "tails", "🦅", "tailz"):
        return "tails"
    return None


def parse_bet(bet_str: str, current_balance: int) -> Tuple[Optional[int], Optional[str]]:
    """Parse bet input into an integer or return an error message."""
    b = str(bet_str).lower().strip().replace(",", "").replace("$", "")
    if b in ("all", "all-in", "max"):
        if current_balance <= 0:
            return None, "You have **0** coins! Use `/daily` or `!daily` to claim free coins."
        return current_balance, None

    if b in ("half", "50%"):
        half = current_balance // 2
        if half <= 0:
            return None, "You don't have enough coins to bet half!"
        return half, None

    try:
        amount = int(b)
        if amount <= 0:
            return None, "Bet must be at least **1** coin!"
        if amount > current_balance:
            return None, f"Insufficient funds! You have **{current_balance:,}** 🪙, but tried to bet **{amount:,}** 🪙."
        return amount, None
    except ValueError:
        return None, "Invalid bet amount! Enter a positive number (e.g. `100`), or `all` / `half`."


def execute_coin_flip(user_id: int | str, choice: str, bet: int) -> Tuple[bool, str, int, int]:
    """
    Simulate coin toss and update economy.
    Returns (won, outcome, net_change, new_balance).
    """
    outcome = random.choice(["heads", "tails"])
    won = (choice.lower() == outcome)
    net_change, new_bal = economy.record_bet(user_id, bet, won)
    return won, outcome, net_change, new_bal


def create_flip_embed(
    author: discord.User | discord.Member,
    choice: str,
    outcome: str,
    bet: int,
    won: bool,
    new_balance: int
) -> discord.Embed:
    """Generate a rich embed displaying the coin toss outcome."""
    choice_icon = "👑 Heads" if choice == "heads" else "🦅 Tails"
    outcome_icon = "👑 Heads" if outcome == "heads" else "🦅 Tails"

    if won:
        embed = discord.Embed(
            title="🎉 VICTORY! The coin landed on " + outcome_icon + "!",
            description=f"Congratulations {author.mention}, you won your coin toss gamble!",
            color=0x22C55E  # Bright Green
        )
        embed.add_field(name="🎯 Your Call", value=f"**{choice_icon}**", inline=True)
        embed.add_field(name="🪙 Coin Result", value=f"**{outcome_icon}**", inline=True)
        embed.add_field(name="💰 Profit", value=f"**+{bet:,}** 🪙", inline=True)
    else:
        embed = discord.Embed(
            title="💔 DEFEAT! The coin landed on " + outcome_icon + "!",
            description=f"Better luck next time {author.mention}!",
            color=0xEF4444  # Crimson Red
        )
        embed.add_field(name="🎯 Your Call", value=f"**{choice_icon}**", inline=True)
        embed.add_field(name="🪙 Coin Result", value=f"**{outcome_icon}**", inline=True)
        embed.add_field(name="💸 Loss", value=f"**-{bet:,}** 🪙", inline=True)

    embed.add_field(name="💳 New Balance", value=f"**{new_balance:,}** 🪙", inline=False)
    embed.set_footer(text="Gamble responsibly • Powered by Azure Discord Bot")
    return embed


# ---------------------------------------------------------
# Interactive UI View (Flip Again & Check Balance Buttons)
# ---------------------------------------------------------

class CoinTossActionView(discord.ui.View):
    def __init__(self, author_id: int, choice: str, bet: int):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.choice = choice
        self.bet = bet

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ You cannot use buttons on someone else's game!",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="🔁 Flip Again", style=discord.ButtonStyle.primary)
    async def flip_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_bal = economy.get_balance(self.author_id)
        if current_bal < self.bet:
            await interaction.response.send_message(
                f"❌ You do not have enough coins to bet **{self.bet:,}** 🪙 again! Your balance: **{current_bal:,}** 🪙. Use `/daily` to get more.",
                ephemeral=True
            )
            return

        won, outcome, net_change, new_bal = execute_coin_flip(self.author_id, self.choice, self.bet)
        embed = create_flip_embed(interaction.user, self.choice, outcome, self.bet, won, new_bal)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="💰 Balance", style=discord.ButtonStyle.secondary)
    async def check_balance(self, interaction: discord.Interaction, button: discord.ui.Button):
        bal = economy.get_balance(self.author_id)
        await interaction.response.send_message(
            f"💳 Your current balance is **{bal:,}** 🪙",
            ephemeral=True
        )


# ---------------------------------------------------------
# Interactive Game Setup View (If user enters command without args)
# ---------------------------------------------------------

class QuickFlipView(discord.ui.View):
    def __init__(self, author: discord.User | discord.Member):
        super().__init__(timeout=60)
        self.author = author
        self.selected_choice: Optional[str] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "❌ This interactive board is not for you. Start your own with `/cointoss`!",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="👑 Heads", style=discord.ButtonStyle.primary)
    async def choose_heads(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.selected_choice = "heads"
        await self._prompt_or_flip(interaction)

    @discord.ui.button(label="🦅 Tails", style=discord.ButtonStyle.secondary)
    async def choose_tails(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.selected_choice = "tails"
        await self._prompt_or_flip(interaction)

    async def _prompt_or_flip(self, interaction: discord.Interaction):
        # Default quick bet: 50 coins or all if balance < 50
        bal = economy.get_balance(self.author.id)
        if bal <= 0:
            await interaction.response.send_message(
                "❌ You don't have any coins! Use `/daily` to claim 250 free coins.",
                ephemeral=True
            )
            return

        bet = min(50, bal)
        won, outcome, net_change, new_bal = execute_coin_flip(self.author.id, self.selected_choice, bet)
        embed = create_flip_embed(self.author, self.selected_choice, outcome, bet, won, new_bal)
        next_view = CoinTossActionView(self.author.id, self.selected_choice, bet)
        await interaction.response.edit_message(embed=embed, view=next_view)


# ---------------------------------------------------------
# Discord Bot Core Class
# ---------------------------------------------------------

class GamblingBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )
        self.start_time = time.time()

    async def setup_hook(self):
        """Register and sync slash commands with Discord."""
        logger.info("Syncing slash commands...")
        try:
            synced = await self.tree.sync()
            logger.info(f"Successfully synced {len(synced)} slash command(s).")
        except Exception as e:
            logger.error(f"Error syncing slash commands: {e}")

    async def on_ready(self):
        logger.info(f"Bot logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guild(s)")

        # Set Gambling status presence
        activity = discord.Activity(
            type=discord.ActivityType.competing,
            name="🪙 Coin Toss | /cointoss"
        )
        await self.change_presence(status=discord.Status.online, activity=activity)

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Direct mention handler
        if self.user and self.user.mentioned_in(message) and not message.mention_everyone:
            clean = message.clean_content.replace(f"@{self.user.display_name}", "").strip()
            parts = clean.split()
            if len(parts) >= 2 and parts[0].lower() in ("flip", "cointoss", "cf"):
                # e.g. @bot flip heads 100
                choice = parse_choice(parts[1])
                bet_str = parts[2] if len(parts) > 2 else "50"
                if choice:
                    bal = economy.get_balance(message.author.id)
                    bet, err = parse_bet(bet_str, bal)
                    if err:
                        await message.reply(f"⚠️ {err}", mention_author=False)
                        return
                    won, outcome, net_change, new_bal = execute_coin_flip(message.author.id, choice, bet)
                    embed = create_flip_embed(message.author, choice, outcome, bet, won, new_bal)
                    view = CoinTossActionView(message.author.id, choice, bet)
                    await message.reply(embed=embed, view=view, mention_author=False)
                    return

            # Default reply on mention
            await message.reply(
                "🪙 **Welcome to the Coin Toss Casino!**\n"
                "Try `/cointoss <heads|tails> <bet>` or `!cointoss heads 100`.\n"
                "Check your balance with `/balance` and get free coins with `/daily`!",
                mention_author=False
            )
            return

        await self.process_commands(message)


bot = GamblingBot()


# ---------------------------------------------------------
# Slash Commands: Coin Toss & Gambling
# ---------------------------------------------------------

@bot.tree.command(name="cointoss", description="Gamble coins on a heads or tails coin toss!")
@app_commands.describe(
    choice="Choose Heads or Tails",
    bet="Bet amount in coins (e.g. 50, 100, 'all', 'half')"
)
async def slash_cointoss(
    interaction: discord.Interaction,
    choice: Literal["heads", "tails"],
    bet: str = "50"
):
    current_bal = economy.get_balance(interaction.user.id)
    bet_amount, err = parse_bet(bet, current_bal)
    if err:
        await interaction.response.send_message(f"⚠️ {err}", ephemeral=True)
        return

    won, outcome, net_change, new_bal = execute_coin_flip(interaction.user.id, choice, bet_amount)
    embed = create_flip_embed(interaction.user, choice, outcome, bet_amount, won, new_bal)
    view = CoinTossActionView(interaction.user.id, choice, bet_amount)
    await interaction.response.send_message(embed=embed, view=view)


@bot.tree.command(name="coinflip", description="Quick interactive coin toss game.")
async def slash_coinflip(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🪙 Coin Toss Game",
        description=(
            "Pick **Heads (👑)** or **Tails (🦅)** below to flip for **50** coins!\n"
            "Or use `/cointoss <choice> <bet>` for custom amounts."
        ),
        color=0xF59E0B
    )
    bal = economy.get_balance(interaction.user.id)
    embed.add_field(name="💳 Your Balance", value=f"**{bal:,}** 🪙", inline=False)
    view = QuickFlipView(interaction.user)
    await interaction.response.send_message(embed=embed, view=view)


@bot.tree.command(name="balance", description="Check your coin balance and gambling statistics.")
@app_commands.describe(user="User to check balance for (leave empty for yourself)")
async def slash_balance(interaction: discord.Interaction, user: Optional[discord.User] = None):
    target = user or interaction.user
    stats = economy.get_user(target.id)

    total_games = stats.get("wins", 0) + stats.get("losses", 0)
    win_rate = round((stats.get("wins", 0) / total_games * 100), 1) if total_games > 0 else 0.0
    profit = stats.get("net_profit", 0)
    profit_str = f"+{profit:,}" if profit >= 0 else f"{profit:,}"

    embed = discord.Embed(
        title=f"💳 {target.display_name}'s Casino Wallet",
        color=0xF59E0B
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="🪙 Balance", value=f"### **{stats['balance']:,}** coins", inline=False)
    embed.add_field(name="🏆 Total Wins", value=f"**{stats['wins']:,}**", inline=True)
    embed.add_field(name="💀 Total Losses", value=f"**{stats['losses']:,}**", inline=True)
    embed.add_field(name="📊 Win Rate", value=f"**{win_rate}%**", inline=True)
    embed.add_field(name="📈 Net Profit / Loss", value=f"**{profit_str}** 🪙", inline=True)
    embed.add_field(name="🎲 Total Wagered", value=f"**{stats['total_bet']:,}** 🪙", inline=True)
    embed.set_footer(text="Use /daily every 24h to claim free coins!")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="daily", description="Claim your daily allowance of 250 free coins!")
async def slash_daily(interaction: discord.Interaction):
    success, amount, remaining = economy.claim_daily(interaction.user.id)
    if success:
        new_bal = economy.get_balance(interaction.user.id)
        embed = discord.Embed(
            title="🎁 Daily Reward Claimed!",
            description=f"You received **+{amount:,}** 🪙 coins!\nNew balance: **{new_bal:,}** 🪙",
            color=0x22C55E
        )
        embed.set_footer(text="Come back in 24 hours for more!")
        await interaction.response.send_message(embed=embed)
    else:
        hours, rem = divmod(remaining, 3600)
        minutes, seconds = divmod(rem, 60)
        time_str = f"{hours}h {minutes}m {seconds}s"
        embed = discord.Embed(
            title="⏳ Daily Already Claimed!",
            description=f"You've already claimed your daily reward today!\nPlease wait **{time_str}** before claiming again.",
            color=0xF59E0B
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="leaderboard", description="View the top richest gamblers!")
async def slash_leaderboard(interaction: discord.Interaction):
    leaders = economy.get_leaderboard(limit=10)
    if not leaders:
        await interaction.response.send_message("No gamblers recorded yet! Start playing with `/cointoss`.")
        return

    embed = discord.Embed(
        title="🏆 High Rollers Leaderboard",
        description="The wealthiest gamblers in the casino:",
        color=0xF59E0B
    )

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    lines = []
    for idx, (uid, bal, wins, losses) in enumerate(leaders):
        medal = medals[idx] if idx < len(medals) else f"#{idx+1}"
        lines.append(f"{medal} <@{uid}> — **{bal:,}** 🪙 *({wins}W / {losses}L)*")

    embed.description = "\n".join(lines)
    embed.set_footer(text="Climb the ranks with /cointoss!")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="give", description="Transfer coins to another user.")
@app_commands.describe(
    user="The user to send coins to",
    amount="Number of coins to send"
)
async def slash_give(interaction: discord.Interaction, user: discord.User, amount: int):
    if user.bot:
        await interaction.response.send_message("❌ You cannot send coins to bots!", ephemeral=True)
        return

    success, msg = economy.transfer(interaction.user.id, user.id, amount)
    if success:
        embed = discord.Embed(
            title="💸 Coin Transfer Successful",
            description=f"{interaction.user.mention} sent **{amount:,}** 🪙 coins to {user.mention}!",
            color=0x22C55E
        )
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(f"⚠️ {msg}", ephemeral=True)


@bot.tree.command(name="ping", description="Check the bot's WebSocket latency.")
async def ping(interaction: discord.Interaction):
    latency_ms = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latency: **{latency_ms} ms**",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="azure", description="View Azure cloud hosting status, specs, and uptime.")
async def azure_info(interaction: discord.Interaction):
    embed = discord.Embed(
        title="☁️ Microsoft Azure Hosting Status",
        description="This bot is configured and optimized for Microsoft Azure deployment.",
        color=discord.Color.from_rgb(0, 120, 212)
    )
    status_label = "✅ Active on Azure" if config.IS_AZURE else "💻 Local Machine (Ready for Azure)"
    embed.add_field(name="Hosting Environment", value=status_label, inline=False)
    embed.add_field(name="App Instance", value=config.AZURE_APP_NAME, inline=True)
    embed.add_field(name="Uptime", value=get_uptime_formatted(), inline=True)
    embed.add_field(name="Python Version", value=platform.python_version(), inline=True)
    embed.add_field(name="OS Platform", value=f"{platform.system()} {platform.release()}", inline=True)
    embed.add_field(name="Connected Servers", value=str(len(bot.guilds)), inline=True)
    embed.add_field(
        name="Health Check Endpoint",
        value=f"Internal Port `{config.PORT}` (`/health`)",
        inline=False
    )
    embed.set_footer(text="Powered by discord.py & Microsoft Azure")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="help", description="Show casino commands and rules.")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🪙 Coin Toss Casino Bot — Command Guide",
        description="Welcome to the Discord Coin Toss Gambling Bot! Bet coins on coin flips and build your fortune.",
        color=0xF59E0B
    )
    embed.add_field(
        name="🪙 `/cointoss <heads|tails> <bet>` (or `!cointoss` / `!cf`)",
        value="Bet coins on a coin flip. Bets can be numbers, `all`, or `half`.\n*Example:* `/cointoss heads 100` or `!cf tails all`",
        inline=False
    )
    embed.add_field(
        name="🎮 `/coinflip` (or `!flip`)",
        value="Launches an interactive button menu to flip coins.",
        inline=False
    )
    embed.add_field(
        name="💳 `/balance` (or `!balance`, `!bal`)",
        value="View your wallet balance, win/loss record, and net earnings.",
        inline=False
    )
    embed.add_field(
        name="🎁 `/daily` (or `!daily`)",
        value="Claim **250 free coins** every 24 hours.",
        inline=False
    )
    embed.add_field(
        name="🏆 `/leaderboard` (or `!leaderboard`, `!top`)",
        value="See who holds the most coins.",
        inline=False
    )
    embed.add_field(
        name="💸 `/give <user> <amount>` (or `!give`)",
        value="Transfer coins to a friend.",
        inline=False
    )
    embed.add_field(
        name="☁️ `/azure` & 🏓 `/ping`",
        value="Check system uptime, cloud status, and gateway latency.",
        inline=False
    )
    embed.set_footer(text="Every new player starts with 1,000 coins!")
    await interaction.response.send_message(embed=embed)


# ---------------------------------------------------------
# Prefix Commands (!cointoss, !cf, !flip, !bal, !daily, etc.)
# ---------------------------------------------------------

@bot.command(name="cointoss", aliases=["cf", "flip", "coinflip"])
async def prefix_cointoss(ctx: commands.Context, choice: str = "", bet: str = ""):
    if not choice:
        # Launch quick interactive button menu
        embed = discord.Embed(
            title="🪙 Coin Toss Game",
            description="Pick **Heads (👑)** or **Tails (🦅)** below to flip for **50** coins!",
            color=0xF59E0B
        )
        bal = economy.get_balance(ctx.author.id)
        embed.add_field(name="💳 Your Balance", value=f"**{bal:,}** 🪙", inline=False)
        view = QuickFlipView(ctx.author)
        await ctx.send(embed=embed, view=view)
        return

    parsed_choice = parse_choice(choice)
    if not parsed_choice:
        await ctx.send("⚠️ Invalid choice! Choose either `heads` (or `h`) or `tails` (or `t`).\n*Example:* `!cf heads 100`")
        return

    current_bal = economy.get_balance(ctx.author.id)
    bet_str = bet if bet else "50"
    bet_amount, err = parse_bet(bet_str, current_bal)
    if err:
        await ctx.send(f"⚠️ {err}")
        return

    won, outcome, net_change, new_bal = execute_coin_flip(ctx.author.id, parsed_choice, bet_amount)
    embed = create_flip_embed(ctx.author, parsed_choice, outcome, bet_amount, won, new_bal)
    view = CoinTossActionView(ctx.author.id, parsed_choice, bet_amount)
    await ctx.send(embed=embed, view=view)


@bot.command(name="balance", aliases=["bal", "coins", "wallet"])
async def prefix_balance(ctx: commands.Context, member: Optional[discord.Member] = None):
    target = member or ctx.author
    stats = economy.get_user(target.id)

    total_games = stats.get("wins", 0) + stats.get("losses", 0)
    win_rate = round((stats.get("wins", 0) / total_games * 100), 1) if total_games > 0 else 0.0
    profit = stats.get("net_profit", 0)
    profit_str = f"+{profit:,}" if profit >= 0 else f"{profit:,}"

    embed = discord.Embed(
        title=f"💳 {target.display_name}'s Casino Wallet",
        color=0xF59E0B
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="🪙 Balance", value=f"### **{stats['balance']:,}** coins", inline=False)
    embed.add_field(name="🏆 Total Wins", value=f"**{stats['wins']:,}**", inline=True)
    embed.add_field(name="💀 Total Losses", value=f"**{stats['losses']:,}**", inline=True)
    embed.add_field(name="📊 Win Rate", value=f"**{win_rate}%**", inline=True)
    embed.add_field(name="📈 Net Profit / Loss", value=f"**{profit_str}** 🪙", inline=True)
    embed.add_field(name="🎲 Total Wagered", value=f"**{stats['total_bet']:,}** 🪙", inline=True)
    embed.set_footer(text="Use !daily every 24h to claim free coins!")
    await ctx.send(embed=embed)


@bot.command(name="daily")
async def prefix_daily(ctx: commands.Context):
    success, amount, remaining = economy.claim_daily(ctx.author.id)
    if success:
        new_bal = economy.get_balance(ctx.author.id)
        embed = discord.Embed(
            title="🎁 Daily Reward Claimed!",
            description=f"You received **+{amount:,}** 🪙 coins!\nNew balance: **{new_bal:,}** 🪙",
            color=0x22C55E
        )
        embed.set_footer(text="Come back in 24 hours for more!")
        await ctx.send(embed=embed)
    else:
        hours, rem = divmod(remaining, 3600)
        minutes, seconds = divmod(rem, 60)
        time_str = f"{hours}h {minutes}m {seconds}s"
        embed = discord.Embed(
            title="⏳ Daily Already Claimed!",
            description=f"You've already claimed your daily reward today!\nPlease wait **{time_str}** before claiming again.",
            color=0xF59E0B
        )
        await ctx.send(embed=embed)


@bot.command(name="leaderboard", aliases=["lb", "top"])
async def prefix_leaderboard(ctx: commands.Context):
    leaders = economy.get_leaderboard(limit=10)
    if not leaders:
        await ctx.send("No gamblers recorded yet! Start playing with `!cf heads 50`.")
        return

    embed = discord.Embed(
        title="🏆 High Rollers Leaderboard",
        description="The wealthiest gamblers in the casino:",
        color=0xF59E0B
    )

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    lines = []
    for idx, (uid, bal, wins, losses) in enumerate(leaders):
        medal = medals[idx] if idx < len(medals) else f"#{idx+1}"
        lines.append(f"{medal} <@{uid}> — **{bal:,}** 🪙 *({wins}W / {losses}L)*")

    embed.description = "\n".join(lines)
    embed.set_footer(text="Climb the ranks with !cointoss!")
    await ctx.send(embed=embed)


@bot.command(name="give", aliases=["pay", "send"])
async def prefix_give(ctx: commands.Context, member: discord.Member, amount: int):
    if member.bot:
        await ctx.send("❌ You cannot send coins to bots!")
        return

    success, msg = economy.transfer(ctx.author.id, member.id, amount)
    if success:
        embed = discord.Embed(
            title="💸 Coin Transfer Successful",
            description=f"{ctx.author.mention} sent **{amount:,}** 🪙 coins to {member.mention}!",
            color=0x22C55E
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"⚠️ {msg}")


@bot.command(name="ping")
async def prefix_ping(ctx: commands.Context):
    latency_ms = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! Latency: `{latency_ms} ms`")


@bot.command(name="azure")
async def prefix_azure(ctx: commands.Context):
    status = "Active on Azure ☁️" if config.IS_AZURE else "Running locally 💻"
    await ctx.send(f"☁️ **Azure Status:** {status} | **Uptime:** {get_uptime_formatted()}")


@bot.command(name="help")
async def prefix_help(ctx: commands.Context):
    embed = discord.Embed(
        title="🪙 Coin Toss Casino Bot Commands",
        description="Bet coins on coin flips and build your fortune!",
        color=0xF59E0B
    )
    embed.add_field(name="`!cf <heads|tails> <bet>`", value="Bet coins on a coin flip (e.g. `!cf heads 100` or `!cf tails all`).", inline=False)
    embed.add_field(name="`!bal` / `!balance`", value="Check your balance and win/loss records.", inline=False)
    embed.add_field(name="`!daily`", value="Claim **250 free coins** every 24h.", inline=False)
    embed.add_field(name="`!leaderboard` / `!top`", value="Show top ranking gamblers.", inline=False)
    embed.add_field(name="`!give <@user> <amount>`", value="Send coins to a friend.", inline=False)
    embed.add_field(name="`!ping` & `!azure`", value="Check latency and cloud status.", inline=False)
    await ctx.send(embed=embed)


# ---------------------------------------------------------
# Main Execution: Bot + Azure Health Probe Web Server
# ---------------------------------------------------------

async def main():
    if not config.validate_config():
        logger.error("Configuration validation failed. Exiting.")
        return

    # 1. Start the internal aiohttp HTTP server for Azure health probes
    app = create_health_app(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()
    logger.info(f"Azure health check server listening on http://0.0.0.0:{config.PORT}")

    # 2. Run the Discord bot
    try:
        async with bot:
            await bot.start(config.DISCORD_TOKEN)
    except discord.LoginFailure:
        logger.error("Invalid Discord Token provided. Please check your .env file or Azure Application Settings.")
    except Exception as e:
        logger.error(f"Unexpected error running bot: {e}")
    finally:
        logger.info("Shutting down health check server...")
        await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
