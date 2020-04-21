import discord
from discord.ext import commands, tasks
import json
import requests
from urllib.parse import quote 

class Ranking(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.url = 'https://curseofaros.com'
        self.ranking_modes = {
            'xp': 'highscores', 
            'woodcutting': 'highscores-woodcutting',
            'mining': 'highscores-mining',
            'smithing': 'highscores-woodcutting'
        }
        
    @commands.command()
    async def rankings_top(self, ctx, *, mode):
        if mode not in self.ranking_modes:
            await ctx.send(f'Could not find mode.\nAcceptable Modes: {", ".join([m for m in self.ranking_modes.keys()])}')
        resource = self.ranking_modes[mode]
        req = requests.get(f'{url}/{resource}.json?p=0')
        json_data = json.loads(req.text)
        embed = discord.Embed(
            title=f'Top ranks for {mode}',
            description='\n'.join([f'{i+1}. {p["name"]}, {p["xp"]}' for i, p in enumerate(json_data)]),
            color=discord.Color.green(),
        )
        await ctx.send(embed=embed)

def setup(client):
    client.add_cog(Ranking(client))
    print('Loaded Rankings')