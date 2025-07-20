import discord
from discord.ext import commands
from discord import app_commands
import yfinance as yf
import matplotlib.pyplot as plt
from io import BytesIO
import random

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

stockle_games = {}

def get_random_nasdaq_ticker():
    while True:
        random_ticker = random.choice(yf.tickers_nasdaq())
        stock = yf.Ticker(random_ticker)
        info = stock.info
        if "shortName" in info:
            return random_ticker

def is_nasdaq_ticker(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return "Nasdaq" in info.get("exchange", "")
    except Exception:
        return False

def generate_chart(ticker, timeframe):
    stock = yf.Ticker(ticker)

    if timeframe == "1D":
        data = stock.history(period="1d", interval="5m")
    elif timeframe == "5D":
        data = stock.history(period="5d", interval="15m")
    elif timeframe == "1M":
        data = stock.history(period="1mo", interval="1d")
    elif timeframe == "6M":
        data = stock.history(period="6mo", interval="1d")
    elif timeframe == "1Y":
        data = stock.history(period="1y", interval="1d")
    else:
        data = stock.history(period="1y", interval="1d")

    if data.empty:
        raise ValueError("No data found for this ticker/timeframe.")

    fig, ax = plt.subplots()
    ax.plot(data.index, data['Close'])
    ax.set_title(f"{ticker.upper()} - {timeframe}")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price")

    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig)
    return buf

class TimeframeView(discord.ui.View):
    def __init__(self, ticker, message=None):
        super().__init__(timeout=None)
        self.ticker = ticker
        self.message = message

    @discord.ui.button(label="1D", style=discord.ButtonStyle.primary)
    async def one_day(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_chart(interaction, "1D")

    @discord.ui.button(label="5D", style=discord.ButtonStyle.primary)
    async def five_days(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_chart(interaction, "5D")

    @discord.ui.button(label="1M", style=discord.ButtonStyle.primary)
    async def one_month(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_chart(interaction, "1M")

    @discord.ui.button(label="6M", style=discord.ButtonStyle.primary)
    async def six_months(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_chart(interaction, "6M")

    @discord.ui.button(label="1Y", style=discord.ButtonStyle.primary)
    async def one_year(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_chart(interaction, "1Y")

    async def update_chart(self, interaction, timeframe):
        try:
            buf = generate_chart(self.ticker, timeframe)
            file = discord.File(buf, filename="chart.png")
            await interaction.response.edit_message(files=[file], view=self)
        except Exception as e:
            await interaction.response.send_message(f"Error generating chart: {str(e)}", ephemeral=True)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}!")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print(e)

@bot.tree.command(name="stockle", description="Start a game of Stockle!")
async def stockle(interaction: discord.Interaction):
    ticker = get_random_nasdaq_ticker()
    stockle_games[interaction.user.id] = ticker
    buf = generate_chart(ticker, "1Y")
    file = discord.File(buf, filename="chart.png")
    view = TimeframeView(ticker)
    await interaction.response.send_message("Guess the stock!", file=file, view=view)

@bot.tree.command(name="guess", description="Make a guess for the Stockle game.")
@app_commands.describe(ticker="Your guess for the stock ticker")
async def guess(interaction: discord.Interaction, ticker: str):
    if not is_nasdaq_ticker(ticker):
        await interaction.response.send_message("That’s not a valid NASDAQ-listed stock. Try again.", ephemeral=True)
        return

    answer = stockle_games.get(interaction.user.id)
    if not answer:
        await interaction.response.send_message("You haven't started a Stockle game. Use /stockle first!", ephemeral=True)
        return

    if ticker.upper() == answer:
        await interaction.response.send_message(f"🎉 Correct! The stock was **{answer}**.")
        del stockle_games[interaction.user.id]
    else:
        await interaction.response.send_message("❌ Incorrect guess. Try again!")

bot.run("YOUR_BOT_TOKEN")
