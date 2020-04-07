import discord
from discord.ext import commands
import os
import json

def get_prefix(client, message):
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    return config[str(message.guild.id)]['prefix']

client = commands.Bot(command_prefix=get_prefix)

@client.command()
async def load(ctx, extension):
    client.load_extension(f'cogs.{extension}')

@client.command()
async def unload(ctx, extension):
    client.unload_extension(f'cogs.{extension}')

@client.command()
async def reload(ctx, extension):
    client.unload_extension(f'cogs.{extension}')
    client.load_extension(f'cogs.{extension}')

for filename in os.listdir('./cogs'):
    if filename.endswith('.py'):
        client.load_extension(f'cogs.{filename[:-3]}')

# @client.command()
# async def ping(ctx):
#     await ctx.send(f'Pong! {round(client.latency * 1000)}ms')

# @client.command()
# async def giveaway(ctx, length, winners, max_players, *, item):
#     start = time.time()
#     await ctx.send(f'''Starting giveaway for {item}.\n
#     Max of {max_players} can enter, and only {winners} can win.\n
#     Giveaway starts at {start + int(length)}!
#     ''')

with open('settings.json', 'r') as f:
    token = json.load(f)['token']
client.run(token)