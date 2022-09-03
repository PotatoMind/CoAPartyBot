import discord
from discord.ext import commands
import os
import json
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from redis.client import Redis
import asyncio


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


async def load_cogs(bot):
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            await bot.load_extension(f'cogs.{filename[:-3]}')


async def main():
    intents = discord.Intents.default()

    bot = commands.Bot(command_prefix=get_prefix, intents=intents)
    bot.launch_time = datetime.utcnow()

    await load_cogs(bot)

    with open('settings.json', 'r') as f:
        settings = json.load(f)

    token = settings['token']
    bot.owner_id = settings['owner_id']
    bot.leaderboards_api_url = settings['leaderboards_api_url']
    motor_client = AsyncIOMotorClient(settings['mongo_uri'])
    bot.db = motor_client['coa']
    player_cache = Redis.from_url(settings['redis_url'], db=0)
    max_page_cache = Redis.from_url(settings['redis_url'], db=1)
    bot.player_cache = player_cache
    bot.max_page_cache = max_page_cache
    await bot.start(token)

asyncio.run(main())
