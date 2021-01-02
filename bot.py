import discord
from discord.ext import commands
import os
import json
from datetime import datetime
from pymongo import MongoClient
from pymongo.collation import Collation
from redis.client import Redis

def get_prefix(bot, message):
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

bot = commands.Bot(command_prefix=get_prefix)
bot.launch_time = datetime.utcnow()

for filename in os.listdir('./cogs'):
    if filename.endswith('.py'):
        bot.load_extension(f'cogs.{filename[:-3]}')

with open('settings.json', 'r') as f:
    settings = json.load(f)

token = settings['token']
bot.owner_id = settings['owner_id']
mongo_client = MongoClient(settings['mongo_uri'])
bot.db = mongo_client['coa']
player_cache = Redis.from_url(settings['redis_url'], db=0)
max_page_cache = Redis.from_url(settings['redis_url'], db=1)
bot.player_cache = player_cache
bot.max_page_cache = max_page_cache
bot.run(token)
