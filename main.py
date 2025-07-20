import discord
from discord.ui import Button, View
import os
import random
import requests
from PIL import Image
from io import BytesIO
import yfinance as yf


TICKER_LIST = [
    "NVDA", "MSFT", "AAPL", "AMZN", "AVGO", "META", "NFLX", "TSLA", "GOOGL",
    "COST", "GOOG", "PLTR", "CSCO", "AMD", "TMUS", "LIN", "INTU", "PEP",
    "TXN", "ISRG", "BKNG", "QCOM", "AMGN", "ADBE", "AMAT", "SHOP", "HON",
    "GILD", "PANW", "CMCSA", "LRCX", "MU", "KLAC", "ADP", "ADI", "MELI",
    "VRTX", "CRWD", "APPL", "SBUX", "INTC", "CEG", "DASH", "SNPS", "MDLZ",
    "CTAS", "CDNS", "FTNT", "ORLY", "MAR", "PDD", "PYPL", "ASML", "CSX",
    "ADSK", "MRVL", "ABNB", "ROP", "REGN", "AXON", "MNST", "NXPI", "AEP",
    "CHTR", "FAST", "PAYX", "WDAY", "PCAR", "KDP", "DDOG", "ZS", "CPRT",
    "CCEP", "EXC", "ROST", "TTWO", "VRSK", "IDXX", "AZN", "FANG", "XEL",
    "MCHP", "BKR", "EA", "CTSH", "TTD", "CSGP", "ANSS", "GEHC", "ODFL",
    "KHC", "DXCM", "WBD", "TEAM", "LULU", "ON", "CDW", "GFS", "ARM", "BIIB"
]

# --- Bot Setup ---
intents = discord.Intents.default()
bot = discord.Bot(intents=intents) 
active_games = {}

# --- Helper Functions ---

def generate_wordle_feedback(guess: str, answer: str) -> str:
    """Generates Wordle-style feedback (🟩🟨⬛) for a guess."""
    if len(guess) != len(answer): return ""
    feedback = ["⬛"] * len(answer)
    answer_letters = list(answer)
    # First pass for correct letters in the correct position (green)
    for i in range(len(guess)):
        if guess[i] == answer[i]:
            feedback[i] = "🟩"
            answer_letters[i] = None # Mark as used
    # Second pass for correct letters in the wrong position (yellow)
    for i in range(len(guess)):
        if feedback[i] == "🟩": continue
        if guess[i] in answer_letters:
            feedback[i] = "🟨"
            answer_letters[answer_letters.index(guess[i])] = None # Mark as used
    return "".join(feedback)


def generate_chart_image(ticker: str, user_id: int, timeframe: str = 'd') -> str | None:
    """Generates a stock chart image from Finviz and saves it locally."""
    finviz_url = f"https://finviz.com/chart.ashx?t={ticker}&ty=c&ta=0&p={timeframe}&s=l"
    headers = {'User-Agent': 'Mozilla/5.0'} # Finviz blocks default request user-agents
    try:
        response = requests.get(finviz_url, headers=headers)
        if response.status_code != 200:
            print(f"Finviz returned status {response.status_code} for {ticker}")
            return None
        image = Image.open(BytesIO(response.content))
        # Crop the top part of the image that contains the ticker name
        width, height = image.size
        cropped_image = image.crop((0, 25, width, height))
        file_path = f"chart_{user_id}.png"
        cropped_image.save(file_path)
        return file_path
    except Exception as e:
        print(f"Error generating chart for {ticker}: {e}")
        return None


def get_stock_data(ticker: str) -> dict | None:
    """Fetches stock data from yfinance and validates it."""
    try:
        stock = yf.Ticker(ticker)
        # A robust check: ensure info exists and has a market cap.
        # This filters out invalid tickers and some non-stock entities.
        if stock.info and stock.info.get('marketCap') is not None:
            return {
                "ticker": stock.info.get('symbol', 'N/A'),
                "name": stock.info.get('longName', 'N/A'),
                "sector": stock.info.get('sector', 'N/A'),
                "market_cap": stock.info.get('marketCap', 0)
            }
        return None
    except Exception:
        # yfinance will throw an error for most invalid tickers, which we catch here.
        return None

# --- UI Views ---

class TimeframeView(View):
    """A view with buttons to change the timeframe of the stock chart."""
    def __init__(self, author_id: int, original_message: discord.InteractionMessage):
        super().__init__(timeout=300) # View times out after 5 minutes
        self.author_id = author_id
        self.message = original_message

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensures only the person who started the game can use the buttons."""
        if interaction.user.id == self.author_id:
            return True
        await interaction.response.send_message("This isn't your game!", ephemeral=True)
        return False

    async def update_chart(self, interaction: discord.Interaction, timeframe: str):
        """Updates the chart image in the original message."""
        await interaction.response.defer() # Acknowledge the interaction
        game = active_games.get(interaction.user.id)
        if not game:
            await interaction.followup.send("Your game has ended.", ephemeral=True)
            self.stop() # Disable the view
            return

        ticker = game["answer"]
        chart_file_path = generate_chart_image(ticker, interaction.user.id, timeframe=timeframe)

        if chart_file_path:
            embed = self.message.embeds[0]
            # Use a random filename to bypass Discord's image cache
            cache_buster = f"stock_chart_{random.randint(1,99999)}.png"
            embed.set_image(url=f"attachment://{cache_buster}")
            with open(chart_file_path, 'rb') as f:
                picture = discord.File(f, filename=cache_buster)
                await self.message.edit(embed=embed, files=[picture], view=self)
            os.remove(chart_file_path)
        else:
            await interaction.followup.send("Sorry, couldn't generate the new chart.", ephemeral=True)

    @discord.ui.button(label="Daily", style=discord.ButtonStyle.success)
    async def daily_button(self, button: Button, interaction: discord.Interaction):
        await self.update_chart(interaction, 'd')

    @discord.ui.button(label="Weekly", style=discord.ButtonStyle.primary)
    async def weekly_button(self, button: Button, interaction: discord.Interaction):
        await self.update_chart(interaction, 'w')

    @discord.ui.button(label="Monthly", style=discord.ButtonStyle.secondary)
    async def monthly_button(self, button: Button, interaction: discord.Interaction):
        await self.update_chart(interaction, 'm')

# --- Bot Events and Commands ---

@bot.event
async def on_ready():
    """Event handler for when the bot logs in."""
    print(f"Bot '{bot.user.name}' is online and ready!")

@bot.slash_command(name="stockle", description="Start a new game of Stockle!")
async def stockle(ctx: discord.ApplicationContext):
    user_id = ctx.author.id
    if user_id in active_games:
        await ctx.respond("You already have a game in progress! Use `/quit` to end it.", ephemeral=True)
        return

    await ctx.defer() # Defer the response as fetching data can take time

    # Find a valid ticker to use as the answer
    answer_ticker = random.choice(TICKER_LIST)
    answer_data = get_stock_data(answer_ticker)
    if not answer_data:
        await ctx.followup.send("Sorry, couldn't start a game. The chosen answer stock was invalid.", ephemeral=True)
        return

    chart_file_path = generate_chart_image(answer_ticker, user_id, timeframe='d')
    if not chart_file_path:
        await ctx.followup.send("Sorry, couldn't generate the stock chart for the game.", ephemeral=True)
        return

    # Create the initial game message
    embed = discord.Embed(
        title="Guess the Stock Ticker!",
        description=f"The answer is a **{len(answer_ticker)}-letter** ticker.\nUse `/guess <TICKER>` to play.",
        color=discord.Color.green()
    )
    file = discord.File(chart_file_path, filename="stock_chart.png")
    embed.set_image(url="attachment://stock_chart.png")

    response_message = await ctx.followup.send(embed=embed, file=file, wait=True)
    view = TimeframeView(author_id=user_id, original_message=response_message)
    await response_message.edit(view=view)

    # Store the game state
    active_games[user_id] = {
        "answer": answer_ticker,
        "answer_data": answer_data,
        "guesses": 0,
        "history": [],
        "message": response_message
    }
    os.remove(chart_file_path)


@bot.slash_command(name="guess", description="Make a guess in your current Stockle game.")
async def guess(ctx: discord.ApplicationContext, ticker: str):
    user_id = ctx.author.id
    guess_ticker = ticker.upper().strip() # Standardize the guess

    if user_id not in active_games:
        await ctx.respond("You don't have a game in progress. Use `/stockle` to start one.", ephemeral=True)
        return

    game = active_games[user_id]
    answer_ticker = game["answer"]

    if len(guess_ticker) != len(answer_ticker):
        await ctx.respond(f"Your guess must be a **{len(answer_ticker)}-letter** ticker.", ephemeral=True)
        return

    await ctx.defer()

    # Fetch data for the guessed ticker to validate it and get its info
    guess_data = get_stock_data(guess_ticker)
    if not guess_data:
        await ctx.respond(
            f"'{guess_ticker}' doesn't seem to be a valid stock ticker. Please try again.",
            ephemeral=True
        )
        return

    # Process the guess
    game["guesses"] += 1
    answer_data = game["answer_data"]

    # Generate feedback hints
    wordle_hint = generate_wordle_feedback(guess_ticker, answer_ticker)
    sector_feedback = f"🟩 {answer_data['sector']}" if guess_data["sector"] == answer_data["sector"] else "🟥 Wrong"
    cap_feedback = ("✅ Correct" if guess_data["market_cap"] == answer_data["market_cap"]
                    else "⬇️ Lower" if guess_data["market_cap"] > answer_data["market_cap"]
                    else "⬆️ Higher")

    # Add the current guess to the game's history
    history_line = f"**{game['guesses']}.** `{guess_ticker}` {wordle_hint}\n> Sector: {sector_feedback} | Mkt Cap: {cap_feedback}"
    game["history"].append(history_line)

    is_win = (guess_ticker == answer_ticker)
    is_loss = (game["guesses"] >= 6 and not is_win)

    # Check for win/loss condition
    if is_win or is_loss:
        if is_win:
            end_title = f"🎉 You got it! It was {answer_ticker}!"
            end_desc = f"**{answer_data['name']}**\n\n" + "\n\n".join(game["history"])
            end_color = discord.Color.gold()
        else: # Loss condition
            end_title = "Game Over!"
            end_desc = f"The correct ticker was **{answer_ticker} ({answer_data['name']})**.\n\n" + "\n\n".join(game["history"])
            end_color = discord.Color.red()

        end_embed = discord.Embed(title=end_title, description=end_desc, color=end_color)

        original_message = game.get("message")
        if original_message:
            await original_message.edit(view=None) # Remove buttons from original message

        await ctx.respond(embed=end_embed)
        del active_games[user_id] # Clean up the finished game
        return

    # If the game is not over, show the updated history
    embed = discord.Embed(title="Your Guess History", description="\n\n".join(game["history"]), color=discord.Color.blue())
    embed.set_footer(text=f"You have {6 - game['guesses']} guesses left.")
    await ctx.respond(embed=embed)


@bot.slash_command(name="quit", description="Quit your current Stockle game.")
async def quit_game(ctx: discord.ApplicationContext):
    user_id = ctx.author.id
    if user_id in active_games:
        game = active_games[user_id]
        original_message = game.get("message")
        if original_message:
            await original_message.edit(view=None) # Remove buttons
        del active_games[user_id]
        await ctx.respond("Your game has been ended.", ephemeral=True)
    else:
        await ctx.respond("You don't have an active game to quit.", ephemeral=True)

# --- Run the Bot ---
# Make sure to set your bot's token as an environment variable.
# For example, in Replit, use the "Secrets" tab to set DISCORD_TOKEN.
try:
    TOKEN = os.environ['DISCORD_TOKEN']
    bot.run(TOKEN)
except KeyError:
    print("FATAL ERROR: DISCORD_TOKEN environment variable not set.")
    print("Please set your bot's token as an environment variable (e.g., in Replit Secrets).")
