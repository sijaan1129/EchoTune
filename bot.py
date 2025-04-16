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

GUILD_ID = 123456789012345678  # Replace this with your actual server ID
guild = discord.Object(id=GUILD_ID)

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

queues = {}  # guild_id: [url, url, ...]

YDL_OPTIONS = {
    'format': 'bestaudio',
    'noplaylist': True,
    'cookies': 'cookies.txt',  # Make sure this path is correct
    'quiet': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
}
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1', 'options': '-vn'}

current = {}  # guild_id: {title, thumbnail, url}

async def play_next(interaction, guild_id):
    if queues.get(guild_id):
        next_url = queues[guild_id].pop(0)
        vc = interaction.guild.voice_client
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(next_url, download=False)
            audio_url = info['url']
            title = info.get('title')
            thumbnail = info.get('thumbnail')
            current[guild_id] = {'title': title, 'thumbnail': thumbnail, 'url': next_url}

        vc.play(discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS),
                after=lambda e: asyncio.run_coroutine_threadsafe(play_next(interaction, guild_id), bot.loop))

        embed = discord.Embed(title="Now Playing 🎶", description=title, color=0x1DB954)
        embed.set_thumbnail(url=thumbnail)
        await interaction.channel.send(embed=embed)
    else:
        current[guild_id] = None

@bot.tree.command(name="play", description="Play a song by name or URL (YouTube/Spotify)", guild=guild)
async def play(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    guild_id = interaction.guild.id

    if "spotify.com" in query:
        query = get_spotify_track(query)
    elif not query.startswith("http"):
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]
                query = info['webpage_url']
            except IndexError:
                return await interaction.followup.send("❌ No results found for your search query.")
            except Exception as e:
                print(f"Error during search: {e}")
                return await interaction.followup.send(f"❌ Something went wrong while searching: {e}")

    voice_channel = interaction.user.voice.channel
    if not voice_channel:
        return await interaction.followup.send("You must be in a voice channel!")

    vc = interaction.guild.voice_client
    if not vc:
        vc = await voice_channel.connect()

    if not queues.get(guild_id):
        queues[guild_id] = []

    if not vc.is_playing():
        queues[guild_id].insert(0, query)
        await play_next(interaction, guild_id)
    else:
        queues[guild_id].append(query)
        await interaction.followup.send("Added to queue ✅")

@bot.tree.command(name="pause", description="Pause the current song", guild=guild)
async def pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.pause()
        await interaction.response.send_message("⏸ Paused")
    else:
        await interaction.response.send_message("Nothing is playing.")

@bot.tree.command(name="resume", description="Resume the paused song", guild=guild)
async def resume(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_paused():
        vc.resume()
        await interaction.response.send_message("▶️ Resumed")
    else:
        await interaction.response.send_message("Nothing is paused.")

@bot.tree.command(name="skip", description="Skip the current song", guild=guild)
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.stop()
        await interaction.response.send_message("⏭ Skipped")
    else:
        await interaction.response.send_message("Nothing is playing.")

@bot.tree.command(name="queue", description="Show the current queue", guild=guild)
async def queue_cmd(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    q = queues.get(guild_id, [])
    if not q:
        return await interaction.response.send_message("The queue is empty.")
    desc = "\n".join([f"{idx+1}. {url}" for idx, url in enumerate(q)])
    embed = discord.Embed(title="🎵 Music Queue", description=desc, color=0x5865F2)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="nowplaying", description="Show the currently playing song", guild=guild)
async def nowplaying(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    now = current.get(guild_id)
    if not now:
        return await interaction.response.send_message("Nothing is playing.")
    embed = discord.Embed(title="Now Playing 🎶", description=now['title'], color=0x1DB954)
    embed.set_thumbnail(url=now['thumbnail'])
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stop", description="Stop music and leave voice channel", guild=guild)
async def stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc:
        await vc.disconnect()
        queues[interaction.guild.id] = []
        current[interaction.guild.id] = None
        await interaction.response.send_message("🛑 Stopped and left the voice channel.")
    else:
        await interaction.response.send_message("I'm not connected to a voice channel.")

@bot.tree.command(name="help", description="List all commands and features", guild=guild)
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎵 Music Bot Commands",
        description="Here’s what I can do:",
        color=0x00FFAB
    )

    embed.add_field(name="/play [name or URL]", value="Play a song from YouTube or Spotify", inline=False)
    embed.add_field(name="/pause", value="Pause the current song", inline=False)
    embed.add_field(name="/resume", value="Resume the paused song", inline=False)
    embed.add_field(name="/skip", value="Skip the current song", inline=False)
    embed.add_field(name="/queue", value="Show the current queue", inline=False)
    embed.add_field(name="/nowplaying", value="Show the currently playing song", inline=False)
    embed.add_field(name="/stop", value="Stop music and leave voice channel", inline=False)
    embed.add_field(name="/help", value="Show this help message", inline=False)

    embed.set_footer(text="Developed with ❤️ by Aimbot")
    await interaction.response.send_message(embed=embed)

@bot.event
async def on_ready():
    await bot.wait_until_ready()
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"✅ Synced {len(synced)} commands to guild {GUILD_ID}")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")
    print(f"🤖 Logged in as {bot.user}")

keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
