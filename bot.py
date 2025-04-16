import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import yt_dlp
import os
import random
from keep_alive import keep_alive
from spotify_utils import get_spotify_track
from dotenv import load_dotenv

load_dotenv()

# ====== CONFIGURATION ======
GUILD_ID = 123456789012345678  # <-- Replace with your Discord server ID
guild = discord.Object(id=GUILD_ID)

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ====== STATE ======
queues = {}    # guild_id: [url, ...]
loops = {}     # guild_id: "off"|"single"|"queue"
volumes = {}   # guild_id: float (0.0–1.0)

# ====== YTDL & FFMPEG ======
YDL_OPTIONS = {
    'format': 'bestaudio',
    'noplaylist': True,
    'cookies': 'cookies.txt',
    'quiet': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
}
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1',
    'options': '-vn'
}

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.current = {}  # guild_id: {title, thumbnail, url}

    async def play_next(self, interaction, guild_id):
        mode = loops.get(guild_id, "off")
        if self.current.get(guild_id) and mode in ("single", "queue"):
            url = self.current[guild_id]['url']
            if mode == "single":
                queues[guild_id].insert(0, url)
            else:
                queues[guild_id].append(url)

        if queues.get(guild_id):
            next_url = queues[guild_id].pop(0)
            vc = interaction.guild.voice_client
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                info = ydl.extract_info(next_url, download=False)
                audio_url = info['url']
                title = info.get('title')
                thumbnail = info.get('thumbnail')
                self.current[guild_id] = {'title': title, 'thumbnail': thumbnail, 'url': next_url}

            volume = volumes.get(guild_id, 1.0)
            source = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS),
                volume=volume
            )
            vc.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(interaction, guild_id), self.bot.loop))

            embed = discord.Embed(title="Now Playing 🎶", description=title, color=0x1DB954)
            embed.set_thumbnail(url=thumbnail)
            await interaction.channel.send(embed=embed)
        else:
            self.current[guild_id] = None

    @app_commands.command(name="play", description="Play a song by name or URL (YouTube/Spotify)")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.send_message("🔍 Searching...", ephemeral=True)
        guild_id = interaction.guild.id

        if "spotify.com" in query:
            query = get_spotify_track(query)
        elif not query.startswith("http"):
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                try:
                    info = ydl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]
                    query = info['webpage_url']
                except Exception:
                    return await interaction.edit_original_response(content="❌ No results found.")

        vc = interaction.guild.voice_client
        if not vc:
            voice_channel = interaction.user.voice.channel
            if not voice_channel:
                return await interaction.edit_original_response(content="❌ You must be in a voice channel!")
            vc = await voice_channel.connect()

        queues.setdefault(guild_id, [])
        if not vc.is_playing():
            queues[guild_id].insert(0, query)
            await self.play_next(interaction, guild_id)
        else:
            queues[guild_id].append(query)
            return await interaction.edit_original_response(content="✅ Added to queue.")

        await interaction.delete_original_response()

    @app_commands.command(name="pause", description="Pause the current song")
    async def pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸ Paused")
        else:
            await interaction.response.send_message("Nothing is playing.")

    @app_commands.command(name="resume", description="Resume the paused song")
    async def resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Resumed")
        else:
            await interaction.response.send_message("Nothing is paused.")

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("⏭ Skipped")
        else:
            await interaction.response.send_message("Nothing is playing.")

    @app_commands.command(name="queue", description="Show the current queue")
    async def queue_cmd(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        q = queues.get(guild_id, [])
        if not q:
            return await interaction.response.send_message("The queue is empty.")
        desc = "\n".join([f"{i+1}. {u}" for i, u in enumerate(q)])
        embed = discord.Embed(title="🎵 Music Queue", description=desc, color=0x5865F2)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Show the currently playing song")
    async def nowplaying(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        now = self.current.get(guild_id)
        if not now:
            return await interaction.response.send_message("Nothing is playing.")
        embed = discord.Embed(title="Now Playing 🎶", description=now['title'], color=0x1DB954)
        embed.set_thumbnail(url=now['thumbnail'])
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="stop", description="Stop music and leave voice channel")
    async def stop(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            await vc.disconnect()
            queues[interaction.guild.id] = []
            self.current[interaction.guild.id] = None
            await interaction.response.send_message("🛑 Stopped and left the voice channel.")
        else:
            await interaction.response.send_message("I'm not connected to a voice channel.")

    @app_commands.command(name="volume", description="Set playback volume (0–100%)")
    @app_commands.describe(level="Volume level from 0 to 100")
    async def volume(self, interaction: discord.Interaction, level: int):
        if level < 0 or level > 100:
            return await interaction.response.send_message("❌ Volume must be 0–100.")
        guild_id = interaction.guild.id
        volumes[guild_id] = level / 100.0
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = volumes[guild_id]
        await interaction.response.send_message(f"🔊 Volume set to {level}%")

    @app_commands.command(name="loop", description="Toggle loop mode: off, single, or queue")
    @app_commands.choices(mode=[
        app_commands.Choice(name="off", value="off"),
        app_commands.Choice(name="single", value="single"),
        app_commands.Choice(name="queue", value="queue"),
    ])
    async def loop(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        loops[interaction.guild.id] = mode.value
        await interaction.response.send_message(f"🔁 Loop mode set to {mode.name}")

    @app_commands.command(name="shuffle", description="Shuffle the current queue")
    async def shuffle(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        q = queues.get(guild_id, [])
        if not q:
            return await interaction.response.send_message("The queue is empty.")
        random.shuffle(q)
        await interaction.response.send_message("🔀 Queue shuffled.")

    @app_commands.command(name="clear", description="Clear the current music queue")
    async def clear(self, interaction: discord.Interaction):
        queues[interaction.guild.id] = []
        await interaction.response.send_message("🗑️ Queue cleared.")

    @app_commands.command(name="help", description="List all commands and features")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🎵 Music Bot Commands", description="Here’s what I can do:", color=0x00FFAB)
        cmds = [
            ("/play [name or URL]", "Play a song from YouTube or Spotify"),
            ("/pause", "Pause the current song"),
            ("/resume", "Resume the paused song"),
            ("/skip", "Skip the current song"),
            ("/queue", "Show the current queue"),
            ("/nowplaying", "Show the currently playing song"),
            ("/stop", "Stop music and leave voice channel"),
            ("/volume [0-100]", "Set playback volume"),
            ("/loop [off|single|queue]", "Toggle loop mode"),
            ("/shuffle", "Shuffle the current queue"),
            ("/clear", "Clear the music queue"),
            ("/help", "Show this help message"),
        ]
        for name, desc in cmds:
            embed.add_field(name=name, value=desc, inline=False)
        embed.set_footer(text="Developed with ❤️ by Aimbot")
        await interaction.response.send_message(embed=embed)

@bot.event
async def on_ready():
    bot.add_cog(Music(bot))
    print(f"Logged in as {bot.user}")
    synced = await bot.tree.sync(guild=guild)
    print(f"Synced {len(synced)} commands: {[c.name for c in synced]}")

keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
