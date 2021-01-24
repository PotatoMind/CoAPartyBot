import discord
from discord.ext import commands
import aiohttp
from urllib.parse import quote 
import textdistance
import itertools
from bs4 import BeautifulSoup

class Wiki(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.url = 'https://www.curseofaros.wiki'

    @commands.command()
    async def wiki(self, ctx, *, page):
        async with aiohttp.ClientSession() as cs:
            async with cs.get(f'{self.url}/api.php?action=parse&page={quote(page)}&prop=text&formatversion=2&format=json') as r:
                req = await r.json()

        if 'error' in req:
            return await ctx.send('Bad page name. To search using the wiki_search')

        parsed_info = BeautifulSoup(req['parse']['text'], 'html.parser')
        info_table = parsed_info.find('table', attrs={'class':'coa-infobox'})

        if not info_table:
            return await ctx.send('This page is not supported!')

        rows = info_table.find_all('tr')
        embed = discord.Embed(
            title=rows[0].get_text(),
            description=rows[2].get_text(),
            url=f'{self.url}/wiki/{quote(page)}',
            color=discord.Color.blue(),
        )
        image = rows[1].find("img")
        if image:
            embed.set_thumbnail(url=f'{self.url}{image["src"]}')
        first_level_info = parsed_info.find('p')
        if first_level_info:
            embed.add_field(name='Some Info', value=first_level_info.get_text().rstrip())
        await ctx.send(embed=embed)

    @commands.command()
    async def wiki_fuzzy(self, ctx, *, page):
        prefix_page_ranks = await self.wiki_page_prefix_search(page)
        substring_page_ranks = await self.wiki_page_substring_search(page)
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

        top_page = page_ranks[0][0]
        async with aiohttp.ClientSession() as cs:
            async with cs.get(f'{self.url}/api.php?action=parse&page={quote(top_page)}&prop=text&formatversion=2&format=json') as r:
                req = await r.json()

        parsed_info = BeautifulSoup(req['parse']['text'], 'html.parser')
        info_table = parsed_info.find('table', attrs={'class':'coa-infobox'})

        if not info_table:
            return await ctx.send('This page is not supported!')

        rows = info_table.find_all('tr')
        embed = discord.Embed(
            title=rows[0].get_text(),
            description=rows[2].get_text(),
            url=f'{self.url}/wiki/{quote(top_page)}',
            color=discord.Color.green(),
        )
        image = rows[1].find("img")
        if image:
            embed.set_thumbnail(url=f'{self.url}{image["src"]}')
        first_level_info = parsed_info.find('p')
        if first_level_info:
            embed.add_field(name='Some Info', value=first_level_info.get_text().rstrip())
        await ctx.send(embed=embed)

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
                description='\n'.join([f'[{req[1][i]}]({req[3][i]})' for i in range(len(req[3][0:10]))]),
                color=discord.Color.magenta(),
            )
            await ctx.send(embed=embed)

    @commands.command(aliases=['wsf'])
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
            description='\n'.join([f'[{page_rank[0]}]({self.url}/wiki/{quote(page_rank[0])})' for page_rank in page_ranks[0:10]]),
            color=discord.Color.magenta()
        )
        await ctx.send(embed=embed)

    async def wiki_page_prefix_search(self, search_term):
        page_ranks = []
        url_options = f'action=query&list=allpages&aplimit=500&apprefix={search_term.split()[0]}&format=json'
        async with aiohttp.ClientSession() as cs:
            async with cs.get(f'{self.url}/api.php?{url_options}') as r:
                req = await r.json()
        for page in req['query']['allpages']:
            levenstein_distance = textdistance.damerau_levenshtein.normalized_similarity(page['title'].lower(), search_term.lower())
            substr_distance = textdistance.lcsstr.normalized_similarity(page['title'].lower().split(), search_term.lower().split())
            page_ranks.append((page['title'], (levenstein_distance + substr_distance)/2))
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
                levenstein_distance = textdistance.damerau_levenshtein.normalized_similarity(page['title'].lower(), search_term.lower())
                substr_distance = textdistance.lcsstr.normalized_similarity(page['title'].lower().split(), search_term.lower().split())
                page_ranks.append((page['title'], (levenstein_distance + substr_distance)/2))
        return page_ranks

def setup(bot):
    bot.add_cog(Wiki(bot))
    print('Loaded Wiki')
