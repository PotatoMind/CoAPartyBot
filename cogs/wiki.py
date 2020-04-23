import discord
from discord.ext import commands, tasks
import json
import requests
from urllib.parse import quote 

class Wiki(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.command()
    async def wiki_search(self, ctx, *, search_term):
        req = requests.get(f'https://www.curseofaros.wiki/api.php?action=opensearch&search={quote(search_term)}&format=json')
        json_data = json.loads(req.text)
        if 'error' in json_data:
            await ctx.send('Search has broke. Contact the dev.')
        elif len(json_data[3]) == 0:
            await ctx.send('Could not find that search term.')
        else:
            embed = discord.Embed(
                title=f'Search for {search_term}',
                description='\n'.join([link for link in json_data[3]]),
                color=discord.Color.magenta(),
            )
            await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Wiki(bot))
    print('Loaded Wiki')