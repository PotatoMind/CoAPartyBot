## CoaPartyBot
This example defines a basic setup for CoAPartyBot. CoAPartyBot is used to do a faster rank search than Curse of Aros (CoA) leaderboards website and pull info from the CoA wiki. 

## Settings configuration
Before this bot can be used, the settings have to be set. The database connection parameters can be changed for outside databases. If they are changed to an outside database, make sure to remove the services in `docker-compose.yml`.
__settings.json__:
- `token`: Discord application bot token
- `owner_id`: Discord user ID of the bot owner
- `mongo_uri`: MongoDB URI to connect to
- `redis_url`: Redis URL to connect to
Note: An example template is `settings.template.json`. Feel free to rename this file and change the paramaters. MongoDB and Redis connection parameters are already set to the defaults required by docker compose, so only the token and owner_id need to be set for a fully functional bot.

## Deploy with docker-compose

```
$ docker-compose up -d
```

## Stop and remove the containers

```
$ docker-compose down
```

To delete all data, remove all named volumes by passing the -v arguments:

```
$ docker-compose down -v
```

## Websites
- CoA Wiki: https://curseofaros.wiki/
- CoA Leaderboards: https://www.curseofaros.com/