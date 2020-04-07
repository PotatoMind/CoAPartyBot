import discord
from discord.ext import commands, tasks
from itertools import cycle
import json

class Util(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.statuses = cycle(['eat the potato', 'bake the potato', 'sleep with potato', 'kill the potato'])
    
    @commands.Cog.listener()
    async def on_ready(self):
        self.change_status.start()
        print('Bot is ready')
    
    @tasks.loop(hours=1)
    async def change_status(self):
        await self.client.change_presence(activity=discord.Game(next(self.statuses)))

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        config[str(guild.id)] = {'prefix': '!'}

        with open('config.json', 'w') as f:
            json.dump(config, f)
    
    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        config.pop(str(guild.id))

        with open('config.json', 'w') as f:
            json.dump(config, f)
        
    
    @commands.command()
    async def ping(self, ctx):
        await ctx.send(f'pong | {round(self.client.latency * 1000)}ms')

    @commands.command()
    async def change_prefix(self, ctx, prefix):
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        config[str(ctx.guild.id)]['prefix'] = prefix

        with open('config.json', 'w') as f:
            json.dump(config, f)
        
        await ctx.send(f'Changed prefix to "{prefix}"')

def setup(client):
    client.add_cog(Util(client))
    print('Loaded Utils')