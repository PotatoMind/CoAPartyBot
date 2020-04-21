import discord
from discord.ext import commands, tasks
import asyncio
import numpy as np
from datetime import datetime
from datetime import timedelta
import re
import json

class Giveaway(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.time_lookup = {'s': 1, 'm': 60, 'h': 3600}
        self.time_regex = r'^[0-9]+[smh]?$'
        self.emoji = '\N{PURPLE HEART}'
        self.lock = asyncio.Lock()
        self.check_giveaways.start()

    @tasks.loop(seconds=1)
    async def check_giveaways(self):
        await self.client.wait_until_ready()
        with open('config.json', 'r') as f:
            config = json.load(f)
        for guild_id, guild_data in config.items():
            if len(guild_data['giveaways']) > 0:
                msg_id, msg_data = list(guild_data['giveaways'].items())[0]
                if msg_data[0] < datetime.utcnow().timestamp():
                    channel = self.client.get_channel(msg_data[1])
                    await self.remove_giveaway(channel, msg_id)
                    msg = await channel.fetch_message(msg_id)
                    embed = msg.embeds[0]
                    winners = await self.get_winners(channel, msg, msg_data[3])
                    embed.description = 'Has been completed'
                    embed.color = discord.Color.purple()
                    embed.remove_field(1)
                    embed.add_field(name='Winners', value=f'{" ".join([w.mention for w in winners])}')
                    await msg.edit(embed=embed)
                    await msg.clear_reactions()

    @commands.command()
    async def giveaway_start(self, ctx, length=None, num_winners=None, *, item=None):
        if not (length and num_winners and item):
            await ctx.send('Bad arguments. Ex: "!giveaway_start 30m 2 potatoes"')
            return
        if not re.match(self.time_regex, length.lower()):
            await ctx.send('Bad time format. Ex: "3600s", "60m", "1h", "3600"')
            return
        try:
            num_winners = int(num_winners)
        except:
            await ctx.send('Bad number of winner format.')
            return

        length_in_seconds = int(length[:-1]) * self.time_lookup[length[-1]]
        ends_at = ctx.message.created_at + timedelta(seconds=length_in_seconds)
        embed = discord.Embed(
            title=f'Giveaway for {item}',
            description=f'React to this to enter',
            color=discord.Color.magenta(),
            timestamp=ends_at,
        )
        embed.set_footer(text='Ends at')
        embed.add_field(name='Author', value=f'Hosted by {ctx.message.author.mention}')
        embed.add_field(name='Max Winners', value=f'{num_winners}')

        msg = await ctx.send(embed=embed)
        await msg.add_reaction(self.emoji)

        await self.add_giveaway(ctx, ends_at.timestamp(), msg.id, msg.channel.id, item, num_winners)

        # msg = await ctx.fetch_message(msg.id)
        # players = await self.get_reactions(ctx, msg)
        # winners = np.random.choice(players, num_winners, False)
        # await ctx.send(f'Winners: {" ".join([w.mention for w in winners])}')
    
    async def get_winners(self, ctx, msg, num_winners):
        players = set()
        r_msg = await ctx.fetch_message(msg.id)
        for reaction in r_msg.reactions:
            async for user in reaction.users():
                if not user.bot:
                    players.add(user)
        
        winners = np.random.choice(list(players), num_winners, False)

        return winners
    
    async def add_giveaway(self, ctx, ends_at, msg_id, channel_id, item, num_winners):
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        config[str(ctx.guild.id)]['giveaways'][msg_id] = (ends_at, channel_id, item, num_winners)
        config[str(ctx.guild.id)]['giveaways'] = {k: v for k, v in sorted(config[str(ctx.guild.id)]['giveaways'].items(), key=lambda x:x[1][0])}

        with open('config.json', 'w') as f:
            json.dump(config, f)
    
    async def remove_giveaway(self, ctx, msg_id):
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        config[str(ctx.guild.id)]['giveaways'].pop(msg_id)

        with open('config.json', 'w') as f:
            json.dump(config, f)

def setup(client):
    client.add_cog(Giveaway(client))
    print('Loaded Giveaways')