import discord
from discord.ext import commands, tasks
import json
from urllib.parse import quote
import aiohttp
import sys
from prettytable import PrettyTable
import asyncio
import time
import math
import datetime
import pymongo

class Ranking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.url = 'https://curseofaros.com'
        self.ranking_modes = {
            'xp': 'highscores',
            'mining': 'highscores-mining',
            'smithing': 'highscores-smithing',
            'woodcutting': 'highscores-woodcutting',
            'crafting': 'highscores-crafting',
            'fishing': 'highscores-fishing',
	        'cooking': 'highscores-cooking'
        }
        self.level_table = [
            0, 46, 99, 159, 229,
            309, 401, 507, 628, 768,
            928, 1112, 1324, 1567, 1847,
            2168, 2537, 2961, 3448, 4008,
            4651, 5389, 6237, 7212, 8332,
            9618, 11095, 12792, 14742, 16982,
            19555, 22510, 25905, 29805, 34285,
            39431, 45342, 52132, 59932, 68892,
            79184, 91006, 104586, 120186, 138106,
            158690, 182335, 209496, 240696, 276536,
            317705, 364996, 419319, 481720, 553400,
            635738, 730320, 838966, 963768, 1107128,
            1271805, 1460969, 1678262, 1927866, 2214586,
            2543940, 2922269, 3356855, 3856063, 4429503,
            5088212, 5844870, 6714042, 7712459, 8859339,
            10176758, 11690075, 13428420, 15425254, 17719014,
            20353852, 23380486, 26857176, 30850844, 35438364,
            40708040, 46761308, 53714688, 61702024, 70877064,
            81416417, 93522954, 107429714, 123404386, 141754466,
            162833172, 187046247, 214859767, 246809111, 283509271,
            325666684, 374092835, 429719875, 493618564, 567018884,
            651333710, 748186012, 859440093, 987237472, 1134038112,
            1302667765, 1496372370, 1718880532, 1974475291, 2268076571,
            2605335878, 2992745089, 3437761413, 3948950932, 4536153492,
            5210672106, sys.maxsize
        ]
        self.page_bins = 4
        self.check_pages.start()
        self.get_player_info.start()

    @tasks.loop(hours=24)
    async def get_player_info(self):
        await self.bot.wait_until_ready()
        curr_time = datetime.datetime.now().isoformat()
        with open('rankings.json', 'r') as f:
            config = json.load(f)
        for mode, resource in self.ranking_modes.items():
            page = 0
            max_page = config['max_pages'][mode]
            async with aiohttp.ClientSession() as cs:
                async with cs.get(f'{self.url}/{resource}.json?p={page}') as r:
                    req = await r.text()
            while page < max_page:
                if page % 499 == 0:
                    print(f'Progress for get_levels of {mode}: {page}')
                json_data = json.loads(req)
                for person in json_data:
                    xp = person['xp']
                    level = self.get_level(xp)
                    name = person['name']
                    player_info = self.bot.db.players.find_one({'name': name})
                    if not player_info:
                        player_info = {}
                        player_info['name'] = name
                        for mode in self.ranking_modes.keys():
                            player_info[f'{mode}_xp'] = 0
                            player_info[f'{mode}_level'] = 1
                        player_info['total_xp'] = 0
                        player_info['total_levels'] = len(self.ranking_modes)
                    player_info['last_update'] = curr_time
                    player_info['total_xp'] = (player_info['total_xp'] - player_info[f'{mode}_xp']) + xp
                    player_info['total_levels'] = (player_info['total_levels'] - player_info[f'{mode}_level']) + level
                    player_info[f'{mode}_xp'] = xp
                    player_info[f'{mode}_level'] = level
                    self.bot.db.players.replace_one({'name': name}, player_info, upsert=True)
                page += 1
                async with aiohttp.ClientSession() as cs:
                    async with cs.get(f'{self.url}/{resource}.json?p={page}') as r:
                        req = await r.text()

    @tasks.loop(minutes=10)
    async def check_pages(self):
        await self.bot.wait_until_ready()
        page_numbers = {mode: 0 for mode in self.ranking_modes.keys()}

        for mode, resource in self.ranking_modes.items():
            page_numbers[mode] = await self.get_max_page(resource)

        with open('rankings.json', 'r') as f:
            config = json.load(f)
        config['max_pages'] = page_numbers
        with open('rankings.json', 'w') as f:
            json.dump(config, f)

    async def get_max_page(self, resource):
        index_1 = 1
        index_2 = 1
        async with aiohttp.ClientSession() as cs:
            async with cs.get(f'{self.url}/{resource}.json?p={index_1}') as r:
                req = await r.text()

        while req and len(json.loads(req)) != 0:
            index_2 = index_1
            index_1 = index_1 * 2
            async with aiohttp.ClientSession() as cs:
                async with cs.get(f'{self.url}/{resource}.json?p={index_1}') as r:
                    req = await r.text()

        mid = 0
        while index_1 != index_2:
            mid = index_1 + (index_2 - index_1) // 2
            async with aiohttp.ClientSession() as cs:
                async with cs.get(f'{self.url}/{resource}.json?p={mid}') as r:
                    req = await r.text()
            if req and len(json.loads(req)) != 0:
                index_2 = mid + 1
            else:
                index_1 = mid

        return index_1 - 1

    @commands.command()
    async def rankings(self, ctx, mode='xp', page='1'):
        if mode not in self.ranking_modes:
            await ctx.send(f'Could not find mode.\nAcceptable Modes: {", ".join([m for m in self.ranking_modes.keys()])}')
        else:
            resource = self.ranking_modes[mode]
            async with aiohttp.ClientSession() as cs:
                async with cs.get(f'{self.url}/{resource}.json?p={int(page)-1}') as r:
                    req = await r.text()
            if not req:
                return await ctx.send(f'Ran out of pages!')
            json_data = json.loads(req)

            table = PrettyTable()
            table.field_names = ['Rank', 'Name', 'Level', 'XP']
            for i, p in enumerate(json_data):
                table.add_row([20*(int(page)-1)+i+1, p['name'], self.get_level(p['xp']), f"{p['xp']:,}"])

            with open('rankings.json', 'r') as f:
                config = json.load(f)
            max_page = config['max_pages'].get(mode, 'NA')
            await ctx.send(f'```diff\n{table}\n*** Page {page} / {max_page} ***\n```')

    @commands.command()
    async def rankings_total(self, ctx, _type='xp', start=1, end=20):
        if _type != 'xp' and _type != 'levels':
            await ctx.send('Could not find type.\nAcceptable types: xp, levels')
        elif start < 1 or start >= end or end - start + 1 > 50:
            await ctx.send('Bad index range. Make sure start < end, both are positive values, and the range is < 50')
        else:
            player_infos = self.bot.db.players.find().sort(f'total_{_type}', pymongo.DESCENDING)[start-1:end+1]
            table = PrettyTable()
            table.field_names = ['Rank', 'Name', _type.upper()]
            for i, p in enumerate(player_infos):
                total = p[f'total_{_type}']
                table.add_row([i+start, p['name'], f'{total:,}'])

            await ctx.send(f'```diff\n{table}\n```')
    
    @commands.command(aliases=['rsearch', 'rs', 'rankingss'])
    async def rankings_search(self, ctx, *, name=None):
        return await self.rank_search_helper(ctx, [mode for mode in self.ranking_modes.keys()], name)

    @commands.command(aliases=['rsm', 'rmode'])
    async def rankings_search_mode(self, ctx, mode=None, *, name=None):
        if not mode or mode not in self.ranking_modes:
            await ctx.send(f'Could not find mode.\nAcceptable Modes: {", ".join([m for m in self.ranking_modes.keys()])}')
        else:
            return await self.rank_search_helper(ctx, [mode], name)

    async def rank_search_helper(self, ctx, modes, name):
        if not name:
            name = await self.get_author_name(str(ctx.author.id))
            if not name:
                return await ctx.send('User not linked!')

        if len(name) < 3 or len(name) > 14:
            return await ctx.send('Invalid name!')

        name = name.lower()
        rank_mode_sub = [mode for mode in self.ranking_modes.keys() if mode in modes]
        info = {}
        color = None
        found_name = None
        futures = [self.set_rank_tasks(mode, name) for mode in rank_mode_sub]
        start_time = time.time()
        done, _ = await asyncio.wait(futures)
        end_time = time.time() - start_time
        for task in done:
            player_ranks = task.result()
            sub_info, temp_color = player_ranks[1]
            if not color and temp_color:
                color = temp_color
            if not found_name and sub_info:
                found_name = sub_info[2]
            info[player_ranks[0]] = sub_info
        if found_name:
            embed = discord.Embed(
                title=f'Rank Info for {found_name}',
                color=discord.Color(int(f'0x{color}', 16))
            )
            total_levels = 0
            total_exp = 0
            for mode in self.ranking_modes.keys():
                if mode in info and info[mode]:
                    data = info[mode]
                    total_exp += data[1]
                    total_levels += self.get_level(data[1])
                    embed.add_field(name=mode, value=f'#{data[0]} (LV. {self.get_level(data[1])}) {data[1]:,} XP', inline=False)
            embed.set_footer(text=f'T: {end_time:.1f}s | Levels: {total_levels:,} | XP: {total_exp:,}')
            await ctx.send(embed=embed)
        else:
            await ctx.send('Player rank info not found!')


    @commands.command(aliases=['rl'])
    async def rankings_link(self, ctx, *, name):
        if len(name) < 3 or len(name) > 14:
            return await ctx.send('Invalid name!')

        with open('rankings.json', 'r') as f:
            config = json.load(f)

        config['users'][str(ctx.author.id)] = name

        with open('rankings.json', 'w') as f:
            json.dump(config, f)

        await ctx.send('Linked account!')

    @commands.command(aliases=['rul'])
    async def rankings_unlink(self, ctx):
        with open('rankings.json', 'r') as f:
            config = json.load(f)

        found = config['users'].pop(str(ctx.author.id), None)
        if not found:
            return await ctx.send('Account not found!')

        with open('rankings.json', 'w') as f:
            json.dump(config, f)

        await ctx.send('Unlinked account!')

    async def get_author_name(self, id):
        with open('rankings.json', 'r') as f:
            config = json.load(f)

        return config['users'].get(id, None)

    async def set_rank_tasks(self, mode, name):
        resource = self.ranking_modes[mode]
        max_page = await self.get_max_page(resource)
        split = math.ceil(max_page / self.page_bins)
        tasks = []
        i = 0
        while i < max_page:
            temp = i + split
            mid = (temp + i) // 2
            tasks.append(self.get_rank_info(mode, name, i, max_page if temp > max_page else mid))
            tasks.append(self.get_rank_info(mode, name, -max_page if temp > max_page else -temp, -mid))
            i = temp
        done = None
        if tasks:
            done, pending = await asyncio.wait(tasks, timeout=600, return_when=asyncio.FIRST_COMPLETED)
            [p.cancel() for p in pending]
        if done:
            return done.pop().result()
        else:
            return (mode, (None, None))

    async def get_rank_info(self, mode, name, start_page=0, end_page=sys.maxsize):
        info = None
        color = None
        resource = self.ranking_modes[mode]
        found = False
        async with aiohttp.ClientSession() as cs:
            async with cs.get(f'{self.url}/{resource}.json?p={abs(start_page)}') as r:
                req = await r.text()
        page = start_page
        while req and not found and page < end_page:
            j = 0
            json_data = json.loads(req)
            while j < len(json_data) and not found:
                player = json_data[j]
                if player['name'].lower() == name:
                    found = True
                    rank = abs(page) * 20 + j + 1
                    info = (rank, player['xp'], player['name'])
                    color = player['name_color'] if player['name_color'] else '99aab5'
                else:
                    j += 1
            page += 1
            async with aiohttp.ClientSession() as cs:
                async with cs.get(f'{self.url}/{resource}.json?p={abs(page)}') as r:
                    req = await r.text()

        if not found:
            print(mode, name, start_page, end_page)
            await asyncio.sleep(600)
        return (mode, (info, color))

    def get_level(self, xp):
        level = 0
        while xp >= self.level_table[level]:
            level += 1
        return level

    async def save_to_db(self, name, info):
        self.db.players.update_one({'name': name}, {'$set': info})

    async def get_from_db(self, name):
        return self.db.players.find_one({'name': name})

def setup(bot):
    bot.add_cog(Ranking(bot))
    print('Loaded Rankings')
