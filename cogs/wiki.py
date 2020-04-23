import discord
from discord.ext import commands, tasks
import json
import requests
import aiohttp
from urllib.parse import quote 
import textdistance
import itertools

class Wiki(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.url = 'https://www.curseofaros.wiki'
        
    @commands.command()
    async def wiki_search(self, ctx, *, search_term):
        async with aiohttp.ClientSession() as cs:
            async with cs.get(f'{self.url}/api.php?action=opensearch&search={quote(search_term)}&format=json') as r:
                req = await r.json()
        if 'error' in req:
            await ctx.send('Search has broke. Contact the dev.')
        elif len(req[3]) == 0:
            await ctx.send('Could not find that search term.')
        else:
            embed = discord.Embed(
                title=f'Search for {search_term}',
                description='\n\n'.join([link for link in req[3]]),
                color=discord.Color.magenta(),
            )
            await ctx.send(embed=embed)
    
    @commands.command()
    async def wiki_search_fuzzy(self, ctx, *, search_term):
        prefix_page_ranks = await self.wiki_page_prefix_search(search_term)
        substring_page_ranks = await self.wiki_page_substring_search(search_term)
        combined_page_ranks = prefix_page_ranks + substring_page_ranks
        if len(combined_page_ranks) == 0:
            return await ctx.send('Could not find search term!')

        combined_page_ranks.sort(key=lambda x: x[1], reverse=True)
        page_ranks = []
        for g in itertools.groupby(combined_page_ranks, lambda x: x[0]):
            g_list = list(g[1])
            g_list.sort(key=lambda x: x[1], reverse=True)
            page_ranks.append(g_list[0])
        page_ranks.sort(key=lambda x: x[1], reverse=True)

        embed = discord.Embed(
            title=f'Search for {search_term}',
            color=discord.Color.magenta()
        )
        i = 0
        while i < 10 and i < len(page_ranks):
            embed.add_field(
                name=f'{page_ranks[i][0]}, {page_ranks[i][1]:.2}', 
                value=f'{self.url}/wiki/{quote(page_ranks[i][0])}', 
                inline=False
            )
            i += 1
        await ctx.send(embed=embed)
    
    async def wiki_page_prefix_search(self, search_term):
        page_ranks = []
        url_options = f'action=query&list=allpages&aplimit=500&apprefix={search_term.split()[0]}&format=json'
        async with aiohttp.ClientSession() as cs:
            async with cs.get(f'{self.url}/api.php?{url_options}') as r:
                req = await r.json()
        for page in req['query']['allpages']:
            page_ranks.append((page['title'], textdistance.damerau_levenshtein.normalized_similarity(page['title'].lower(), search_term.lower())))
        return page_ranks
    
    async def wiki_page_substring_search(self, search_term):
        tokens = search_term.split()
        page_ranks = []
        for token in tokens:
            url_options = f'action=query&list=search&srlimit=500&srsearch={token}&format=json'
            async with aiohttp.ClientSession() as cs:
                async with cs.get(f'{self.url}/api.php?{url_options}') as r:
                    req = await r.json()
            for page in req['query']['search']:
                page_ranks.append((page['title'], textdistance.damerau_levenshtein.normalized_similarity(page['title'].lower(), search_term.lower())))
        return page_ranks
        
def setup(bot):
    bot.add_cog(Wiki(bot))
    print('Loaded Wiki')