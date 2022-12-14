import discord
import pytz
import asyncio
from datetime import datetime, timedelta
import ext.server as server
from discord.ext import commands, tasks
from discord.commands import SlashCommandGroup
from ext.perdition import Perdition

restart_interval = 6 # in hours
first_restart = 1 # hour
warnings = [30, 15, 10, 5, 3, 1] # in minutes
server_tz = pytz.timezone('Europe/London')

def get_server_time():
    utc_time = pytz.utc.localize(datetime.utcnow())
    return server_tz.normalize(utc_time.astimezone(server_tz))

def is_dst():
    return get_server_time().astimezone(server_tz).dst() != timedelta(0)

def get_restart():
    now = get_server_time()
    dst = int(is_dst())
    delta = (now.hour - int(not dst)) // 6
    next_restart = server_tz.normalize(datetime(now.year, now.month, now.day, hour=first_restart - dst, tzinfo=now.tzinfo))
    if now.hour >= 1:
        next_restart += timedelta(hours=restart_interval * delta + restart_interval + dst)
    return next_restart, next_restart - now.replace(second=0, microsecond=0)

async def get_players():
    response = None
    lines = response.splitlines()
    names = [name[1:] for name in lines[1:]]
    players = []
    for member in Perdition.server.members:
        name = member.display_name.split('|')[0].strip()
        if name.lower() in [lname.lower() for lname in names]:
            players.append((name, member))
    return players

async def online_embed(member: discord.Member):
    embed = discord.Embed(color=member.top_role.color)
    embed.set_author(name=member.display_name.split('|')[0].strip(), icon_url=member.display_avatar)
    return embed

listing = {}
async def create_listing():
    chan: discord.TextChannel = Perdition.channels["player list"]
    try:
        players = await get_players()
    except Exception as e:
        print("Couldn't get players\n",e)
        return
    print([name for name, member in players])
    print(list(listing.keys()))
    if [name for name, member in players] != list(listing.keys()):
        woosh = list(listing.items())
        for name, msg in woosh:
            print(name)
            if name not in [name for name, member in players]:
                await msg.delete()
                del listing[name]
    for name, member in players:
        if name not in listing.keys():
            msg = await chan.send(embed=await online_embed(member))
            listing.update({name : msg})

class ServerManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.restart_manager.start()

    srv = SlashCommandGroup("server", "server control commands")

    @srv.command()
    async def restart(self, ctx: discord.ApplicationContext):
        await ctx.defer()
        await server.restart()
        await ctx.respond("Server is restarting")

    @srv.command()
    async def message(self, ctx: discord.ApplicationContext, msg: str):
        await ctx.defer()
        server.message(msg)
        await ctx.respond('Message sent!', ephemeral=True)

    @tasks.loop(minutes=1)
    async def restart_manager(self):
        next_restart, until = get_restart()
        for time in warnings:
            if until.seconds == time * 60:
                server.message(f"The server will restart in {time * 60} minutes")
                break
        if until.seconds == warnings[0] * 60.0:
            print(until.seconds)
            await Perdition.channels["restart warnings"].send(f"**Server restart <t:{int(next_restart.timestamp())}:R>!**")
        if until.seconds <= warnings[-1] * 60:
            await asyncio.sleep(until.seconds)
            await server.restart()


    @restart_manager.before_loop
    async def before_warning(self):
        await self.bot.wait_until_ready()
        #chan: discord.TextChannel = Perdition.channels["player list"]
        #await chan.purge() # clean player list channel
        now = get_server_time()
        future = now.replace(microsecond=0) + timedelta(seconds=1)
        until = future - now.replace(microsecond=0)
        print('Sleeping for', until.total_seconds(), 'seconds')
        await asyncio.sleep(until.total_seconds())
def setup(bot):
    bot.add_cog(ServerManagement(bot))
