import discord
from discord.ext import commands
import os
import json

def get_prefix(client, message):
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    try:
        prefix = config[str(message.guild.id)]['prefix']
    except:
        config[str(message.guild.id)] = {'prefix': '!'}
        with open('config.json', 'w') as f:
            json.dump(config, f)
        prefix = '!'
    return prefix

client = commands.Bot(command_prefix=get_prefix)

# async def load(ctx, extension):
#     client.load_extension(f'cogs.{extension}')

# async def unload(ctx, extension):
#     client.unload_extension(f'cogs.{extension}')

# async def reload(ctx, extension):
#     client.unload_extension(f'cogs.{extension}')
#     client.load_extension(f'cogs.{extension}')

for filename in os.listdir('./cogs'):
    if filename.endswith('.py'):
        client.load_extension(f'cogs.{filename[:-3]}')

with open('settings.json', 'r') as f:
    token = json.load(f)['token']
client.run(token)