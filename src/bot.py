#!/usr/bin/python3
import logging
import asyncio
import sys
import re
import io
import os
import importlib
import traceback

from functools import wraps
from textwrap import dedent
from datetime import datetime

import aiohttp
import discord
import colorlog
import youtube_dl

import pytesseract
from PIL import Image

from config import Config
from suggestions import SuggestionList
import commands
import player

log = logging.getLogger(__name__)

class Bot(discord.Client):
    """
    My name's Sputnik. I'm a bot!
    
    As a bot, I don't really have a gender, or even any sentient thought, so for pronouns I prefer to just stick with 'it' and 'its'.
    I recently moved across the United States, from a server in Ohio to one in South Carolina, but the internet is what I consider my true home.
    
    I'm mostly here to play music and help you roll dice, but my functionality is slowly expanding; Just recently I learned to read, and can help you transcribe images!
    If there's a feature you'd like to see, make sure to let Ada know, or use the `{command_prefix}suggest` command

    You can find my full source code on [GitHub]({github})!
    """

    def __init__(self, config, test=False):
        self.test = test
        self.config = config
        self.players={}

        self.ytdl = youtube_dl.YoutubeDL(player.ydl_opts)

        if test: log.warning("Loading in TEST MODE")

        super().__init__()

        log.info("Initialized Client")

    async def on_ready(self):
        log.info("Connected to Discord. Loading Server Information...")
        try:
            self.suggestions = SuggestionList(
                self.config.get(0, "Trello", "APIKey"), 
                self.config.get(0, "Trello", "APIToken"), 
                None, 
                None,
                self.config.get(0, "Trello", "NewSuggestionList")
            )
        except:
            log.error("Unable to connect to Trello. Suggestions unavailable.")
            self.suggestions = None
        self.config.server_setup(self.guilds)
        self.validate_channels()
        await self.join_channels()
        

    def validate_channels(self):
        for guild in self.guilds:
            if (self.config.get(guild.id, "Server", "BindToChannels")):
                if (isinstance(self.config.get(guild.id, "Server", "BindToChannels"),list)):
                    configuredChannels = self.config.get(guild.id, "Server", "BindToChannels")
                else:
                    configuredChannels = [self.config.get(guild.id, "Server", "BindToChannels"),]

                missingChannels = set(configuredChannels) - set([str(text.id) for text in guild.text_channels])
                if missingChannels:
                    log.warning("Unable to listen to channels not present on %s:\n%s", guild.name, missingChannels)
                    self.config.put(guild.id,"Server","BindToChannels", set(configuredChannels) - missingChannels)
            else:
                log.info("Not bound to any channels on %s; listening to all.", guild.name)
            
            if self.config.get(guild.id,"Server","AutoJoinChannel"):
                missingChannels = self.config.get(guild.id,"Server","AutoJoinChannel") not in [str(voice.id) for voice in guild.voice_channels]
                if missingChannels:
                    log.warning("Unable to auto-join channel not present on %s:\n%s", guild.name, self.config.get(guild.id,"Server","AutoJoinChannel"))
                    
                    self.config.put(guild.id,"Server","AutoJoinChannel", "")
            else:
                log.info("Not auto-joining any channels on %s.", guild.name)
    
    async def join_channels(self):
        for guild in self.guilds:
            if self.config.get(guild.id,"Server","AutoJoinChannel"):
                if guild.voice_client:
                    await guild.voice_client.disconnect()
                await guild.get_channel(int(self.config.get(guild.id,"Server","AutoJoinChannel"))).connect()
                self.players[guild.id] = player.Player(self, guild.id)
            else:   #nothing configd
                continue

    async def on_guild_join(self, guild):
        self.config.server_setup([guild,])
    
    async def on_error(event, *args, **kwargs):
        log.exception("Exception in bot handler")

    async def on_message(self, message):
        await self.wait_until_ready()

        if message.author == self.user:
            return

        if not message.content.startswith(self.config.get((message.guild.id if message.guild else "default"), "Server", "CommandPrefix")):
            if re.match("\\b(rip)\\b", message.content, flags=re.IGNORECASE):
                await message.channel.send(content="Yeah, RIP.")
            return
        
        command = message.content.split(' ', 1)[0][len(self.config.get((message.guild.id if message.guild else "default"), "Server", "CommandPrefix")):].lower()

        handler = getattr(commands, 'cmd_' + command, None)

        if not handler:
            return

        if isinstance(message.channel, discord.DMChannel) and not handler.is_available_everywhere:
            return
        
        if self.config.get((message.guild.id if message.guild else "default"),"Server","BindToChannels") and str(message.channel.id) not in self.config.get((message.guild.id if message.guild else "default"),"Server","BindToChannels") and not hasattr(handler, "is_available_everywhere"):
            return

        try:
            async with message.channel.typing():
                replies = await handler(self, message)
            
            if not isinstance(replies, list):
                replies = [replies,]
            for reply in replies:
                await message.channel.send(content=reply.content, files=reply.files, embed=reply.embed)
        except commands.IncorrectUsageError as e:
            log.exception("Incorrect Usage of %s" % command)
            await message.channel.send(
                content="Incorrect usage of %s:\n```%s```" % (
                    command, 
                    dedent(handler.__doc__.format(command_prefix=self.config.get((message.guild.id if message.guild else "default"), "Server", "CommandPrefix")))
                    )
                )
        except NotImplementedError as e:
            await message.channel.send(content="I'm sorry, that command hasn't been written yet :sob:") 
        except Exception as e:
            await message.channel.send(content="I'm sorry, something went wrong and I couldn't run that command properly. :sob:")
            raise e
        
    def reloadCommandSet(self):
        log.warning("Reloading command set...")
        importlib.reload(commands)

    async def restartBot(self):
        log.warning("Restarting...")
        await self.wait_until_ready()
        for client in self.voice_clients:
            await client.disconnect()
        command = "python" if " " in sys.executable else sys.executable
        log.error("{} - {}".format(sys.executable, [command] + sys.argv))
        os.execv(sys.executable, [command] + sys.argv)

#   Set logging up across all modules
def logging_setup(level="DEBUG"):

    logging.basicConfig(level=level)

    format = "%(asctime)s - %(levelname)s:%(name)s:%(message)s"

    if os.path.isfile("logs/sputnik.log"):
        try:
            log.warning("Renaming old log file ")
            if os.path.isfile("logs/sputnik_old.log"):
                os.remove("logs/sputnik_old.log")
            os.rename("logs/sputnik.log", "logs/sputnik_old.log")
        except:
            log.error("Unable to move old log file. Appending new logs.")

    logfile = logging.FileHandler("logs/sputnik.log",mode='a')
    logfile.setFormatter(logging.Formatter(
        fmt=format
    ))
    logging.getLogger().addHandler(logfile)

# Clean up old songs to limit disk usage
def clean_data():
    log.info("Removing previously downloaded songs.")
    for file in os.listdir('data/'):
        if file != ".gitignore":
            os.remove(os.path.join("data/", file))

if __name__ == "__main__":

    os.chdir(os.path.dirname(os.path.abspath(__file__))+"/..")

    config = Config(test=("--test" in sys.argv))

    logging_setup(level=config.get(0, "Debug", "LogLevel"))
    clean_data()

    boio = Bot(config, test=("--test" in sys.argv))
    
    boio.run(config.get(0, "Credentials", "Token"))
