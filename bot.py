import discord
from discord.ext import commands
import os
import json
from datetime import datetime
from pymongo import MongoClient
from pymongo.collation import Collation
from redis.client import Redis

def get_prefix(bot, message):
    guild_id = str(message.guild.id)
    prefix_info = bot.db.prefixes.find_one({'guild_id': guild_id})
    if prefix_info:
        return prefix_info['prefix']
    else:
        prefix_info = {
            'guild_id': guild_id,
            'prefix': '!'
        }
        bot.db.prefixes.insert_one(prefix_info)
        return '!'

def json_to_db(collection):
    with open('config.json', 'r') as f:
        config = json.load(f)
    for guild_id, info in config.items():
        prefix_info = {
            'guild_id': guild_id,
            'prefix': info['prefix']
        }
        collection.insert_one(prefix_info)
        print(f'inserted {prefix_info}')

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
json_to_db(bot.db.prefixes)
player_cache = Redis.from_url(settings['redis_url'], db=0)
max_page_cache = Redis.from_url(settings['redis_url'], db=1)
bot.player_cache = player_cache
bot.max_page_cache = max_page_cache
bot.run(token)
