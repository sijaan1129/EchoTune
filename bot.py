import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import yt_dlp
import os
from keep_alive import keep_alive
from spotify_utils import get_spotify_track
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
queue = []

YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist': True}
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1', 'options': '-vn'}

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="play", description="Play a song from YouTube or Spotify")
    async def play(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()

        if "spotify.com" in url:
            url = get_spotify_track(url)  # Convert Spotify to YouTube search

        voice_channel = interaction.user.voice.channel
        if not voice_channel:
            return await interaction.followup.send("You must be in a voice channel!")

        vc = interaction.guild.voice_client
        if not vc:
            vc = await voice_channel.connect()

        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info['url']
            title = info.get('title')
            thumbnail = info.get('thumbnail')

        vc.stop()
        vc.play(discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS))

        embed = discord.Embed(title="Now Playing 🎶", description=title, color=0x1DB954)
        embed.set_thumbnail(url=thumbnail)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="stop", description="Stop playback and leave the channel")
    async def stop(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            await vc.disconnect()
            await interaction.response.send_message("Stopped music and left the channel.")
        else:
            await interaction.response.send_message("I'm not connected to any voice channel.")

async def setup():
    await bot.wait_until_ready()
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"Error syncing commands: {e}")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await setup()

bot.tree.add_command(Music(bot).play)
bot.tree.add_command(Music(bot).stop)

keep_alive()  # Start Flask webserver for Render
bot.run(os.getenv("DISCORD_TOKEN"))
