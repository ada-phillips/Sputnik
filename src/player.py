import youtube_dl
import re
import discord
import logging
import os
import asyncio
import functools
import random

log = logging.getLogger(__name__)

LINK_REGEX = re.compile('((http(s)*:[/][/]|www.)([a-z]|[A-Z]|[0-9]|[/.]|[~])*)')

ydl_opts = {
    'format': 'bestaudio/best',
    #'postprocessors': [{
    #    'key': 'FFmpegExtractAudio',
    #}],
    'restrictfilenames': True,
    'noplaylist': True,
    'default_search': 'auto',
    'outtmpl': 'data/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'logger': log.getChild("ytdl"),
}

downloader_loop = asyncio.new_event_loop()

class Player():
    def __init__(self, bot, guildID):
        self.bot = bot
        self.loop = bot.loop
        self.guildID = guildID

        self.volume = float(self.bot.config.get(self.guildID, "Server", "DefaultVolume"))

        #self.ytdl = youtube_dl.YoutubeDL(ydl_opts)

        self.playlist = list()
        self.list_length = 0

        self.now_playing = None
        log.info("Initialized player for %d", guildID)

    def play(self, info):
        log.info("Playing `%s`", info['title'])
        message = info['message']
        
        self.download(info)
        info['filelocation'] = self.bot.ytdl.prepare_filename(info)
        info['message'] = message
        info['start_time'] = self.loop.time()
        self.now_playing = info

        self.bot.get_guild(self.guildID).voice_client.play(
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
        if self.bot.get_guild(self.guildID).voice_client.is_paused():
            log.info("Pausing playback")
            self.bot.get_guild(self.guildID).voice_client.resume()
            self.now_playing['start_time'] = self.now_playing['start_time'] + (self.loop.time() - self.now_playing['pause_time'])

    # Toggle pause
    def pause(self):
        if self.bot.get_guild(self.guildID).voice_client.is_paused():
            log.info("Resuming playback")
            self.bot.get_guild(self.guildID).voice_client.resume()
            self.now_playing['start_time'] = self.now_playing['start_time'] + (self.loop.time() - self.now_playing['pause_time'])
        else:
            log.info("Pausing playback")
            self.bot.get_guild(self.guildID).voice_client.pause()
            self.now_playing['pause_time'] = self.loop.time()
        

    def download(self, info):
        log.info("Downloading `%s`", info['title'])
        self.bot.ytdl.download([info['webpage_url'],])
    
    async def retrieve_info(self, song_url): 
        return await self.loop.run_in_executor(None, functools.partial(self.bot.ytdl.extract_info, song_url, download=False, process=True))

    def after_playing(self, error):
        log.info("Finished playing `%s`", self.now_playing['title'])
        os.remove(self.now_playing['filelocation'])
        self.now_playing = None
        if error:
            log.error(error)
        elif self.playlist:
            self.play(self.playlist.pop(0))

    
    def add(self, info):
        log.info("Adding `%s` to playlist", info['title'])
        self.playlist.append(info)

        if not self.bot.get_guild(self.guildID).voice_client.is_playing():
            self.play(self.playlist.pop(0))

        return len(self.playlist)

    def set_volume(self, volume):
        log.info("Volume set to `%d`", volume)
        self.volume = volume

        if (self.bot.get_guild(self.guildID).voice_client.is_playing()):
            self.bot.get_guild(self.guildID).voice_client.source.volume = self.volume

    def apply_volume(self, source):
        return discord.PCMVolumeTransformer(source, volume=self.volume)

    def shuffle(self):
        random.shuffle(self.playlist)

    def skip(self, author, index=None):
        if (index is None):
            entry = self.now_playing
        else:
            entry = self.playlist[index]
        
        if (entry['message'].author == author):
            if index is None:
                self.bot.get_guild(self.guildID).voice_client.stop()
            else:
                self.playlist.remove(entry)
            return True, 0
        else:
            if 'skips' not in entry:
                entry['skips'] = set()

            entry['skips'].add(author)

            skip_required = min(int(self.bot.config.get(self.guildID, "Server", "SkipsRequired")), int(float(self.bot.config.get(self.guildID, "Server", "SkipRatio")) * (len(self.bot.get_guild(self.guildID).voice_client.channel.members)-1)))
            if len(entry['skips']) >= skip_required:
                log.info("Skipping `%s`", entry['title'])
                if index is None:
                    self.bot.get_guild(self.guildID).voice_client.stop()
                else:
                    self.playlist.remove(entry)
                return True, 0
            else:
                return False, skip_required - len(entry['skips'])



    