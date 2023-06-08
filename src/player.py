import yt_dlp
import re
import discord
import logging
import os
import asyncio
import functools
import random
import math
import threading

log = logging.getLogger(__name__)

LINK_REGEX = re.compile('((http(s)*:[/][/]|www.)([a-z]|[A-Z]|[0-9]|[/.]|[~])*)')

ydl_opts = {
    'format': 'worstaudio/worst',
    #'postprocessors': [{
    #    'key': 'FFmpegExtractAudio',
    #}],
    'source_address': '0.0.0.0',
    'restrictfilenames': True,
    'noplaylist': True,
    'default_search': 'auto',
    'outtmpl': 'data/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'logger': log.getChild("ytdl"),
}

downloader_loop = asyncio.new_event_loop()

class Player():
    def __init__(self, bot, guild):
        self.bot = bot
        self.loop = bot.loop
        self.guild = guild
        self.play_lock = threading.Lock()

        self.volume = float(self.bot.config.get(self.guild.id, "Server", "DefaultVolume"))

        self.playlist = list()

        self.now_playing = None
        log.info("Initialized player for %s", self.guild)

    async def play(self, info):
        with self.play_lock:
            log.info("Playing `%s` on %s", info['title'], self.guild)
            message = info['message']
            
            self.now_playing = info
            await self.download(info)
            info['filelocation'] = self.bot.ytdl.prepare_filename(info)
            info['message'] = message
            info['start_time'] = self.loop.time()

            self.guild.voice_client.play(
                self.apply_volume(discord.FFmpegPCMAudio(info['filelocation'])),
                after = self.after_playing
            )

            embed = discord.Embed(title="**Your song {} is now Playing!**".format(info['title']),
                description="[{:02d}:{:02d}]\n{}\n".format(int(info['duration']/60), int(info['duration']%60), info['webpage_url']))
            embed.set_footer(text="Add more songs with the {}play command!".format(self.bot.config.get((message.guild.id if message.guild else "default"), "Server", "CommandPrefix")))
            embed.set_thumbnail(url=info['thumbnail'])

            self.loop.create_task(message.channel.send(embed=embed, content=message.author.mention))

    #resume
    def resume(self):
        if self.guild.voice_client.is_paused():
            log.info("Pausing playback on %s", self.guild)
            self.guild.voice_client.resume()
            self.now_playing['start_time'] = self.now_playing['start_time'] + (self.loop.time() - self.now_playing['pause_time'])

    # Toggle pause
    def pause(self):
        if self.guild.voice_client.is_paused():
            log.info("Resuming playback on %s", self.guild)
            self.guild.voice_client.resume()
            self.now_playing['start_time'] = self.now_playing['start_time'] + (self.loop.time() - self.now_playing['pause_time'])
        else:
            log.info("Pausing playback on %s", self.guild)
            self.guild.voice_client.pause()
            self.now_playing['pause_time'] = self.loop.time()
        

    async def download(self, info):
        log.info("Downloading `%s` for %s", info['title'], self.guild)
        await self.loop.run_in_executor(None, self.bot.ytdl.download, [info['webpage_url'],])
    
    async def retrieve_info(self, song_url): 
        return await self.loop.run_in_executor(None, functools.partial(self.bot.ytdl.extract_info, song_url, download=False, process=True))

    def after_playing(self, error):
        log.info("Finished playing `%s` on %s", self.now_playing['title'], self.guild)
        os.remove(self.now_playing['filelocation'])
        self.now_playing = None
        if error:
            log.error(error)
        elif self.playlist:
            self.loop.create_task(self.play(self.playlist.pop(0)))

    
    def add(self, info):
        log.info("Adding `%s` to playlist on %s", info['title'], self.guild)
        self.playlist.append(info)

        if not self.guild.voice_client.is_playing() and not self.play_lock.locked():
            self.loop.create_task(self.play(self.playlist.pop(0)))

        return len(self.playlist)

    def set_volume(self, volume):
        log.info("Volume set to `%d` on %s", volume, self.guild)
        self.volume = volume

        if (self.guild.voice_client.is_playing()):
            self.guild.voice_client.source.volume = self.volume

    def apply_volume(self, source):
        return discord.PCMVolumeTransformer(source, volume=self.volume)

    def shuffle(self):
        random.shuffle(self.playlist)

    def clear_playlist(self):
        log.info("Clearing playlist on %s", self.guild)
        self.playlist = list()
        self.guild.voice_client.stop()
    
    def skips_required(self):
        skip_count = int(self.bot.config.get(self.guild.id, "Server", "SkipsRequired"))
        skip_ratio = float(self.bot.config.get(self.guild.id, "Server", "SkipRatio"))
        users = float(len(self.guild.voice_client.channel.members)-1)

        return min(skip_count, math.ceil(skip_count*users))

    def skip(self, author, index=None):
        if (index is None):
            if self.now_playing:
                entry = self.now_playing
            else:
                return -1
        else:
            entry = self.playlist[index]

        if 'skips' not in entry:
            entry['skips'] = set()

        entry['skips'].add(author)

        req = self.skips_required()
        if len(entry['skips']) >= req or (entry['message'].author == author):
            log.info("Skipping `%s` on %s", entry['title'], self.guild)
            if index is None:
                self.guild.voice_client.stop()
            else:
                self.playlist.remove(entry)
            return 0
        else:
            return req - len(entry['skips'])



    