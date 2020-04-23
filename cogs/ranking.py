import discord
from discord.ext import commands, tasks
import json
from urllib.parse import quote
import aiohttp
import sys
from prettytable import PrettyTable

class Ranking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.url = 'https://curseofaros.com'
        self.ranking_modes = {
            'xp': 'highscores',
            'mining': 'highscores-mining',
            'smithing': 'highscores-smithing',
            'woodcutting': 'highscores-woodcutting',
            'crafting': 'highscores-crafting'
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
            sys.maxsize
        ]
        
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
            await ctx.send(f'```diff\n{table}\n*** Page {page} ***\n```')
            # embed = discord.Embed(
            #     title=f'Top ranks for {mode}',
            #     description='\n\n'.join([f'#{20*(int(page)-1)+i+1}. (LV. {self.get_level(p["xp"])}) {p["name"]} | {p["xp"]:,} XP' for i, p in enumerate(json_data)]),
            #     color=discord.Color.green()
            # )
            # for i, p in enumerate(json_data):
            #     embed.add_field(name=f'# {20*(int(page)-1)+i+1}. {p["name"]}', value=f'Level: {self.get_level(p["xp"])}, XP: {p["xp"]}', inline=False)
            # embed.set_footer(text=f'Page {page}')
            # await ctx.send(embed=embed)
    
    @commands.command(aliases=['rsearch', 'rs', 'rankingss'])
    async def rankings_search(self, ctx, *, name=None):
        if not name:
            name = await self.get_author_name(str(ctx.author.id))
            if not name:
                return await ctx.send('User not linked!')
  
        if len(name) < 3 or len(name) > 14:
            return await ctx.send('Invalid name!')

        info = {mode: ('NA', 'NA') for mode in self.ranking_modes.keys()}
        color = None
        for mode in self.ranking_modes.keys():
            sub_info, color = await self.get_rank_info(mode, name)
            info[mode] = sub_info

        embed = discord.Embed(
            title=f'Rank Info for {name}',
            color=discord.Color(int(f'0x{color}', 16))
        )
        for mode, data in info.items():
            embed.add_field(name=mode, value=f'#{data[0]} (LV. {self.get_level(data[1])}) {data[1]:,} XP', inline=False)
        await ctx.send(embed=embed)

    @commands.command(aliases=['rsm', 'rmode'])
    async def rankings_search_mode(self, ctx, mode, *, name=None):
        if not name:
            name = await self.get_author_name(str(ctx.author.id))
            if not name:
                return await ctx.send('User not linked!')
        if len(name) < 3 or len(name) > 14:
            return await ctx.send('Invalid name!')
        if not mode and mode not in self.ranking_modes:
            await ctx.send(f'Could not find mode.\nAcceptable Modes: {", ".join([m for m in self.ranking_modes.keys()])}')
        else:
            info, color = await self.get_rank_info(mode, name)
            
            if info:
                embed = discord.Embed(
                    title=f'Rank Info for {name}',
                    color=discord.Color(int(f'0x{color}', 16))
                )
                embed.add_field(name=mode, value=f'#{info[0]} (LV. {self.get_level(info[1])}) {info[1]:,} XP', inline=False)
                await ctx.send(embed=embed)
            else:
                await ctx.send('Player rank info not found!')
    
    @commands.command(aliases=['rl'])
    async def rankings_link(self, ctx, *, name):
        if len(name) < 3 or len(name) > 14:
            return await ctx.send('Invalid name!')
        
        with open('rankings.json', 'r') as f:
            config = json.load(f)
        
        config[str(ctx.author.id)] = name

        with open('rankings.json', 'w') as f:
            json.dump(config, f)

        await ctx.send('Linked account!')
    
    @commands.command(aliases=['rul'])
    async def rankings_unlink(self, ctx):
        with open('rankings.json', 'r') as f:
            config = json.load(f)
        
        found = config.pop(str(ctx.author.id), None)
        if not found:
            return await ctx.send('Account not found!')

        with open('rankings.json', 'w') as f:
            json.dump(config, f)
        
        await ctx.send('Unlinked account!')
    
    async def get_author_name(self, id):
        with open('rankings.json', 'r') as f:
            config = json.load(f)
        
        return config.get(id, None)

    def get_level(self, xp):
        level = 0
        while xp >= self.level_table[level]:
            level += 1
        return level
    
    async def get_rank_info(self, mode, name):
        info = None
        color = None
        resource = self.ranking_modes[mode]
        page = 0
        i = 1
        found = False
        async with aiohttp.ClientSession() as cs:
            async with cs.get(f'{self.url}/{resource}.json?p={page}') as r:
                req = await r.text()
        while req and not found:
            j = 0
            json_data = json.loads(req)
            while j < len(json_data) and not found:
                player = json_data[j]
                if player['name'] == name:
                    found = True
                    info = (i, player['xp'])
                    color = player['name_color'] if player['name_color'] else '99aab5'
                else:
                    j += 1
                i += 1
            page += 1
            async with aiohttp.ClientSession() as cs:
                async with cs.get(f'{self.url}/{resource}.json?p={page}') as r:
                    req = await r.text()
        
        return info, color

def setup(bot):
    bot.add_cog(Ranking(bot))
    print('Loaded Rankings')