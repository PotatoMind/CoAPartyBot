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
        self.player_cache_to_db.start()
        self.player_cache_check.start()
        self.player_db_check.start()

    @tasks.loop(hours=168)
    async def player_cache_to_db(self):
        await self.bot.wait_until_ready()
        print('Saving cache to db')
        for name in self.bot.player_cache.scan_iter('*'):
            name_decoded = name.decode()
            player_info = await self.get_player_from_cache(name)
            player_info = {k.decode(): int(v.decode()) for k, v in player_info.items()}
            player_info['name'] = name_decoded
            await self.set_player_in_db(name_decoded, player_info)
            self.bot.player_cache.delete(name)
        print('Finished saving cache to db')

    @tasks.loop(minutes=30)
    async def check_pages(self):
        await self.bot.wait_until_ready()
        max_pages = {mode: 0 for mode in self.ranking_modes.keys()}

        for mode, resource in self.ranking_modes.items():
            max_pages[mode] = await self.check_pages_helper(resource)

        self.bot.max_page_cache.hmset('max_pages', max_pages)
        print(f'Saved max pages {max_pages}')

    async def check_pages_helper(self, resource):
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
    
    async def level_binary_search(self, level, mode):
        resource = self.ranking_modes[mode]

        low = 0
        high = await self.get_max_page(mode)

        while low <= high: 
            mid = (low + high) // 2

            async with aiohttp.ClientSession() as cs:
                async with cs.get(f'{self.url}/{resource}.json?p={mid}') as r:
                    req = await r.text()
            data = json.loads(req)
            last_level = self.get_level(data[0]['xp'])

            if last_level > level:
                low = mid + 1
            elif last_level < level: 
                high = mid - 1
            else:
                low = mid + 1

        return high
        
    async def get_max_page(self, mode):
        max_pages = self.bot.max_page_cache.hgetall('max_pages')
        if max_pages:
            return int(max_pages[mode.encode()].decode())
        else:
            return await self.check_pages_helper(self.ranking_modes[mode])

    async def get_player_from_cache(self, name):
        name = name.lower()
        return self.bot.player_cache.hgetall(name)

    async def set_player_in_cache(self, name, player_info):
        name = name.lower()
        return self.bot.player_cache.hmset(name, player_info)

    async def get_player_from_db(self, name):
        name = name.lower()
        return self.bot.db.players.find_one({'name': name})

    async def set_player_in_db(self, name, player_info):
        name = name.lower()
        print(name)
        return self.bot.db.players.replace_one({'name': name}, player_info, upsert=True)

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
            player_info = {}
            for mode, data in info.items():
                player_info[mode] = self.get_level(data[1])
            await self.set_player_in_cache(name, player_info)
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

    async def get_player_mode_max_page(self, name, mode):
        # if not found in cache, get from db
        # if cache found, then get level by convert from bytes to int
        # if db found, no conversion necessary
        # if none found, get max page
        max_page = None

        player_levels = await self.get_player_from_cache(name)
        if not player_levels:
            player_levels = await self.get_player_from_db(name)
            if player_levels and mode in player_levels:
                level = player_levels[mode]
                max_page = await self.level_binary_search(level, mode)
        else:
            mode_encoded = mode.encode()
            if mode_encoded in player_levels:
                level = int(player_levels[mode_encoded].decode())
                max_page = await self.level_binary_search(level, mode)

        if not max_page:
            max_page = await self.get_max_page(mode)
        
        return max_page

    async def set_rank_tasks(self, mode, name):
        max_page = await self.get_player_mode_max_page(name, mode)

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
        while req and not found and page <= end_page:
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
            await asyncio.sleep(600)
        return (mode, (info, color))

    def get_level(self, xp):
        level = 0
        while xp >= self.level_table[level]:
            level += 1
        return level

def setup(bot):
    bot.add_cog(Ranking(bot))
    print('Loaded Rankings')
