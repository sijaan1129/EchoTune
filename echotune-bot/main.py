import discord
from discord.ext import commands
import wavelink
import motor.motor_asyncio
from pymongo import MongoClient
import os

# MongoDB setup
client = motor.motor_asyncio.AsyncIOMotorClient(os.getenv("MONGO_URI"))
db = client["echotune"]

# Discord Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"EchoTune is online as {bot.user}")
    await wavelink.NodePool.create_node(
        bot=bot,
        host='lava.link',
        port=80,
        password='youshallnotpass',
        https=False
    )

@bot.slash_command(name="play", description="Play a song instantly by searching.")
async def play(ctx: discord.ApplicationContext, query: str):
    if not ctx.author.voice:
        return await ctx.respond("Join a voice channel first!")
    
    vc: wavelink.Player = ctx.voice_client or await ctx.author.voice.channel.connect(cls=wavelink.Player)
    track = await wavelink.YouTubeTrack.search(query, return_first=True)
    await vc.play(track)
    await ctx.respond(f"🎶 Now playing: `{track.title}`")

@bot.slash_command(name="24-7", description="Enable/Disable 24/7 stream.")
async def toggle_24_7(ctx: discord.ApplicationContext, enable: bool):
    server_id = str(ctx.guild.id)
    settings = db["settings"]

    # Update the 24/7 setting in MongoDB
    await settings.update_one(
        {"server_id": server_id},
        {"$set": {"24_7": enable}},
        upsert=True
    )

    await ctx.respond(f"24/7 mode {'enabled' if enable else 'disabled'}.")

@bot.slash_command(name="volume", description="Set the bot's volume.")
async def volume(ctx: discord.ApplicationContext, volume: int):
    if not (1 <= volume <= 100):
        return await ctx.respond("Volume must be between 1 and 100.")
    
    server_id = str(ctx.guild.id)
    settings = db["settings"]
    
    # Update the volume setting in MongoDB
    await settings.update_one(
        {"server_id": server_id},
        {"$set": {"volume": volume}},
        upsert=True
    )

    await ctx.respond(f"Volume set to {volume}%.")

# Start the bot
bot.run(os.getenv("DISCORD_BOT_TOKEN"))
