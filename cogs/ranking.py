from datetime import datetime, timedelta
import discord
from discord.ext import commands, tasks
import aiohttp
from aiohttp import ClientOSError
import sys
import os
import asyncio
import time
import math
import pymongo
import DiscordUtils
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


class Ranking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.url = 'https://curseofaros.com'
        self.lone_wolf_tag = 'lw'
        self.ranking_modes = {
            'melee': 'highscores-melee',
            'magic': 'highscores-magic',
            'mining': 'highscores-mining',
            'smithing': 'highscores-smithing',
            'woodcutting': 'highscores-woodcutting',
            'crafting': 'highscores-crafting',
            'fishing': 'highscores-fishing',
            'cooking': 'highscores-cooking',
            'tailoring': 'highscores-tailoring'
        }
        self.ranking_modes_2 = {
            'melee': 100,
            'magic': 101,
            'mining': 0,
            'smithing': 1,
            'woodcutting': 2,
            'crafting': 3,
            'fishing': 4,
            'cooking': 5,
            'tailoring': 7
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
        self.max_db_pages = 1000
        self.items_per_page = 10
        self.total_connection_retries = 5
        self.lock = asyncio.Lock()
        self.player_lock = asyncio.Lock()
        self.session = aiohttp.ClientSession()
        self.blacklist_file = 'blacklist.txt'
        self.tracking_change_min_xp = 10000
        self.tracking_days_after_removal_check = 30
        self.check_pages.start()
        self.clear_old_cache.start()
        self.leaderboards_to_db.start()
        self.tracked_players_to_db.start()

    @tasks.loop(minutes=1)
    async def tracked_players_to_db(self):
        await self.bot.wait_until_ready()
        tracked_players = await self.get_list_of_tracked_players()
        for tracked_player in tracked_players:
            tracked_player_id = tracked_player['id']
            player_info = await self.get_page_info(f'{self.bot.leaderboards_api_url}/players/id/{tracked_player_id}')
            if not player_info:
                tracked_player['track'] = False
                await self.bot.db.tracked_players.replace_one({'id': tracked_player_id}, tracked_player)
            else:
                await self.tracked_player_to_db(tracked_player, player_info)

    async def tracked_player_to_db(self, tracked_player, player_info):
        tracked_player_id = tracked_player['id']
        player_name = player_info['name']
        new_record = {'name': player_name, 'created': datetime.utcnow()}
        total_xp = 0
        for mode, i in self.ranking_modes_2.items():
            rank = await self.get_page_info(f'{self.bot.leaderboards_api_url}/players/rank/{tracked_player_id}/{i}')
            mode_xp_tag = f'{mode}_xp'
            mode_xp = player_info[mode_xp_tag]
            new_record[mode_xp_tag] = mode_xp
            new_record[f'{mode}_rank'] = rank
            total_xp += mode_xp
        tracked_player['total_xp'] = total_xp
        tracked_player['name'] = player_name
        tracked_player['name_lowered'] = player_name.lower()
        tracked_player['records'].insert(0, new_record)
        await self.bot.db.tracked_players.replace_one({'id': tracked_player_id}, tracked_player, upsert=True)

    async def get_list_of_tracked_players(self):
        tracked_players = []
        curr_time = datetime.utcnow()

        # assumes records are sorted by date descending
        async for tracked_player in self.bot.db.tracked_players.find({'track': True}):
            player_id = tracked_player['id']
            last_checked = tracked_player['last_checked']
            if last_checked + timedelta(days=self.tracking_days_after_removal_check) < curr_time:
                records = tracked_player['records']
                i = 0
                while i < len(records) - 1 and records[i]['created'] > last_checked:
                    i += 1

                total_prev_xp = 0
                found_record = records[i]
                for mode in self.ranking_modes_2.keys():
                    total_prev_xp += found_record[f'{mode}_xp']

                xp_change = abs(tracked_player['total_xp'] - total_prev_xp)
                if xp_change < self.tracking_change_min_xp:
                    tracked_player['track'] = False

                tracked_player['last_checked'] = curr_time

            if tracked_player['track']:
                tracked_players.append(tracked_player)

            await self.bot.db.tracked_players.replace_one({'id': player_id}, tracked_player)

        return tracked_players

    async def remove_player_from_tracked(self, player_id):
        tracked_player = self.bot.db.tracked_players.find_one(
            {'id': player_id})
        if tracked_player:
            tracked_player['track'] = False
            await self.bot.db.tracked_players.replace_one({'id': player_id}, tracked_player)

    @commands.command(aliases=['tp'])
    async def track_player(self, ctx, *, name=None):
        if name is None:
            return await ctx.send('Must give name to track')

        if await self.is_blacklisted(name):
            return await ctx.send('Player not found')

        player_info = await self.get_page_info(f'{self.bot.leaderboards_api_url}/players/name/{name}')
        if not player_info:
            return await ctx.send('Player not found')

        tracked_player = await self.bot.db.tracked_players.find_one(
            {'id': player_info['id']})
        if tracked_player:
            if tracked_player['track']:
                return await ctx.send('Player already being tracked')
            else:
                tracked_player['track'] = True
                tracked_player['last_checked'] = datetime.utcnow()
                await self.tracked_player_to_db(tracked_player, player_info)
        else:
            tracked_player = {
                'id': player_info['id'],
                'name': player_info['name'],
                'name_lowered': name.lower(),
                'last_checked': datetime.utcnow(),
                'track': True,
                'total_xp': 0,
                'records': []
            }
            await self.tracked_player_to_db(tracked_player, player_info)
        return await ctx.send(f'Started tracking for player: {name}!')

    @commands.command(aliases=['tpi'])
    async def tracked_player_info(self, ctx, *, name=None):
        if name is None:
            return await ctx.send('Must give name to get info for')

        player_info = await self.get_page_info(f'{self.bot.leaderboards_api_url}/players/name/{name}')
        if not player_info:
            return await ctx.send('Player not found')

        tracked_player = await self.bot.db.tracked_players.find_one(
            {'id': player_info['id']})
        if not tracked_player:
            return await ctx.send('Player not found')

        i = 0
        x = []
        y = {}
        while i < len(tracked_player['records']):
            record = tracked_player['records'][i]
            xp_values = []
            total_xp = 0
            for mode in self.ranking_modes_2.keys():
                mode_xp_tag = f'{mode}_xp'
                if mode_xp_tag in record:
                    mode_xp = record[mode_xp_tag]
                    if i == 0:
                        y[mode] = []
                    y[mode].append(mode_xp)
                    total_xp += mode_xp

            x.append(record['created'])
            # if i == 0:
            #     y['total_xp'] = []

            # y['total_xp'].append(total_xp)

            i += 1
        
        fig, ax = plt.subplots()
        for k, v in y.items():
            ax.plot(x, v, label=k)

        ax_pos = ax.get_position()
        ax.legend(loc='upper right')
        # ax.set_ylim([0, self.level_table[-2]])
        plt.title(f'XP over Time for {name}')
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.gcf().autofmt_xdate()
        curr_time = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f'{name}-{curr_time}.png'
        fig.savefig(filename)
        plt.close(fig)
        await ctx.send(file=discord.File(filename))
        os.remove(filename)
    
    @commands.command(aliases=['tpim'])
    async def tracked_player_info_mode(self, ctx, mode='melee', *, name=None):
        if name is None:
            return await ctx.send('Must give name to get info for')

        player_info = await self.get_page_info(f'{self.bot.leaderboards_api_url}/players/name/{name}')
        if not player_info:
            return await ctx.send('Player not found')

        tracked_player = await self.bot.db.tracked_players.find_one(
            {'id': player_info['id']})
        if not tracked_player:
            return await ctx.send('Player not found')

        i = 0
        x = []
        y = []
        mode_xp_tag = f'{mode}_xp'
        while i < len(tracked_player['records']):
            record = tracked_player['records'][i]
            xp_values = []
            if mode_xp_tag in record:
                mode_xp = record[mode_xp_tag]
                y.append(mode_xp)

            x.append(record['created'])

            i += 1
        
        fig, ax = plt.subplots()
        ax.plot(x, y)
        ax_pos = ax.get_position()
        ax.legend(loc='upper right')
        # ax.set_ylim([0, self.level_table[-2]])
        plt.title(f'XP over Time for {name} - {mode}')
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.gcf().autofmt_xdate()
        curr_time = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f'{name}-{curr_time}.png'
        fig.savefig(filename)
        plt.close(fig)
        await ctx.send(file=discord.File(filename))
        os.remove(filename)

    @tasks.loop(hours=24)
    async def leaderboards_to_db(self):
        await self.bot.wait_until_ready()
        await self.bot.db.totals.drop()
        await self.bot.db.lw_totals.drop()
        await self.bot.db.guilds.drop()
        tasks = [self.leaderboards_to_db_task(
            mode, resource, lw) for mode, resource in self.ranking_modes.items() for lw in [True, False]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        print(results)

    async def leaderboards_to_db_task(self, mode, resource, lw=False):
        mode_level_key = f'{mode}_level'
        mode_xp_key = f'{mode}_xp'
        max_page = await self.get_max_page(mode, lw)
        lw_tag = f'{self.lone_wolf_tag}={1 if lw else 0}'
        page = 0
        while page < max_page and page < self.max_db_pages:
            if page % 1000 == 0:
                print(f'Saving leaderboards to db, {mode}: {page} | LW: {lw}')
            json_data = await self.get_page_info(f'{self.url}/{resource}.json?{lw_tag}&p={page}')
            for player in json_data:
                player_name_lower = player['name'].lower()
                player_name_lower_split = player_name_lower.split()
                player_guild_tag = None
                if len(player_name_lower_split) > 1:
                    player_guild_tag = player_name_lower_split[0]
                player_level = self.get_level(player['xp'])

                async with self.player_lock:
                    player_info = await self.bot.db.totals.find_one({'name': player_name_lower})
                    if not player_info:
                        player_info = {
                            'name': player_name_lower,
                            'total_xp': 0,
                            'total_level': 0
                        }

                    if mode_level_key in player_info:
                        player_info['total_xp'] -= player_info[mode_xp_key]
                        player_info['total_level'] -= player_info[mode_level_key]

                    player_info['total_xp'] += player['xp']
                    player_info['total_level'] += player_level
                    player_info[mode_level_key] = player_level
                    player_info[mode_xp_key] = player['xp']

                    if player_guild_tag and not lw:
                        player_guild_info = await self.bot.db.guilds.find_one({'name': player_guild_tag})
                        if not player_guild_info:
                            player_guild_info = {
                                'name': player_guild_tag,
                                'num_players': 0,
                                'total_xp': 0,
                                'total_level': 0,
                                'average_xp': 0,
                                'average_level': 0,
                                'players': []
                            }
                        player_guild_info['total_xp'] += player['xp']
                        player_guild_info['total_level'] += player_level
                        player_guild_info['players'].append(player_name_lower)
                        player_guild_info['players'] = list(
                            set(player_guild_info['players']))
                        player_guild_info['num_players'] = len(
                            player_guild_info['players'])
                        player_guild_info['average_xp'] = player_guild_info['total_xp'] // player_guild_info['num_players']
                        player_guild_info['average_level'] = player_guild_info['total_level'] // player_guild_info['num_players']
                        await self.bot.db.guilds.replace_one({'name': player_guild_tag}, player_guild_info, upsert=True)

                    if lw:
                        await self.bot.db.lw_totals.replace_one({'name': player_name_lower}, player_info, upsert=True)
                    else:
                        await self.bot.db.totals.replace_one({'name': player_name_lower}, player_info, upsert=True)
            page += 1
        return True

    @commands.command(aliases=['rt'])
    async def rankings_total(self, ctx, _type='xp', lw=False, start=1, size=20):
        if _type != 'xp' and _type != 'level':
            await ctx.send('Could not find type.\nAcceptable types: xp, level')
        elif start < 1 or size > 50:
            await ctx.send('Bad index range. Make sure start is > 0 and size is < 50')
        else:
            player_infos = self.bot.db.lw_totals.find() if lw else self.bot.db.totals.find()
            player_infos.sort(f'total_{_type}', pymongo.DESCENDING).skip(
                start-1).limit(size)

            embed = discord.Embed(
                title=f'Total Player Rankings - Sorted by {_type.title()}')
            if lw:
                embed.title = f'{embed.title} (LW)'
            i = 0
            async for player_info in player_infos:
                value = f'''
Name: {player_info["name"]}
Total XP: {player_info["total_xp"]:,}
Total Level: {player_info["total_level"]:,}
                '''
                embed.add_field(name=f'Rank {i + start}', value=value)
                i += 1

            return await ctx.send(embed=embed)
    
    async def check_if_player_lone_wolf(self, name):
        name = name.lower()
        return await self.bot.db.lw_totals.find_one({'name': name}, {'_id': False}) != None

    async def get_player_total_rank(self, name, _type):
        name = name.lower()

        player_infos = None
        if await self.bot.db.totals.find_one({'name': name}, {'_id': False}):
            player_infos = self.bot.db.totals.find()
        elif await self.bot.db.lw_totals.find_one({'name': name}, {'_id': False}):
            player_infos = self.bot.db.lw_totals.find()
        else:
            return None

        player_infos.sort(f'total_{_type}', pymongo.DESCENDING)
        player_rank = 1
        async for p in player_infos:
            if p['name'] == name:
                return player_rank
            else:
                player_rank += 1
        return None

    @tasks.loop(hours=24)
    async def clear_old_cache(self):
        await self.bot.wait_until_ready()
        print('Started clearing old cache')
        for name in self.bot.player_cache.scan_iter('*'):
            player_info = await self.get_player_from_cache(name)
            modify_date = datetime.strptime(
                player_info['modify_date'.encode()].decode(), '%Y-%m-%dT%H:%M:%SZ')
            if modify_date + timedelta(days=1) < datetime.utcnow():
                self.bot.player_cache.delete(name)
                print(f'Deleted {name}: {player_info} from cache')
        print('Finished clearing old cache')

    @tasks.loop(minutes=30)
    async def check_pages(self):
        await self.bot.wait_until_ready()
        max_pages = {mode: 0 for mode in self.ranking_modes.keys()}
        for mode, resource in self.ranking_modes.items():
            max_pages[mode] = await self.check_pages_helper(resource)
        self.bot.max_page_cache.hmset('max_pages', max_pages)
        print(f'Saved max pages {max_pages}')

        lw_max_pages = {mode: 0 for mode in self.ranking_modes.keys()}
        for mode, resource in self.ranking_modes.items():
            lw_max_pages[mode] = await self.check_pages_helper(resource, True)
        self.bot.max_page_cache.hmset('lw_max_pages', lw_max_pages)
        print(f'Saved lone wolf max pages {lw_max_pages}')

    async def get_page_info(self, link, tries=0):
        if tries > self.total_connection_retries:
            return None

        try:
            async with self.session.get(link) as response:
                data = await response.json(content_type=None)
        except ClientOSError:
            return await self.get_page_info(link, tries + 1)
        except ValueError:
            return None
        else:
            return data

    async def check_pages_helper(self, resource, lw=False):
        index_1 = 1
        index_2 = 1

        lw_tag = f'{self.lone_wolf_tag}={1 if lw else 0}'

        req = await self.get_page_info(f'{self.url}/{resource}.json?{lw_tag}&p={index_1}')
        while req:
            index_2 = index_1
            index_1 = index_1 * 2
            req = await self.get_page_info(f'{self.url}/{resource}.json?{lw_tag}&p={index_1}')

        mid = 0
        while index_1 != index_2:
            mid = index_1 + (index_2 - index_1) // 2
            req = await self.get_page_info(f'{self.url}/{resource}.json?{lw_tag}&p={mid}')
            if req:
                index_2 = mid + 1
            else:
                index_1 = mid

        return index_1 - 1

    async def level_binary_search(self, level, mode, lw=False):
        resource = self.ranking_modes[mode]

        lw_tag = f'{self.lone_wolf_tag}={1 if lw else 0}'

        low = 0
        high = await self.get_max_page(mode, lw)

        while low <= high:
            mid = (low + high) // 2

            data = await self.get_page_info(f'{self.url}/{resource}.json?{lw_tag}&p={mid}')
            last_level = self.get_level(data[0]['xp'])

            if last_level > level:
                low = mid + 1
            elif last_level < level:
                high = mid - 1
            else:
                low = mid + 1

        return high

    async def get_max_page(self, mode, lw=False):
        max_pages = self.bot.max_page_cache.hgetall('lw_max_pages') if lw else self.bot.max_page_cache.hgetall('max_pages')
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

    async def remove_player_in_cache(self, name):
        return self.bot.player_cache.delete(name)

    async def get_player_from_db(self, name):
        name = name.lower()
        return await self.bot.db.players.find_one({'name': name})

    async def set_player_in_db(self, name, player_info):
        name = name.lower()
        return await self.bot.db.players.replace_one({'name': name}, player_info, upsert=True)

    @commands.command(aliases=['pol'])
    async def players_over_level(self, ctx, level=80, mode=None, lw=False):
        if mode and mode not in self.ranking_modes:
            return await ctx.send(f'Could not find mode.\nAcceptable Modes: {", ".join([m for m in self.ranking_modes.keys()])}')

        if level < 80 or level > 120:
            return await ctx.send('Bad level. Pick a level between 80 and 120.')

        if mode:
            search_resources = [self.ranking_modes[mode]]
        else:
            search_resources = list(self.ranking_modes.values())

        lw_tag = f'{self.lone_wolf_tag}={1 if lw else 0}'

        embed_title = f'Players above Level {level} in {mode.capitalize() if mode else "ALL"}'
        embed = discord.Embed(title=f'Searching for {embed_title}')
        msg = await ctx.send(embed=embed)

        player_counts = {}
        for resource in search_resources:
            data = await self.get_page_info(f'{self.url}/{resource}.json?{lw_tag}&p=0')
            page = 1
            while data and self.get_level(data[0]['xp']) >= level:
                for player in data:
                    player_level = self.get_level(player['xp'])
                    if player_level >= level:
                        if player['name'] not in player_counts:
                            player_counts[player['name']] = (1, player_level)
                        else:
                            count, total_level = player_counts[player['name']]
                            player_counts[player['name']] = (
                                count + 1, total_level + player_level)
                data = await self.get_page_info(f'{self.url}/{resource}.json?{lw_tag}&p={page}')
                page += 1

        filtered_player_levels = {
            k: v[1] for k, v in player_counts.items() if v[0] == len(search_resources)}
        filtered_player_names = [k for k, v in sorted(
            filtered_player_levels.items(), key=lambda k:k[1], reverse=True)]

        if len(filtered_player_names) > self.items_per_page:
            splits = math.ceil(
                len(filtered_player_names) / self.items_per_page)

            embeds = []
            i = 0
            for j in range(splits):
                i += self.items_per_page
                if i > len(filtered_player_names):
                    i = len(filtered_player_names)

                embed = discord.Embed(
                    title=f'Found {len(filtered_player_names)} {embed_title}', color=discord.Color.purple())
                for player_name in filtered_player_names[j * self.items_per_page:i]:
                    embed.add_field(
                        name=player_name, value=filtered_player_levels[player_name], inline=True)
                embeds.append(embed)
            await msg.delete()
            paginator = DiscordUtils.Pagination.AutoEmbedPaginator(
                ctx, auto_footer=True)
            return await paginator.run(embeds)
        else:
            embed = discord.Embed(
                title=f'Found {len(filtered_player_names)} {embed_title}', color=discord.Color.purple())
            for player_name in filtered_player_names:
                embed.add_field(
                    name=player_name, value=filtered_player_levels[player_name], inline=False)
            await msg.delete()
            return await ctx.send(embed=embed)

    @commands.command(aliases=['gts'])
    async def guild_tag_search(self, ctx, tag, player_sort='level'):
        if player_sort != 'xp' and player_sort != 'level':
            await ctx.send('Could not find sorting type.\nAcceptable types: xp, level')
        tag = tag.lower()
        guild_info = await self.bot.db.guilds.find_one({'name': tag}, {'_id': False})

        embed = discord.Embed(title=f'Searching for {tag.upper()}')
        msg = await ctx.send(embed=embed)

        if guild_info:
            guild_players = guild_info['players']
            guild_player_infos = {}
            for player_name in guild_players:
                player_info = await self.bot.db.totals.find_one({'name': player_name}, {'_id': False})
                if player_info:
                    guild_player_infos[player_name] = {
                        'xp': player_info['total_xp'], 'level': player_info['total_level']}
                else:
                    guild_player_infos[player_name] = {'xp': 0, 'level': 0}
            guild_player_infos = [(k, v) for k, v in sorted(
                guild_player_infos.items(), key=lambda k:k[1][player_sort], reverse=True)]
            num_players = guild_info['num_players']
            total_xp = guild_info['total_xp']
            total_levels = guild_info['total_level']
            avg_xp_per_player = guild_info['average_xp']
            avg_levels_per_player = guild_info['average_level']
            if num_players > self.items_per_page:
                splits = math.ceil(num_players / self.items_per_page)

                embeds = []
                i = 0
                for j in range(splits):
                    i += self.items_per_page
                    if i > num_players:
                        i = num_players

                    embed = discord.Embed(
                        title=f'Guild {tag.upper()} - {num_players} Players Found',
                        color=discord.Color.purple(),
                        description=f'''
Total XP: {total_xp:,}
Total Levels: {total_levels:,}
Avg XP Per Member: {avg_xp_per_player:,}
Avg Levels Per Member: {avg_levels_per_player:,}
                        '''
                    )
                    for player_name, player_values in guild_player_infos[j * self.items_per_page:i]:
                        player_value = f"XP: {player_values['xp']:,}\nLevels: {player_values['level']:,}"
                        embed.add_field(name=player_name,
                                        value=player_value, inline=True)
                    embeds.append(embed)
                await msg.delete()
                paginator = DiscordUtils.Pagination.AutoEmbedPaginator(
                    ctx, auto_footer=True)
                return await paginator.run(embeds)
            else:
                embed = discord.Embed(
                    title=f'Guild {tag.upper()} - {num_players} Players Found',
                    color=discord.Color.purple(),
                    description=f'''
Total XP: {total_xp:,}
Total Levels: {total_levels:,}
Avg XP Per Member: {avg_xp_per_player:,}
Avg Levels Per Member: {avg_levels_per_player:,}
                    '''
                )
                for player_name, player_values in guild_player_infos:
                    player_value = f"XP: {player_values['xp']:,}\nLevels: {player_values['level']:,}"
                    embed.add_field(name=player_name,
                                    value=player_value, inline=True)
                await msg.delete()
                return await ctx.send(embed=embed)

        await msg.delete()
        return await ctx.send(f'Guild {tag} not found within {self.max_db_pages} leaderboard pages')

    @commands.command(aliases=['gr'])
    async def guild_rankings(self, ctx, calc='total', _type='xp', min_members=10, start=1, size=10):
        if _type != 'xp' and _type != 'level':
            return await ctx.send('Could not find type.\nAcceptable types: xp, level')
        elif start < 1 or size > 50:
            return await ctx.send('Bad index range. Make sure start is > 0 and size is < 50')
        elif calc != 'average' and calc != 'total':
            return await ctx.send('Bad calc type.\nAcceptable types: average, total')
        else:
            guild_infos = self.bot.db.guilds.find(
                {'num_players': {'$gte': min_members}})
            if not guild_infos:
                return await ctx.send('No guilds match this criteria')

            guild_infos.sort(f'{calc}_{_type}', pymongo.DESCENDING).skip(
                start-1).limit(size)

            embed = discord.Embed(
                title=f'Guild Rankings - Sorted by {calc.title()} {_type.title()}')
            i = 0
            async for guild_info in guild_infos:
                value = f'''
Tag: {guild_info["name"]}
Num Players: {guild_info["num_players"]}
Total XP: {guild_info["total_xp"]:,}
Total Level: {guild_info["total_level"]:,}
Average XP Per Player: {guild_info["average_xp"]:,}
Average Levels Per Player: {guild_info["average_level"]:,}
                '''
                embed.add_field(name=f'Rank {i + start}', value=value)
                i += 1

            return await ctx.send(embed=embed)

    @commands.command()
    async def rankings(self, ctx, mode='melee', page='1', lw=False):
        if mode not in self.ranking_modes:
            await ctx.send(f'Could not find mode.\nAcceptable Modes: {", ".join([m for m in self.ranking_modes.keys()])}')
        else:
            resource = self.ranking_modes[mode]
            lw_tag = f'{self.lone_wolf_tag}={1 if lw else 0}'
            json_data = await self.get_page_info(f'{self.url}/{resource}.json?{lw_tag}&p={int(page)-1}')
            if not json_data:
                return await ctx.send(f'Ran out of pages!')

            embed = discord.Embed(title=f'Player Rankings - {mode}')
            for i, p in enumerate(json_data):
                value = f'''
Name: {p["name"]}
Level: {self.get_level(p["xp"])}
XP: {p["xp"]:,}
                '''
                embed.add_field(
                    name=f'Rank {20*(int(page)-1)+i+1}', value=value)

            max_page = await self.get_max_page(mode)
            if max_page:
                max_page = str(max_page)
            else:
                max_page = 'NA'

            embed.set_footer(text=f'Page {page} / {max_page}')

            return await ctx.send(embed=embed)

    @commands.command(aliases=['rsearch', 'rs', 'rankingss'])
    async def rankings_search(self, ctx, *, name=None):
        return await self.rank_search_helper(ctx, [mode for mode in self.ranking_modes.keys()], name)

    @commands.command(aliases=['rsm', 'rmode'])
    async def rankings_search_mode(self, ctx, mode=None, *, name=None):
        if not mode or mode not in self.ranking_modes_2:
            await ctx.send(f'Could not find mode.\nAcceptable Modes: {", ".join([m for m in self.ranking_modes_2.keys()])}')
        else:
            return await self.rank_search_helper(ctx, [mode], name)

    async def rank_search_helper(self, ctx, modes, name):
        if not name:
            name = await self.get_author_name(str(ctx.author.id))
            if not name:
                return await ctx.send('User not linked!')
        elif len(name) < 3 or len(name) > 14:
            return await ctx.send('Invalid name!')

        print(f'Starting rank search for {name}')
        embed = discord.Embed(
            title=f'Searching leaderboards for {name}...',
            color=discord.Color.green()
        )
        msg = await ctx.send(embed=embed)

        if await self.is_blacklisted(name):
            embed.title = f'Info for {name} not found'
            embed.color = discord.Color.red()
            print(f'{name} is blacklisted')
            return await msg.edit(embed=embed)

        player_info = await self.get_page_info(f'{self.bot.leaderboards_api_url}/players/name/{name}')
        if not player_info:
            embed.title = f'Info for {name} not found'
            embed.color = discord.Color.red()
            print(f'{name} not found')
            return await msg.edit(embed=embed)

        embed.title = f'Rank info for {player_info["name"]}'
        if await self.check_if_player_lone_wolf(name):
            embed.title = f'{embed.title} (LW)'
        embed.color = discord.Color.purple()
        name = name.lower()
        total_xp = 0
        total_levels = 0
        for mode, i in self.ranking_modes_2.items():
            rank = await self.get_page_info(f'{self.bot.leaderboards_api_url}/players/rank/{player_info["id"]}/{i}')
            mode_api = f'{mode}_xp'
            xp = player_info[mode_api]
            level = self.get_level(xp)
            total_xp += xp
            total_levels += level
            embed.add_field(
                name=mode, value=f'#{rank if rank else "NA":,} (LV. {level}) {xp:,} XP', inline=False)

        if len(modes) > 1:
            total_xp_rank = await self.get_player_total_rank(name, 'xp')
            total_level_rank = await self.get_player_total_rank(name, 'level')
            total_levels = sum([self.get_level(
                player_info[f'{mode}_xp']) for mode in self.ranking_modes_2.keys()])
            footer_text = f'Levels: #{total_level_rank if total_level_rank else "NA"} - {total_levels:,} | XP: #{total_xp_rank if total_xp_rank else "NA"} - {total_xp:,}'
            embed.set_footer(text=footer_text)

        print(f'Finished rank search for {name}')
        return await msg.edit(embed=embed)

    @commands.command(aliases=['rl'])
    async def rankings_link(self, ctx, *, name):
        if len(name) < 3 or len(name) > 14:
            return await ctx.send('Invalid name!')

        link_info = {
            'author_id': str(ctx.author.id),
            'name': name
        }
        await self.bot.db.links.replace_one({'author_id': str(ctx.author.id)}, link_info, upsert=True)

        await ctx.send('Linked account!')
        print(f'Linked account {str(ctx.author.id)} to {name}')

    async def get_author_name(self, author_id):
        link_info = await self.bot.db.links.find_one({'author_id': author_id})
        if link_info:
            return link_info['name']
        return None

    def get_level(self, xp):
        level = 0
        while xp >= self.level_table[level]:
            level += 1
        return level

    async def is_blacklisted(self, name):
        try:
            with open(self.blacklist_file) as f:
                blacklisted_players = f.read().splitlines()

            if blacklisted_players:
                return name.lower() in blacklisted_players
        except FileNotFoundError as e:
            print(e)

        return False


async def setup(bot):
    await bot.add_cog(Ranking(bot))
    print('Loaded Rankings')
