import logging
import asyncio
import sys
import re
import io
import importlib
import random
import subprocess

from functools import wraps
from textwrap import dedent
from datetime import datetime

import aiohttp
import urllib
import discord
import colorlog

import pytesseract
from PIL import Image

from config import Config
import player

message_builder = {'content':None, 'file':None, 'embed': None}

class Reply:
    def __init__(self, content=None, files=None, embed=None):
        self.content=content
        self.files=files
        self.embed=embed

class IncorrectUsageError(ValueError):
    pass

##################################################################
# Permissions Utilities
##################################################################

async def is_owner(bot, message):
    appInfo = await bot.application_info()
    return message.author == (appInfo.team.owner, appInfo.owner)[appInfo.team is None]

async def is_dev(bot, message):
    appInfo = await bot.application_info()
    return (message.author in appInfo.team.members, False)[appInfo.team is None] or is_owner(bot, message)

async def is_admin(bot, message):
    return  message.channel.permissions_for(message.author).administrator or is_dev(bot, message)


##################################################################
# Command Wrappers
##################################################################

def owner_only(func):
    func.__doc__ +="Only usable by the bot Owner.\n    "
    
    @wraps(func)
    async def wrapper(bot, message, *args, **kwargs):
        allowed = await is_owner(bot, message)

        if allowed:
            return await func(bot, message, *args, **kwargs)
        else:
            return Reply(content="Only the owner can use this command")

    return wrapper

def dev_only(func):
    func.__doc__ +="Only usable by the bot Developers.\n    "
    
    @wraps(func)
    async def wrapper(bot, message, *args, **kwargs):
        allowed = await is_dev(bot, message)

        if allowed:
            return await func(bot, message, *args, **kwargs)
        else:
            return Reply(content="Only members of the dev team can use this command")

    return wrapper

def admin_only(func):
    func.__doc__ +="Only usable by server administrators.\n    "
    
    @wraps(func)
    async def wrapper(bot, message, *args, **kwargs):
        allowed = await is_admin(bot, message)

        if allowed:
            return await func(bot, message, *args, **kwargs)
        else:
            return Reply(content="Only server admins can use this command")

    return wrapper

def available_everywhere(func):
    func.__doc__ +="Usable in every channel, including DMs.\n    "
    func.is_available_everywhere=True
    return func

def mention_invoker(func):
    @wraps(func)
    async def wrapper(bot, message, *args, **kwargs):
        reply = await func(bot, message, *args, **kwargs)
        if isinstance(reply, list):
            first = reply.pop(0)
            first.content = "{}, {}".format(message.author.mention, first.content)
            reply.insert(0, first)
        else:
            reply.content = "{}, {}".format(message.author.mention, reply.content)
        return reply

    return wrapper

def needs_voice(func):
    func.__doc__ +="Only usable while the bot is in a voice channel.\n    "
     
    @wraps(func)
    async def wrapper(bot, message, *args, **kwargs):
        if(message.guild.id in bot.players):
            reply = await func(bot, message, *args, **kwargs)
        else:
            reply = Reply(content="Sorry, this command can't be used when the I'm not in a voice channel")
        return reply
    return wrapper

def needs_listening(func):
    func.__doc__ +="Only usable while in a voice channel with the bot.\n    "

    @wraps(func)
    async def wrapper(bot, message, *args, **kwargs):
        if message.author in message.guild.voice_client.channel.members:
            reply = await func(bot, message, *args, **kwargs)
        else:
            reply = Reply(content="You can only use that command when you're in the voice channel with me.")
        return reply
    return wrapper

##################################################################
# Commands
##################################################################

# Development Commands
#######################
@owner_only
@mention_invoker
@available_everywhere
async def cmd_reloadcmd(bot, msg):
    """
    Usage:
        {command_prefix}reloadcmd

    Reload the command library, pulling in any new changes. Helps with on-going development.
    """

    bot.reloadCommandSet()

    return Reply(content="I've reloaded the command set.")

@owner_only
@available_everywhere
async def cmd_update(bot, msg):
    """
    Usage:
        {command_prefix}update

    Pulls the latest updates from the Sputnik Github repository
    """

    content = "Attempting to pull the most recent updates...\n```\u200b{}```"

    pull = subprocess.check_output(["git","pull"]).decode("utf-8")+" "

    return Reply(content=content.format(pull))

@admin_only
@available_everywhere
async def cmd_introduce(bot, message):
    """
    Usage:
        {command_prefix}introduce

    Prompts me to Introduce myself to the guild.
    """

    embed = discord.Embed(
        title="Hi, I'm Sputnik!", 
        description=dedent(bot.__doc__).format(
            command_prefix=bot.config.get((message.guild.id if message.guild else "default"), "Server", "CommandPrefix"),
            github=bot.config.get(0, "General", "GitHub")
        )
    )
    embed.set_thumbnail(url=bot.user.avatar_url)
    return Reply(embed=embed)

async def cmd_id(bot, message):
    """
    Usage:
        {command_prefix}id [@user]

    Tells the user their id or the id of another user.
    """
    if not message.mentions:
        return Reply(content='your id is `\u200b%s`' % message.author.id)
    else:
        info = ''
        for user in message.mentions:
            info+="%s's id is `\u200b%s`\n" % (user.name, user.id)
        return Reply(content=info)

@dev_only
async def cmd_reboot(bot, message):
    """
    Usage:
        {command_prefix}reboot

    Makes me drop what I'm doing and restart my central processes. 
    Helps if I get stuck on something. 
    """
    await message.channel.send(content="Restarting!")
    await bot.restartBot()

@dev_only
@available_everywhere
async def cmd_except(bot, message):
    """
    Usage:
        {command_prefix}except

    Raises an immediate exception. Useful for debugging. 
    """
    raise Exception()

@owner_only
@available_everywhere
async def cmd_echo(bot, message):
    """
    Usage:
        {command_prefix}echo message

    Echoes a given message.
    """
    echo = message.content.split(" ", 1)[1]

    return Reply(content=echo)

@dev_only
@available_everywhere
async def cmd_logs(bot, message):
    """
    Usage:
        {command_prefix}logs [current|old]

    Displays as many log lines as will fit into a single message, or, if specified, uploads either the current or previous log file. 
    """
    try:
        specify = message.content.split(" ", 1)[1]

        content = "Here's the log file you requested:"
        
        if specify=="current":
            logFile = discord.File(open("logs/sputnik.log", 'rb'))
        elif specify == "old":
            logFile = discord.File(open("logs/sputnik_old.log", 'rb'))

        return Reply(content=content, files=[logFile,])

    except IndexError:
        content = "Here are the last %d lines from the log:\n```\u200b%s```"
        lineCount = 0
        with open("logs/sputnik.log", "r") as f:
            lines = f.readlines()
            lines.reverse()
            logs=""
            for line in lines:
                if len(line)+len(content)+len(logs)<2000:
                    logs=line+logs
                    lineCount+=1
                else:
                    break
        
        content = content % (lineCount, logs)
        return Reply(content=content)

@admin_only
async def cmd_config(bot, message):
    """
    Usage:
        {command_prefix}config
        {command_prefix}config option
        {command_prefix}config option value

    Show all configuration settings for this server,
    Show a given configuration setting for this server, 
    or set a new value for a given configuration setting.
    """

    # try to a first argument, get specific value
    try:
        command, remainder = message.content.split(" ", 1)

        # try to get a second argument, set value
        try:
            key, value = remainder.split(" ", 1)

            content = "Changing {} from `{}\u200b` to `{}\u200b`".format(key, bot.config.get_raw(message.guild.id, "Server", key), value)

            bot.config.put(message.guild.id, "Server", key, value)

            return Reply(content=content)

        # except no second argument, get value
        except ValueError:
            key = remainder

            return Reply(content="Option {} set to `{}\u200b`".format(key, bot.config.get_raw(message.guild.id, "Server", key)))
    
    # except no arguments, give list of configurable options. 
    except ValueError:
            
        embed = discord.Embed(title="**Configuration**", description="Here are the currently configured Sputnik options for this server:\n\n")
        embed.set_footer(text="You can also use this command to update these options! Try {}help config".format(bot.config.get((message.guild.id if message.guild else "default"), "Server", "CommandPrefix")))


        for option in bot.config.get_section(message.guild.id, "Server"):
            embed.add_field(name=option[0], value=(option[1] if not option[1]=="" else "N/A"), inline=False)
        
        return Reply(embed=embed)

# Utility Commands
###################

@available_everywhere
@mention_invoker
async def cmd_read(bot, msg):
    """
    Usage:
        {command_prefix}read

    Attempt to transcribe the text in the most recent image message sent to this channel. Limited to 15 messages of history. 
    """

    async for message in msg.channel.history(limit=15):
        if message.attachments or message.embeds:

            if message.attachments:
                url = message.attachments[0].url
            elif message.embeds[0].image:
                url = message.embeds[0].image.url
            elif message.embeds[0].thumbnail:
                url = message.embeds[0].thumbnail.url
            request = urllib.request.Request(url, headers={"User-Agent": "Sputnik is a good bot, pls let me read this"})
            with urllib.request.urlopen(request) as embed:
                meme = io.BytesIO(embed.read())
                transcript = pytesseract.image_to_string(Image.open(meme), lang="eng+spa+fra+fin")
                
                if transcript: 
                    transcript = transcript.replace('|','I')
                    replies = [Reply(content="I took a look at it, and here's my best guess for what it says:"),]
                    while(len(transcript)>0):
                        chunk, transcript = transcript[:1900], transcript[1900:]
                        replies.append(Reply(content="```\n"+chunk+"```"))
                    return replies
                else: 
                    return Reply(content = "I took a look at it, but I couldn't read any text there, sorry.")
            return Reply(content=content)
    
    return Reply(content="Sorry, I didn't find any images that I could read.")

@available_everywhere
async def cmd_spoiler(bot, message):
    """
    Usage:
        {command_prefix}spoiler [message]
        Message must contain images or embeded images. 

    Re-uploads all images in the invoking message as Spoilers, adding any included text as a description underneath.
    Will delete the invoking message if I have the correct permissions. 
    """

    images = [
        discord.File(
            io.BytesIO(urllib.request.urlopen(
                urllib.request.Request(attachment.url, headers={"User-Agent": "Sputnik is a good bot, pls let me read this"})
            ).read()), 
            filename=attachment.filename, 
            spoiler=True
        )
        for attachment in message.attachments
    ]
    
    if len(images)==0:
        raise IncorrectUsageError
    
    image_message = message.content.split(" ", 1)[1] if len(message.content.split(" ", 1))>1 else discord.Embed.Empty


    embed = discord.Embed(title=discord.Embed.Empty, description=image_message)
    embed.set_author(name=message.author.display_name, icon_url=message.author.avatar_url)

    try:
        await message.delete()
        embed.set_footer(text="Original message deleted.")
    except (discord.Forbidden):
        embed.set_footer(text="Please delete the original message.")

    return Reply(embed=embed, files=images)
    


async def cmd_help(bot, message):
    """
    Usage:
        {command_prefix}help [command]

    Prints a help message.
    If a command is specified, it prints a help message for that command.
    Otherwise, it lists the available commands.
    """

    try:
        command = message.content.split(" ", 1)[1]
        cmd = getattr(sys.modules[__name__], 'cmd_' + command, None)
        if cmd:
            return Reply(
                content= "```\n{}```"
                    .format(dedent(cmd.__doc__))
                    .format(command_prefix=bot.config.get((message.guild.id if message.guild else "default"), "Server", "CommandPrefix"))
            )
        else:
            return Reply(content="No such command")

    except IndexError:
        helpmsg = "**Available commands**\n```"
        commands = []

        for att in dir(sys.modules[__name__]):
            if att.startswith('cmd_') and att != 'cmd_help':
                command_name = att.replace('cmd_', '').lower()
                commands.append("{}{}".format(bot.config.get((message.guild.id if message.guild else "default"), "Server", "CommandPrefix"), command_name))

        helpmsg += ", ".join(commands)
        helpmsg += "```\nYou can also use `{}help x` for more info about each command.".format(bot.config.get((message.guild.id if message.guild else "default"), "Server", "CommandPrefix"))

        return Reply(content=helpmsg)

@mention_invoker
async def cmd_roll(self, message):
    """
    Usage:
        {command_prefix}roll XdY[(+|-|*)Z] [message]

    Used to roll X dice with Y sides, and an optional modifier of Z. A message can also be specified,
    and will be returned alongside the results.
    """

    expression = re.compile('((\d+)([dD])(\d+))(([+*-])((((\d+)([dD])(\d+)|\d+|)([+*-])*)*))?((([^\S\n])*(\w+))*)')

    def quickmath(op, num1, num2):
        if op is "+":
            return num1+num2
        elif op is "-":
            return num1 - num2
        elif op is "*":
            return num1*num2

    def dice(number, sides):
        results = [0] * number
        for i in range(number):
            results[i] = random.randint(1,sides)
        return results

    def roll(argus):
        parse = expression.match(argus)
        total = 0

        if parse:
            rolls = dice(int(parse.group(2)), int(parse.group(4)))
            total = sum(rolls)
            out = parse.group(1)+" ("+", ".join(str(x) for x in rolls) + ") = " + str(total)
            if parse.group(7):
                nex = roll(parse.group(7))
                total = quickmath(parse.group(6),total,nex[1])
                out ="({0}) {1} ({2}) = {3}".format(out, parse.group(6), nex[0], total)
            if parse.group(14):
                out = out + " " + parse.group(14).strip()
        elif argus.isdigit():
            out = "("+argus+") = "+argus
            total = int(argus)
        return out, total

    try:
        args = message.content.split(" ",1)[1]
    except IndexError:
        raise IncorrectUsageError
    
    return Reply(content=roll(args)[0])
cmd_r = cmd_roll

async def cmd_suggestions(bot, message):
    """
    Usage:
        {command_prefix}suggestions

    Lists previous suggestions, as well as their authors.
    """

    embed = discord.Embed(title="**Suggestions**", description="A full view of all suggestions can be found on the [Sputnik Development Trello Board](https://trello.com/b/59hNomms/sputnik-development)\n\n")
    embed.set_footer(text="Have any to add? Try the {}suggest command!".format(bot.config.get((message.guild.id if message.guild else "default"), "Server", "CommandPrefix")))

    for card in bot.suggestions.get_suggestions():
        embed.add_field(name=card.name, value="Suggested {} by {}\u2003\u2003\u2003\u2003Status: {}\nDescription:\n{}\n\u200b".format(card.get_custom_field_by_name("Suggested On").value[:10], card.get_custom_field_by_name("Suggested By").value, card.get_list().name, card.description), inline=True)

    return Reply(embed=embed)

async def cmd_suggest(bot, message): 
    """
    Usage:
        {command_prefix}suggest title
        description

    Used to suggest additional features for Sputnik. All suggestions get added to the Sputnik Trello board, which Ada checks whenever she's doing dev work.
    Before suggesting a new feature, consider using '{command_prefix}suggestions' to make sure it isn't a duplicate.
    """
    try:
        suggestion = message.content.split(" ", 1)[1]
    except IndexError:
        raise IncorrectUsageError

    title = suggestion.split("\n", 1)[0]

    try: 
        description = suggestion.split("\n", 1)[1]
    except IndexError:
        description=""
    
    bot.suggestions.add_suggestion(title, description[:1000], message.author.display_name)

    return Reply(content="Thanks for the suggestion!")

# Fun Commands
###############

@available_everywhere
async def cmd_sayhi(bot, msg):
    """
    Usage:
        {command_prefix}sayhi

    Sends a short message, mostly just for testing purposes. 
    """

    catchPhrases = ["fuck the police", "never cross a picket line", "don't be a scab", "snitches get stiches", "be gay, do crimes", "throw a brick"]

    return Reply(content=random.choice(catchPhrases))

async def cmd_hug(bot, message):
    """
    Usage:
        {command_prefix}hug [@user(s)|@role(s)]

    Sends a virtual hug to the user, or to the specified users or roles.
    """
    hug = [discord.File(open("virtual_hug.gif", 'rb')), ]

    embed_content=""
    content=None
    if message.mentions:
        for user in message.mentions:
            embed_content += ":heart: %s :heart:\n" % user.mention 

    elif message.role_mentions:
        for role in message.role_mentions:
            if role.mentionable:
                embed_content += ":heart: %s :heart:\n" % role.mention
            else: 
                content = "The rules say I'm not allowed to hug %s :cry:\n" % role.mention
                hug = None
                break
    elif message.mention_everyone:
        if is_admin(bot, message):
            embed_content = ":heart: @everyone :heart:"
        else:
            content = "Sorry, but I don't think that's a good idea..."
            hug = None
    else:
        embed_content = ":heart: %s :heart:" % message.author.mention
    
    if content:
        embed = None
    else: 
        embed = discord.Embed(title=discord.Embed.Empty, description=embed_content)
        embed.set_author(name=message.author.display_name, icon_url=message.author.avatar_url)

    return Reply(content=content, embed=embed, files=hug)

@owner_only
@available_everywhere
async def cmd_guillotine(bot, message):
    """
    Usage:
        {command_prefix}guillotine [@user(s)|@role(s)]

    Sends the user, or specified users or roles, to the guillotine. 
    """
    await message.channel.trigger_typing()

    guillotine = [discord.File(open("guillotine.gif", 'rb')), ]

    embed_content=""
    content=None
    if message.mentions:
        for user in message.mentions:
            embed_content += ":skull_crossbones: %s :skull_crossbones:\n" % user.mention 

    elif message.role_mentions:
        for role in message.role_mentions:
            if role.mentionable:
                embed_content += ":skull_crossbones: %s :skull_crossbones:\n" % role.mention
            else: 
                content = "The rules say I'm not allowed to execute %s :cry:\n" % role.mention
                guillotine = None
                break

    else:
        embed_content = ":skull_crossbones: %s :skull_crossbones:" % message.author.mention
    
    if content:
        embed = None
    else: 
        embed = discord.Embed(title=discord.Embed.Empty, description=embed_content)
        embed.set_author(name=message.author.display_name, icon_url=message.author.avatar_url)

    return Reply(content=content, embed=embed, files=guillotine)

# Music Commands
#################

@needs_voice
@needs_listening
async def cmd_play(bot, message):
    """
    Usage:
        {command_prefix}play song_link
        {command_prefix}play text to search for

    Adds the song to the playlist.  If a link is not provided, the first
    result from a youtube search is added to the queue.
    """
    if not message.guild.voice_client:
        return Reply(content="Not currently connected to any voice channels")

    try:
        song_url = message.content.split(' ', 1)[1]
    except IndexError:
        raise IncorrectUsageError

    matchUrl = player.LINK_REGEX.match(song_url)
    if matchUrl is None:
        song_url = song_url.replace('/', '%2F')
    

    #info = bot.ytdl.extract_info(song_url, download=False, process=True)
    info = await bot.players[message.guild.id].retrieve_info(song_url)

    while 'entries' in info:
        if len(info['entries'])>0:
            song_url = info['entries'][0]['webpage_url']
            info = bot.ytdl.extract_info(song_url, download=False, process=True)
        else:
            return Reply(content="Sorry, I didn't find any results.")
    

    if info['duration']>int(bot.config.get(message.guild.id, "Server", "MaxSongLength")):
        return Reply(content="Sorry, that song's too long.")
    
    info['message'] = message

    position = bot.players[message.guild.id].add(info)

    if position>0:
        return Reply(content="Added {} to queue, in position {}".format(info['title'], position))
    else:
        return Reply(content="{}, coming right up!".format(info['title']))

@needs_voice
@needs_listening
async def cmd_pause(bot, message):
    """
    Usage:
        {command_prefix}pause

    Pauses playback of the current song.
    """
    bot.players[message.guild.id].pause()
    return Reply(content="Pausing %s" % bot.players[message.guild.id].now_playing['title'])

@needs_voice
@needs_listening
async def cmd_resume(bot, message):
    """
    Usage:
        {command_prefix}resume

    Resumes playback of a paused song.
    """
    bot.players[message.guild.id].resume()
    return Reply(content="Resuming %s" % bot.players[message.guild.id].now_playing['title'])

@needs_voice
async def cmd_nowplaying(bot, message):
    """
    Usage:
        {command_prefix}np

    Displays the current song in chat.
    """
    if bot.players[message.guild.id].now_playing:

        now_playing = bot.players[message.guild.id].now_playing

        if message.guild.voice_client.is_paused():
            time_elapsed = now_playing['pause_time'] - now_playing['start_time']
        else:
            time_elapsed = bot.players[message.guild.id].loop.time() - now_playing['start_time']


        embed = discord.Embed(title="**Now {}: \n{}**".format("Paused" if message.guild.voice_client.is_paused() else "Playing", now_playing['title']),
            description="[{:02d}:{:02d}/{:02d}:{:02d}]\n{}\n".format(int(time_elapsed/60), int(time_elapsed%60), int(now_playing['duration']/60), int(now_playing['duration']%60), now_playing['webpage_url']))
        embed.set_footer(text="Add songs with the {}play command!".format(bot.config.get((message.guild.id if message.guild else "default"), "Server", "CommandPrefix")))
        embed.set_thumbnail(url=now_playing['thumbnail'])
        return Reply(embed=embed)

    elif len(bot.players[message.guild.id].playlist)>0:
        return Reply(content="Spinnin' up a new track *as we speak*")
    else: 
        return Reply("Nothing playing yet!")
cmd_np = cmd_nowplaying

@needs_voice
@needs_listening
async def cmd_volume(bot, message):
    """
    Usage:
        {command_prefix}volume (+/-)[volume]|up|down

    Sets the playback volume. Accepted values are from 1 to 100.
    Putting + or - before the volume will make the volume change relative to the current volume.
    Using 'up' or 'down' will shift the volume 5% in either direction
    """
    player = bot.players[message.guild.id]
    try:
        vol = message.content.split(" ", 1)[1].lower()

        try:
            volume = float(vol)/100

            if vol.startswith("-") or vol.startswith("+"):
                volume = player.volume + volume

        except ValueError: 
            if vol == "up":
                volume = player.volume+0.05
            elif vol == "down":
                volume = player.volume-0.05
            else: 
                raise IncorrectUsageError
        
        if (volume>1):
            volume = 1
        elif (volume<0):
            volume = 0
        player.set_volume(volume)

        return Reply(content="Volume set to %i%%" % (player.volume*100))

    except IndexError:
        return Reply(content="Volume set to %i%%" % (player.volume*100))

@needs_voice
@needs_listening
async def cmd_skip(bot, message):
    """
    Usage:
        {command_prefix}skip (position in queue)

    Adds a vote to skip either the current song, or a specified song in the queue. 
    """
    player = bot.players[message.guild.id]
    if (player.now_playing):
        try:
            index = int(message.content.split(" ", 1)[1])

            try:    # Try getting the song at that index
                entry = player.playlist[index-1]
                skipped, needed = player.skip(message.author, index=index-1)
                if (skipped):
                    return Reply(content="Skipping {}!".format(entry['title']))
                return Reply(content="Voted to skip {}. {} more votes needed.".format(entry['title'], needed))

            except IndexError:  #if there is no song there,
                return Reply(content="Sorry, {} doesn't correspond to an entry in the queue.".format(index))

        except IndexError:
            skipped, needed = player.skip(message.author)
            if (skipped):
                return Reply(content="Skipping {}!".format(player.now_playing['title']))
            return Reply(content="Voted to skip {}. {} more votes needed.".format(player.now_playing['title'], needed))
    else:
        return Reply(content="Nothing playing!")

@needs_voice
@needs_listening
async def cmd_shuffle(bot, message):
    """
    Usage:
        {command_prefix}shuffle

    Shuffles the song queue.
    """
    player = bot.players[message.guild.id]

    if not (player.playlist):
        return Reply(content="Nothing queued!")

    player.shuffle()

    embed = discord.Embed(title="**Playlist Shuffled!**", description="Here's the new queue:\n\n")
    embed.set_footer(text="Add songs with the {}play command!".format(bot.config.get((message.guild.id if message.guild else "default"), "Server", "CommandPrefix")))

    if player.now_playing:
        info = player.now_playing

        if message.guild.voice_client.is_paused():
            time_elapsed = info['pause_time'] - info['start_time']
        else:
            time_elapsed = bot.players[message.guild.id].loop.time() - info['start_time']
        
        embed.add_field(
            name="Currently {}: {}".format(
                "Paused" if message.guild.voice_client.is_paused() else "Playing", info['title']), 
            value="[{:02d}:{:02d}/{:02d}:{:02d}]\nAdded by {}\n{}\n\u200b".format(
                int(time_elapsed/60), int(time_elapsed%60), int(info['duration']/60), int(info['duration']%60),
                info['message'].author.display_name, 
                info['webpage_url']
                ), 
            inline=False
        )


    if player.playlist:
        for index in range(len(player.playlist)):
            info = player.playlist[index]
            embed.add_field(
                name="{}: {}".format(index+1,info['title']),
                value="[{:02d}:{:02d}]\nAdded by {}\n{}\n\u200b".format(
                    int(info['duration']/60), int(info['duration']%60),
                    info['message'].author.display_name, info['webpage_url']
                    ), 
                inline=False
            )
    
    return Reply(embed=embed)

async def cmd_queue(bot, message):
    """
    Usage:
        {command_prefix}queue

    Prints the current song queue.
    """
    player = bot.players[message.guild.id]

    embed = discord.Embed(title="**Playlist**", description= "Here's what's been queued up so far\n\n" if (player.now_playing or player.playlist) else "Nothing in the queue!")
    embed.set_footer(text="Add songs with the {}play command!".format(bot.config.get((message.guild.id if message.guild else "default"), "Server", "CommandPrefix")))

    if player.now_playing:
        info = player.now_playing

        if message.guild.voice_client.is_paused():
            time_elapsed = info['pause_time'] - info['start_time']
        else:
            time_elapsed = bot.players[message.guild.id].loop.time() - info['start_time']
        
        embed.add_field(
            name="Currently {}: {}".format(
                "Paused" if message.guild.voice_client.is_paused() else "Playing", info['title']), 
            value="[{:02d}:{:02d}/{:02d}:{:02d}]\nAdded by {}\n{}\n\u200b".format(
                int(time_elapsed/60), int(time_elapsed%60), int(info['duration']/60), int(info['duration']%60),
                info['message'].author.display_name, 
                info['webpage_url']
                ), 
            inline=False
        )


    if player.playlist:
        for index in range(len(player.playlist)):
            info = player.playlist[index]
            embed.add_field(
                name="{}: {}".format(index+1,info['title']),
                value="[{:02d}:{:02d}]\nAdded by {}\n{}\n\u200b".format(
                    int(info['duration']/60), int(info['duration']%60),
                    info['message'].author.display_name, info['webpage_url']
                    ), 
                inline=False
            )
    
    return Reply(embed=embed)

@admin_only
async def cmd_summon(bot, message):
    """
    Usage:
        {command_prefix}summon

    Call Sputnik to the summoner's voice channel.
    """

    if not message.author.voice:
        return Reply(content="You need to be in a channel if you expect to be able to summon me there.")
    
    if message.guild.voice_client:
        message.guild.voice_client.stop()
        await message.guild.voice_client.disconnect()

    await message.author.voice.channel.connect()
    if message.guild.id in bot.players:
        bot.players[message.guild.id].playlist = list()
    else:
        bot.players[message.guild.id] = player.Player(bot, message.guild.id)
    
    return Reply(content="I have been summoned!")
