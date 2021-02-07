import discord
from discord.ext import commands
import os
import json
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from redis.client import Redis

async def get_prefix(bot, message):
    guild_id = str(message.guild.id)
    prefix_info = await bot.db.prefixes.find_one({'guild_id': guild_id})
    prefix = '!?'
    if prefix_info:
        prefix = prefix_info['prefix']
    else:
        prefix_info = {
            'guild_id': guild_id,
            'prefix': prefix
        }
        await bot.db.prefixes.insert_one(prefix_info)
    return commands.when_mentioned_or(prefix)(bot, message)

bot = commands.Bot(command_prefix=get_prefix, activity=discord.Game('Default prefix: !?'))
bot.launch_time = datetime.utcnow()

for filename in os.listdir('./cogs'):
    if filename.endswith('.py'):
        bot.load_extension(f'cogs.{filename[:-3]}')

with open('settings.json', 'r') as f:
    settings = json.load(f)

token = settings['token']
bot.owner_id = settings['owner_id']
motor_client = AsyncIOMotorClient(settings['mongo_uri'])
bot.db = motor_client['coa']
player_cache = Redis.from_url(settings['redis_url'], db=0)
max_page_cache = Redis.from_url(settings['redis_url'], db=1)
bot.player_cache = player_cache
bot.max_page_cache = max_page_cache
bot.run(token)
