import discord
from discord.ext import commands, tasks
from datetime import datetime
import pkg_resources
import psutil
import random

class Util(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.process = psutil.Process()

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        prefix_info = {
            'guild_id': str(guild.id),
            'prefix': '!?'
        }
        await self.bot.db.prefixes.insert_one(prefix_info)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        await self.bot.db.prefixes.delete_one({'guild_id': str(guild.id)})

    @commands.command()
    async def findmeagf(self, ctx):
        chance = random.random()
        if chance < 0.2:
            await ctx.send('u wish lmao')
        elif chance < 0.4:
            await ctx.send('No matches found lol')
        elif chance < 0.6:
            await ctx.send('I\'ll think about it')
        elif chance < 0.8:
            await ctx.send('It might be possible kekw')
        else:
            await ctx.send('You did it! You found 0.69 matches')

    @commands.command(hidden=True)
    @commands.is_owner()
    async def load(self, ctx, extension):
        self.bot.load_extension(f'cogs.{extension}')

    @commands.command(hidden=True)
    @commands.is_owner()
    async def unload(self, ctx, extension):
        self.bot.unload_extension(f'cogs.{extension}')

    @commands.command(hidden=True)
    @commands.is_owner()
    async def reload(self, ctx, extension):
        self.bot.unload_extension(f'cogs.{extension}')
        self.bot.load_extension(f'cogs.{extension}')

    @commands.command()
    async def ping(self, ctx):
        await ctx.send(f'pong | {round(self.bot.latency * 1000)}ms')

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def change_prefix(self, ctx, prefix):
        await self.bot.db.prefixes.update_one(
            {'guild_id': str(ctx.guild.id)},
            {'$set': {'prefix': prefix}}
        )
        await ctx.send(f'Changed prefix to {prefix}')

    @commands.command()
    async def get_prefix(self, ctx):
        prefix = await self.bot.db.prefixes.find_one({'guild_id': str(ctx.guild.id)})['prefix']
        await ctx.send(f'Prefix: {prefix}')

    @commands.command()
    async def about(self, ctx):
        embed = discord.Embed(
            title='Official Bot Server Invite',
            url='https://discord.gg/FdkUxzF',
            color = discord.Color.purple()
        )

        owner = await self.bot.fetch_user(self.bot.owner_id)
        embed.set_author(name=str(owner), icon_url=owner.avatar_url)

        total_members = 0
        total_online = 0
        offline = discord.Status.offline
        for member in self.bot.get_all_members():
            total_members += 1
            if member.status is not offline:
                total_online += 1

        total_unique = len(self.bot.users)

        text = 0
        voice = 0
        guilds = 0
        for guild in self.bot.guilds:
            guilds += 1
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel):
                    text += 1
                elif isinstance(channel, discord.VoiceChannel):
                    voice += 1

        embed.add_field(name='Members', value=f'{total_members} total\n{total_unique} unique\n{total_online} unique online')
        embed.add_field(name='Channels', value=f'{text + voice} total\n{text} text\n{voice} voice')

        memory_usage = self.process.memory_full_info().uss / 1024**2
        cpu_usage = self.process.cpu_percent() / psutil.cpu_count()
        embed.add_field(name='Process', value=f'{memory_usage:.2f} MiB\n{cpu_usage:.2f}% CPU')

        version = pkg_resources.get_distribution('discord.py').version
        embed.add_field(name='Guilds', value=guilds)
        days, hours, minutes, seconds = self.get_bot_uptime()
        embed.add_field(name='Uptime', value=f'{days}d, {hours}h, {minutes}m, {seconds}s')
        embed.set_footer(text=f'Made with discord.py v{version}', icon_url='http://i.imgur.com/5BFecvA.png')
        embed.timestamp = datetime.utcnow()
        await ctx.send(embed=embed)

    @commands.command()
    async def uptime(self, ctx):
        days, hours, minutes, seconds = self.get_bot_uptime()
        await ctx.send(f'{days}d, {hours}h, {minutes}m, {seconds}s')

    def get_bot_uptime(self):
        delta_uptime = datetime.utcnow() - self.bot.launch_time
        hours, remainder = divmod(int(delta_uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        return days, hours, minutes, seconds

def setup(bot):
    bot.add_cog(Util(bot))
    print('Loaded Utils')
