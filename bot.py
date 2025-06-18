import asyncio
import os
import re
import discord
import json
import aiofiles
from rich import print
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from discord.ext import commands


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
SHOP_FILE = os.path.join(DATA_DIR, "shop.json")
PREDICTIONS_FILE = os.path.join(DATA_DIR, "predictions.json")

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

FILEPATHS = [SETTINGS_FILE, USERS_FILE, SHOP_FILE, PREDICTIONS_FILE]
LIST_OF_COMMANDS = ["!bet", "!shop", "!wallet", "!buy", "!sell", "!predictions", "!auction_item", "!auctions", "!bid", "!inventory", "!my_bets", "!reward", "!create_auction", "!create_prediction", "!close_prediction", "!resolve_prediction", "!create_shop_item", "!delete_shop_item", "!edit_shop_item", "!reset_user_inventory", "!reset_user", "!purge_deprecated_users", "!set_default_channel", "!toggle_command"]
USER_COMMANDS = []
MODERATOR_COMMANDS = []
DEBUG = False

COMMAND_QUEUE = []


intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix = "!", intents = intents)

async def add_server_to_jsons(server_id):
    settings = await async_load_json(SETTINGS_FILE)
    if server_id not in settings:
        settings[server_id] = {
            "Default Commerce Channel ID": None,
            "User Commands":{
                "!bet": True,
                "!shop": True,
                "!wallet": True,
                "!buy": True,
                "!sell": True,
                "!predictions": True,
                "!auction_item": True,
                "!auctions": True,
                "!bid": True,
                "!inventory": True,
                "!my_bets": True
            },
            "Privileged Commands":{
                "!reward": True,
                "!create_auction": True,
                "!create_prediction": True,
                "!close_prediction": True,
                "!resolve_prediction": True,
                "!create_shop_item": True,
                "!delete_shop_item": True,
                "!edit_shop_item": True,
                "!reset_user_inventory": True,
                "!reset_user": True,
                "!purge_deprecated_users": True,
                "!set_default_channel": True
            }
            }
    await async_save_json(SETTINGS_FILE, settings)
    
    shop = await async_load_json(SHOP_FILE)
    if server_id not in shop:
        shop[server_id] = {
            "Next Shop ID": 1,
            "Next Auction ID": 1,
            "Items":{},
            "Auctions":{}
        }
    await async_save_json(SHOP_FILE, shop)
    
    users = await async_load_json(USERS_FILE)
    if server_id not in users:
        users[server_id] = {}
    await async_save_json(USERS_FILE, users)
    
    predictions = await async_load_json(PREDICTIONS_FILE)
    if server_id not in predictions:
        predictions[server_id] = {
            "Predictions": {},
            "Data": {
                "next_bet_number": 1
            }
        }
    await async_save_json(PREDICTIONS_FILE, predictions)

async def add_user_to_json(server_id, user_id):
    users = await async_load_json(USERS_FILE)
    name = await get_display_name(server_id, user_id)
    user_name = await get_user_name(server_id, user_id)
    if user_id not in users[server_id]:
        if DEBUG:
            print("[yellow]User_id not in users[server_id]")
        users[server_id][user_id] = {
            "display_name": name,
            "user_name": user_name,
            "inventory": {},
            "total_currency_bet": 0,
            "total_currency_won": 0,
            "total_currency_lost": 0,
            "profit": 0,
            "bets_won": 0,
            "bets_lost": 0,
            "wallet": 500
        }
        await async_save_json(USERS_FILE, users)

async def update_display_name(server_id, user_id, name):
    users = await async_load_json(USERS_FILE)
    users[server_id][user_id]["display_name"] = name
    await async_save_json(USERS_FILE, users)

async def add_prediction_to_json(title, options, server_id): #Dictionary of options
    current_prediction = {
        "title": title, 
        "options": options,
        "open": True,
        "user_bets": {},
        "total_bets": 0
        }
    predictions = await async_load_json(PREDICTIONS_FILE)
    next_bet_number = str(predictions[server_id]["Data"]["next_bet_number"])
    predictions[server_id]["Predictions"][next_bet_number] = current_prediction
    predictions[server_id]["Data"]["next_bet_number"] += 1
    await async_save_json(PREDICTIONS_FILE, predictions)

async def add_user_bet(server_id, user_id, prediction_number, option_number, amount, channel_id = None): #Add prediction to commerce.json
    predictions, users = await asyncio.gather(async_load_json(PREDICTIONS_FILE), async_load_json(USERS_FILE))
    user = await get_user(server_id, user_id)
    user_name = user.display_name
    user = users[server_id][user_id]
    prediction = predictions[server_id]["Predictions"][prediction_number]
    user_bets = prediction["user_bets"]
    new_bet = {"name": user_name, 
               "option": option_number, #Number string
               "amount": amount
               }
    if prediction["open"]:
        if user_id in user_bets:
            if user_bets[user_id]["option"] == option_number:
                user_bets[user_id]["amount"] += amount
            elif channel_id:
                await send_message("You can't bet for an option you are already betting against.", channel_id)
                return
        else:
            user_bets[user_id] = new_bet
        predictions[server_id]["Predictions"][prediction_number]["total_bets"] += amount
    else:
        await send_message("Betting for this prediction is currently closed.", channel_id)
        return
    user["wallet"] -= amount
    users[server_id][user_id]["total_currency_bet"] += amount
    await send_message("Bet successfully made.", channel_id)
    await asyncio.gather(async_save_json(PREDICTIONS_FILE, predictions), async_save_json(USERS_FILE, users))

async def remove_prediction_data(server_id, title = None, prediction_number = None): #Delete prediction from commerce.json #Will only receive either title or bet_number, never both
    predictions = await async_load_json(PREDICTIONS_FILE)
    if prediction_number:
        if prediction_number in predictions[server_id]["Predictions"]:
            del predictions[server_id]["Predictions"][str(prediction_number)]
        else:
            if DEBUG:
                print("[red]Invalid prediction_number provided.")
            return
    elif title:
        found_bet = False
        for bet in predictions[server_id]["Predictions"]:
            if bet["title"] == title:
                del bet
                found_bet = True
                break
        if not found_bet:
            if DEBUG:
                print("[red]Invalid prediction_title provided.")
            return
    await async_save_json(PREDICTIONS_FILE, predictions)

async def create_prediction(message = None, title = None, options = None, server_id = None): #!create_prediction (<name>) <number_of_options> (<option_1>) (<option_2>) (<option_3>)... #Options is list, used internally instead of command.
    if message:
        channel_id = message.channel.id
        server_id = str(message.guild.id)
        pattern = r"!create_prediction\s+\(([^)]+)\)\s+(\d+)((?:\s+\([^)]+\))+)"
        match = re.match(pattern, message.content)
        if not match:
            await send_message("Invalid parameters. [SYNTAX] !create_prediction (<title>) <number_of_options> (<option_1>) (<option_2>) (<option_3>)...", channel_id)
            return
        title = match.group(1).strip()
        predictions = await async_load_json(PREDICTIONS_FILE)
        for id, prediction in predictions[server_id]["Predictions"].items():
            if prediction["title"].lower() == title.lower():
                await send_message(f"Invalid Parameters. A prediction with the title {title} already exists, please try again.", channel_id)
                return
        num_options = int(match.group(2))
        options_str = match.group(3)

        options_list = re.findall(r"\(([^)]+)\)", options_str)
        if len(options_list) != num_options:
            if DEBUG:
                print(f"[red]Invalid number of parameters. User stated {num_options} options, but provided {len(options_list)}")
            await send_message(f"Invalid Parameters. User stated {num_options} options, but provided {len(options_list)}!", channel_id)
            return
        options = {i + 1: option for i, option in enumerate(options_list)}

    if all([title, options, server_id]):
        await add_prediction_to_json(title, options, server_id)
        await send_message(f"Prediction: \"{title}\" was created.", channel_id)
    else:
        if DEBUG:
            print(f"[red]Some parameters empty, can't create prediction.")
        return

async def close_prediction(message = None, bet_number = None, server_id = None, channel_id = None): #!close_prediction <name OR id>
    predictions = await async_load_json(PREDICTIONS_FILE)
    bet = message.content.strip("!close_prediction").strip()
    server_id = str(message.guild.id)
    channel_id = message.channel.id
    if not bet:
        await send_message("Invalid parameters. [SYNTAX] !close_prediction <title_of_prediction OR prediction_id>", channel_id)
    if not bet.isdigit():
        bet_number = await get_prediction_number(bet, server_id)
        if not bet_number:
            await send_message(f"Prediction **{bet}** not found!", channel_id)
            return
    else:
        bet_number = bet
    if bet_number in predictions[server_id]["Predictions"]:
        if predictions[server_id]["Predictions"][bet_number]["open"]:
            predictions[server_id]["Predictions"][bet_number]["open"] = False
            title = predictions[server_id]["Predictions"][bet_number]["title"]
            await send_message(f"Betting on {title} is now closed.", channel_id)

    await async_save_json(PREDICTIONS_FILE, predictions)

async def get_prediction_number(title, server_id):
    commerce = await async_load_json(PREDICTIONS_FILE)
    for k, prediction in commerce[server_id]["Predictions"].items():
        if prediction["title"].lower() == title.lower():
            return k

async def parse_resolve_command(message):
    """
    Parses a resolve command of the form:
    !resolve_prediction <number or (name)> <number or (option_name)>
    Returns a tuple: (bet_number or bet_name, option_number or option_name)
    """
    content = message.content.strip()
    pattern = r"!resolve_prediction\s+(?:(\d+)|\(([^)]+)\))\s+(?:(\d+)|\(([^)]+)\))"
    match = re.match(pattern, content)
    if not match:
        if DEBUG:
            print("[red]Invalid syntax. [SYNTAX] !resolve_prediction <number or (name)> <number or (option_name)>")
        return False

    bet_number = match.group(1)
    bet_name = match.group(2)

    option_number = match.group(3)
    option_name = match.group(4)

    arg1 = bet_number if bet_number else bet_name.strip()
    arg2 = option_number if option_number else option_name.strip()
    return (arg1, arg2)
    
async def resolve_prediction(message = None, bet_number = None, winning_option = None, server_id = None, channel_id = None): #!resolve_prediction <number(optional)>or(<name_optional>) (<winning_option_name_or_number>)
    predictions = await async_load_json(PREDICTIONS_FILE)
    if message:
        args = await parse_resolve_command(message)
        channel_id = message.channel.id
        server_id = str(message.guild.id)
        if not args:
            await send_message("Invalid syntax. [SYNTAX] !resolve_prediction <number or (name)> <number or (option_name)>", channel_id)
            return
        if args[0].isdigit():
            bet_number = args[0]
        else:
            for k, prediction in predictions[server_id]["Predictions"].items():
                if prediction["title"].lower() == args[0].lower():
                    bet_number = k
        winning_option = args[1]
        if not winning_option.isdigit():
            for k, option in predictions[server_id]["Predictions"][bet_number]["options"].items():
                if option.lower() == winning_option.lower():
                    winning_option = k
    if bet_number not in predictions[server_id]["Predictions"] or not all([bet_number, winning_option, server_id, channel_id]) or winning_option not in predictions[server_id]["Predictions"][bet_number]["options"]:
        await send_message("Prediction invalid.", channel_id)
        return
    embed = await payout(bet_number, winning_option, server_id)
    predictions = await async_load_json(PREDICTIONS_FILE)
    del predictions[server_id]["Predictions"][bet_number]
    await async_save_json(PREDICTIONS_FILE, predictions)
    await send_embed_message(embed, channel_id)

async def parse_bet_command(message):
    """
    Parses a bet command of the form:
    !bet <bet_number or (bet_name)> <amount_int> <option_number or (option_name)>
    Returns a tuple: (bet_number or bet_name, amount, option_number or option_name)
    """

    content = message.content.strip()
    # Pattern: first arg is number or (string), second is int, third is number or (string)
    pattern = r"!bet\s+(?:(\d+)|\(([^)]+)\))\s+(\d+)\s+(?:(\d+)|\(([^)]+)\))"
    match = re.match(pattern, content)
    if not match:
        await send_message("Invalid syntax. [SYNTAX] !bet <bet_number or (bet_name)> <amount_int> <option_number or (option_name)>", message.channel.id)
        return None

    bet_number = match.group(1)
    bet_name = match.group(2)

    amount = int(match.group(3))

    option_number = match.group(4)
    option_name = match.group(5)

    arg1 = bet_number if bet_number else bet_name.strip()
    arg3 = option_number if option_number else option_name.strip()
    return (arg1, amount, arg3)

async def handle_bet(message): #!bet <bet_number(optional)>or(<bet_name(optional)>) <amount_int> <option_int(optional)>or(<option_name>)
    args = await parse_bet_command(message)
    if not args:
        return
    bet_number, amount, option_number = args
    channel_id = message.channel.id
    server_id = str(message.guild.id)
    user_id = str(message.author.id)
    predictions, users = await asyncio.gather(async_load_json(PREDICTIONS_FILE), async_load_json(USERS_FILE))
    user = users[server_id][user_id]
    if amount:
        if user["wallet"] < amount:
            await send_message("You do not have enough money in your wallet.", channel_id)
            return
    if not bet_number.isdigit():
        matched_key = None
        for key, prediction in predictions[server_id]["Predictions"].items():
            if prediction["title"].lower() == bet_number.lower():
                matched_key = key
                break
        if matched_key is None:
            await send_message("No prediction found with that title.", channel_id)
            return
        bet_number = matched_key
    prediction = predictions[server_id]["Predictions"][bet_number]
    if not prediction:
        await send_message("Prediction not found.", channel_id)
        return 
    if not option_number.isdigit():
        matched_option = None
        for key, option in prediction["options"].items():
            if option.lower() == option_number.lower():
                matched_option = key
                break
        if matched_option is None:
            await send_message("Option not found in prediction.", channel_id)
            return
        option_number = matched_option

    await add_user_bet(server_id, user_id, bet_number, option_number, amount, channel_id)

async def payout(bet_number, winning_option, server_id):
    predictions, users = await asyncio.gather(
        async_load_json(PREDICTIONS_FILE), async_load_json(USERS_FILE)
    )

    prediction = predictions[server_id]["Predictions"][bet_number]
    user_bets = prediction["user_bets"]
    users_stats = users[server_id]

    total_amount_bet = prediction["total_bets"]
    options_count = len(prediction["options"])
    bonus_pool = 100 * options_count
    total_pool = total_amount_bet + bonus_pool

    payout_str = ""
    total_bet_on_winner = sum(
        user["amount"] for user in user_bets.values() if user["option"] == winning_option
    )

    # No one bet on the winning option
    if total_bet_on_winner == 0:
        embed = discord.Embed(
            title=f"🏆 {prediction['title'].title()} Results",
            description=f"**Winner:** {prediction['options'][winning_option]}\n\n😔 No one bet on the winning option.",
            color=discord.Color.dark_red()
        )
        embed.set_footer(text="Better luck next time!")
        return embed

    # Process losers
    for user_id, user in user_bets.items():
        if user["option"] != winning_option:
            users_stats[user_id]["total_currency_lost"] += user["amount"]
            users_stats[user_id]["bets_lost"] += 1
            users_stats[user_id]["profit"] = (
                users_stats[user_id]["total_currency_won"]
                - users_stats[user_id]["total_currency_lost"]
            )

    # Process winners
    for user_id, user in user_bets.items():
        if user["option"] != winning_option:
            continue

        user_amount = user["amount"]
        share = user_amount / total_bet_on_winner
        winnings = user_amount + round(share * (total_pool - total_bet_on_winner))
        user_name = user["name"]

        users_stats[user_id]["wallet"] += winnings
        users_stats[user_id]["bets_won"] += 1
        users_stats[user_id]["total_currency_won"] += winnings
        users_stats[user_id]["profit"] = (
            users_stats[user_id]["total_currency_won"]
            - users_stats[user_id]["total_currency_lost"]
        )

        payout_str += (
            f"• **{user_name}** won `${winnings:,}` "
            f"(bet `${user_amount:,}`, share `{share:.2%}`)\n"
        )

        if DEBUG:
            print(f"[green]{user_name} won {winnings} (bet {user_amount}, share {share:.2%})")

    # Final embed
    embed = discord.Embed(
        title=f"🏆 {prediction['title'].title()} Results",
        description=f"**Winner:** {prediction['options'][winning_option]}\n\n💰 **Payouts:**",
        color=discord.Color.gold()
    )
    embed.add_field(name="Earnings", value=payout_str or "No one won any money!", inline=False)
    embed.set_footer(text="Thanks for betting!")

    await asyncio.gather(
        async_save_json(PREDICTIONS_FILE, predictions),
        async_save_json(USERS_FILE, users)
    )
    return embed




async def get_predictions(message):
    predictions_file = await async_load_json(PREDICTIONS_FILE)
    server_id, user_id = await get_message_ids(message)
    server_id = str(server_id)
    user_id = str(user_id)
    channel_id = message.channel.id

    predictions = predictions_file[server_id]["Predictions"]
    if not predictions:
        await send_message("There are currently no predictions.", channel_id)
        return

    embeds = []

    for p_key, prediction in predictions.items():
        options_str = ""
        option_totals = {key: 0 for key in prediction["options"].keys()}
        total_bets = prediction.get("total_bets", 0)

        for user_data in prediction.get("user_bets", {}).values():
            option_id = user_data["option"]
            amount = user_data["amount"]
            if option_id in option_totals:
                option_totals[option_id] += amount

        for o_key, option_text in prediction["options"].items():
            bet_amount = option_totals[o_key]
            odds = (bet_amount / total_bets * 100) if total_bets > 0 else 0.0
            options_str += f"{o_key}. {option_text} — 💰 {bet_amount} ({odds:.1f}%)\n"

        status = "Open" if prediction.get("open") else "Closed"

        embed = discord.Embed(
            title=f"Prediction: {prediction['title']}",
            description=f"**Prediction ID:** {p_key}\n**Status:** {status}",
            color=discord.Color.blurple()
        )
        embed.add_field(name = "Options", value = options_str or "None", inline = False)
        embeds.append(embed)

    if len(embeds) == 1:
        await send_embed_message(embed, channel_id)
    else:
        await send_batch_embeds(embeds, channel_id)

async def reward_user(message):
    args = message.content.strip("!reward").strip().split()
    server_id = str(message.guild.id)
    if not args or len(args) < 2:
        await send_message("Invalid Syntax. [SYNTAX] !reward <amount> <user_name or user_id or user_display_name>", message.channel.id)
        return
    try:
        amount = int(args[0])
    except Exception as e:
        await send_message("Invalid Syntax. [SYNTAX] !reward <amount> <user_name or user_id or user_display_name>", message.channel.id)
        return
    user_name = " ".join(args[1:]).strip()

    users = await async_load_json(USERS_FILE)
    if user_name.isdigit():
        if user_name in users[server_id]:
            users[server_id][user_name]["wallet"] += amount
            await async_save_json(USERS_FILE, users)
            await send_message(f"{amount} successfully added to {users[server_id][str(user_name)]["display_name"]}'s wallet.", message.channel.id)
            return
    user_id = await get_user_id_from_username(server_id, user_name)
    if not user_id:
        await send_message("Could not find a user by that name.", message.channel.id)
        return
    if str(user_id) not in users[server_id]:
        await send_message("Could not find user. Have the user send !wallet command to generate a wallet.", message.channel.id)
        return
    users[server_id][str(user_id)]["wallet"] += amount
    await async_save_json(USERS_FILE, users)
    await send_message(f"{amount} successfully added to {users[server_id][str(user_id)]["display_name"]}'s wallet.", message.channel.id)

async def purchase_stock(message = None, stock_name = None, quanitity = None, user_id = None, server_id = None):
    return

async def set_enabled_commands(message):
    global USER_COMMANDS
    global MODERATOR_COMMANDS
    if USER_COMMANDS == [] and MODERATOR_COMMANDS == []:
        settings = await async_load_json(SETTINGS_FILE)
        server_id = str(message.guild.id)
        user_commands = settings[server_id]["User Commands"]
        privileged_commands = settings[server_id]["Privileged Commands"]
        for c_key, command in user_commands.items():
            if c_key in LIST_OF_COMMANDS and command:
                USER_COMMANDS.append(c_key)
        for c_key, command in privileged_commands.items():
            if c_key in LIST_OF_COMMANDS and command:
                MODERATOR_COMMANDS.append(c_key)
    return

async def handle_help(message):
    await message.channel.send(f"{USER_COMMANDS, MODERATOR_COMMANDS if await validate_user_permission(message.guild.id, message.author.id) else USER_COMMANDS}")

async def handle_wallet(message):
    server_id = str(message.guild.id)
    user_id = str(message.author.id)
    users = await async_load_json(USERS_FILE)
    wallet = users[server_id][user_id]["wallet"]
    await send_message(f"Your wallet balance is `${wallet}`.", message.channel.id)

async def ensure_file_exists(filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)  # Ensure parent directory exists
    if not os.path.exists(filepath):
        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write(json.dumps({}, indent=4))
        if DEBUG:
            print(f"[yellow]JSON not found. {filepath} was created")

async def populate_data_folder():
    for file in FILEPATHS:
        await ensure_file_exists(file)
        if DEBUG:
            print(f"[green]{file} checked or created.")

# Load/Save helpers
async def async_load_json(path):
    await ensure_file_exists(path)
    async with aiofiles.open(path, "r", encoding="utf-8") as f:
        content = await f.read()
        if not content.strip():
            return {}
        return json.loads(content)

async def async_save_json(path, data):
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(data, indent=4))

async def handle_message(message):
    server_id, user_id = await get_message_ids(message)
    await add_server_to_jsons(str(server_id))
    if message.content.startswith("!"):
        COMMAND_QUEUE.append(message)

async def check_for_command(message):
    await set_enabled_commands(message)
    users = await async_load_json(USERS_FILE)
    server_id, user_id = await get_message_ids(message)
    if str(user_id) not in users[str(server_id)]:
        await add_user_to_json(str(server_id), str(user_id))
        users = await async_load_json(USERS_FILE)
    elif users[str(server_id)][str(user_id)]["display_name"] != message.author.display_name:
        await update_display_name(str(server_id), str(user_id), message.author.display_name)
        users = await async_load_json(USERS_FILE)
    args = message.content.split()
    command = args[0].lower()
    if command in USER_COMMANDS or command == "!help" or command == "!commands":
        if command == "!help" or command == "!commands":
            await handle_help(message)
            return
        elif command == "!wallet": #!wallet
            await handle_wallet(message) #Tested and working
            return
        elif command == "!bet": #!bet <bet_number or (bet_name)> <amount_int> <option_number or (option_name)>
            await handle_bet(message) #Tested and Working
            return
        elif command == "!shop": #!shop
            await handle_shop(message) #Tested and Working
            return
        elif command == "!buy": #!buy (<name_of_item>) <optional_quantity>
            await handle_buy(message) #Tested and Working
            return
        elif command == "!sell": #!sell (<name_of_item>) <optional_quantity>
            await handle_sell(message) #Tested and Working
            return
        elif command == "!predictions": #!predictions
            await get_predictions(message) #Tested and Working
            return
        elif command == "!auction_item": #!auction_item (<name_of_item>) <quantity> <starting_bid> <number_of_minutes>
            await handle_auction_item(message) #Tested and Working
            return
        elif command == "!auctions": #!auctions
            await handle_auctions_command(message) #Tested and Working
            return
        elif command == "!bid": #!bid <auction_id> <amount_of_money>
            await handle_bid(message) #Tested and Working
            return
        elif command == "!inventory": #!inventory
            await handle_inventory(message) #Tested and Working
            return
        elif command == "!my_bets": #Tested and Working
            await handle_my_bets(message)
            return
    elif command in MODERATOR_COMMANDS and await validate_user_permission(server_id, user_id):
        if command == "!reward": #!reward <amount> <user_name or user_id or user_display_name>
            await reward_user(message) #Tested and Working
            return
        elif command == "!create_auction": #!create_auction (<name_of_item>) <quantity> <starting_bid> <number_of_minutes>
            await handle_create_auction(message) #Tested and Working
            return#this version of the command does not require the item to exist in anyone's inventory to be used, only usable by moderators
        elif command == "!create_prediction": #!create_prediction (<name>) <number_of_options> (<option_1>) (<option_2>) (<option_3>)...
            await create_prediction(message) #Tested and Working
            return
        elif command == "!close_prediction": #!close_prediction (<name>)
            await close_prediction(message) #Tested and Working
            return
        elif command == "!resolve_prediction": #!resolve_prediction <number(optional)>or(<name_optional>) (<winning_option_name_or_number>)
            await resolve_prediction(message) #Tested and Working
            return
        elif command == "!create_shop_item": #!create_shop_item (<name_of_item>) <price> <optional_quantity> <optional_refresh_time_days>
            await handle_create_shop_item(message) #Tested and Working
            return
        elif command == "!delete_shop_item": #!delete_shop_item (<name_of_item>)
            await handle_delete_shop_item(message) #Tested and Working
            return
        elif command == "!edit_shop_item": #!edit_shop_item (<name_of_item>) (<name|price|quantity|refresh_time>) (<new_value>) [...] e.g !edit_shop_item (Cool Item) (name) (Even Cooler Item) (price) (500) 
            await handle_edit_shop_item(message) #Tested and Working
            return
        elif command == "!reset_user_inventory": #!reset_user_inventory (<name_of_user or user_id>)
            await handle_reset_user_inventory(message) #Tested and Working
            return
        elif command == "!reset_user": #!reset_user (<name_of_user or user_id>)    #Currently does not reset bets done by the user on predictions
            await handle_reset_user(message) #Tested and Working
            return
        elif command == "!purge_deprecated_users": #!purge_deprecated_users
            await handle_purge_deprecated_users(message) #Tested and Working
            return
        elif command == "!set_default_channel": #!set_default_channel <OPTIONAL_channel_id>
            await handle_set_default_channel(message) #Tested and Working
            return
        elif command == "!toggle_command": #!toggle_command (!command) (true/false) [...]
            await handle_toggle_command(message) #Tested and Working
            return
        
async def handle_shop(message):
    shop = await async_load_json(SHOP_FILE)
    server_id = str(message.guild.id)
    channel_id = message.channel.id
    server_data = shop.get(str(server_id))

    if not server_data or not server_data.get("Items"):
        await send_message("The shop is currently empty.", channel_id)
        return
    

    embed = discord.Embed(
        title="🛒 Shop Items",
        description="Here are the available items in the shop:",
        color=discord.Color.green()
    )

    for item_id, item in server_data["Items"].items():
        if not item.get("active", False):
            continue
        name = item.get("name", "Unnamed")
        price = item.get("price", "???")
        quantity = item.get("quantity", "???")
        refresh = item.get("refresh_time", "Never")

        # Determine restock status
        restock_msg = ""
        try:
            qty = int(quantity)
        except ValueError:
            qty = -1  # Unlimited or non-numeric

        try:
            refresh_days = int(refresh)  # Convert days to minutes
        except ValueError:
            refresh_days = None

        if qty == 0 and refresh_days:
            restock_msg = f" (Restocks every {refresh_days} days)"
        elif qty == 0:
            restock_msg = " (Out of stock)"

        embed.add_field(
            name=f"{name}",
            value=f"💰 Price: {price}\n📦 Stock: {quantity}{restock_msg}",
            inline=False
        )

    await send_embed_message(embed, channel_id)

async def handle_inventory(message):
    server_id = str(message.guild.id)
    user_id = str(message.author.id)
    channel_id = message.channel.id
    users = await async_load_json(USERS_FILE)
    user_data = users.get(server_id, {}).get(user_id)
    if not user_data or not user_data.get("inventory"):
        embed = discord.Embed(
            title=f"🧾 {await get_display_name(int(server_id), int(user_id))}'s Inventory",
            description="You have no items in your inventory.",
            color=discord.Color.greyple()
        )
        await send_embed_message(embed, channel_id)
        return

    inventory = user_data["inventory"]
    embed = discord.Embed(
        title=f"🧾 {user_data['display_name']}'s Inventory",
        color=discord.Color.blurple()
    )

    for item_id, item in inventory.items():
        name = item["name"]
        quantity = item["quantity"]
        value = item["value"]
        embed.add_field(
            name=f"📦 {name}",
            value=f"Quantity: **{quantity}**\nValue per item: `${value}`\nTotal value: `${value * quantity}`",
            inline=False
        )

    await send_embed_message(embed, channel_id)
    

async def handle_auctions_command(message):
    shop = await async_load_json(SHOP_FILE)
    server_id = str(message.guild.id)
    auctions = shop.get(server_id, {}).get("Auctions", {})
    if not auctions:
        embed = discord.Embed(
            title="🛒 Current Auctions",
            description="There are no active auctions at the moment.",
            color=discord.Color.greyple()
        )
        return embed

    embed = discord.Embed(
        title="🛒 Current Auctions",
        color=discord.Color.blurple()
    )

    now = datetime.now(timezone.utc)

    for auction_id, auction in auctions.items():
        item = auction["item"]
        quantity = auction["quantity"]
        auction_end = datetime.fromisoformat(auction["auction_end"])
        remaining = auction_end - now

        if remaining.total_seconds() <= 0:
            time_left = "Expired"
        elif remaining.total_seconds() < 3600:
            time_left = f"{round(remaining.total_seconds() / 60)} minute(s)"
        elif remaining.total_seconds() < 86400:
            time_left = f"{round(remaining.total_seconds() / 3600)} hour(s)"
        else:
            time_left = f"{round(remaining.total_seconds() / 86400)} day(s)"

        auctioner_user = await get_display_name(int(server_id), int(auction["user_id"]))
        highest_bid = auction["current_bid"]
        highest_bidder_id = auction["current_highest_bidder_id"]
        highest_bidder = await get_display_name(int(server_id), int(highest_bidder_id)) if highest_bidder_id else "None"
        bid_count = auction["number_of_bids"]

        embed.add_field(
            name=f"🆔 Auction ID: `{auction_id}` • {quantity}x {item}",
            value=(
                f"• 🧑‍💼 Auctioned by: **{auctioner_user}**\n"
                f"• 💰 Current Bid: `${highest_bid:,}`\n"
                f"• 🥇 Highest Bidder: **{highest_bidder}**\n"
                f"• 🔢 Number of Bids: `{bid_count}`\n"
                f"• ⏳ Time Left: **{time_left}**"
            ),
            inline=False
        )

    embed.set_footer(text="Use !bid <auction_id> <amount> to place your bid!")
    await send_embed_message(embed, message.channel.id)

async def handle_buy(message):
    shop, users = await asyncio.gather(async_load_json(SHOP_FILE), async_load_json(USERS_FILE))
    content = message.content.strip()
    channel_id = message.channel.id
    server_id = str(message.guild.id)
    user_id = str(message.author.id)
    users_data = users.get(server_id)
    pattern = r"^!buy\s+\(([^)]+)\)(?:\s+(\d+))?$"
    match = re.match(pattern, content)
    if not match:
        await send_message("Invalid syntax. [SYNTAX] !buy (<name_of_item>) <OPTIONAL_quantity>", channel_id)
        return
    
    if match:
        name = match.group(1)
        quantity = int(match.group(2)) if match.group(2) else 1

    server_data = shop.get(server_id)

    if not server_data or not server_data.get("Items"):
        await send_message(f"{name} is not currently in the shop.", channel_id)
        return
    
    found = False
    for item_id, item in server_data["Items"].items():
        if item["name"].lower() == name.lower():
            found = True
            if item["price"] == "Free":
                price = 0
                value = 0
            else:
                price = item["price"] * quantity
                value = int(round(item["price"] * 0.25))
            if price > users_data[user_id]["wallet"]:
                await send_message(f"You do not have enough in your wallet to purchase {quantity} {name}{"s." if quantity > 1 else "."}", channel_id)
                return
            elif item["quantity"] != "Unlimited":
                if item["quantity"] < quantity:
                    await send_message(f"There are not enough {name}s in stock.", channel_id)
                    return
                item["quantity"] -= quantity

            users_data[user_id]["wallet"] -= price
            await async_save_json(USERS_FILE, users)
            await add_item_to_inventory(user_id, item_id, value, name, quantity, server_id)
            await async_save_json(SHOP_FILE, shop)

    if found:
        await send_message(f"{quantity} {name}{"s" if quantity > 1 else ""} successfully purchased.", channel_id)
    else:
        await send_message(f"{name} is not currently in the shop.", channel_id)

async def add_item_to_inventory(user_id, item_id, value, name, quantity, server_id):
    users = await async_load_json(USERS_FILE)

    if item_id not in users[server_id][user_id]["inventory"]:
        users[server_id][user_id]["inventory"][item_id] = {
            "name": name,
            "quantity": quantity,
            "value": value
        }
    else:
        users[server_id][user_id]["inventory"][item_id]["quantity"] += quantity
        if users[server_id][user_id]["inventory"][item_id]["name"] != name:
            users[server_id][user_id]["inventory"][item_id]["name"] = name
        if users[server_id][user_id]["inventory"][item_id]["value"] != value:
            users[server_id][user_id]["inventory"][item_id]["value"] = value

    await async_save_json(USERS_FILE, users)

async def handle_sell(message):
    users = await async_load_json(USERS_FILE)
    content = message.content.strip()
    channel_id = message.channel.id
    server_id = str(message.guild.id)
    user_id = str(message.author.id)
    users_data = users.get(server_id)
    pattern = r"^!sell\s+\(([^)]+)\)(?:\s+(\d+))?$"
    match = re.match(pattern, content)
    if not match:
        await send_message("Invalid syntax. [SYNTAX] !sell (<name_of_item>) <OPTIONAL_quantity>", channel_id)
        return
    
    if match:
        name = match.group(1)
        quantity = int(match.group(2)) if match.group(2) else 1

    found = False
    for item_id, item in users_data[user_id]["inventory"].items():
        if item["name"].lower() == name.lower():
            found = True
            if item["quantity"] < quantity:
                await send_message(f"You do not have {quantity} {name}s.", channel_id)
                return
            worth = item["value"] * quantity
            users_data[user_id]["wallet"] += worth
            await async_save_json(USERS_FILE, users)
            await remove_item_from_inventory(user_id, item_id, name, quantity, server_id)
    
    if found:
        await send_message(f"Successfully sold {quantity} {name}{"s" if quantity > 1 else ""} for a total of {worth}!", channel_id)
    else:
        await send_message(f"You do not have any {name}s.", channel_id)
                
async def remove_item_from_inventory(user_id, item_id, name, quantity, server_id):
    users = await async_load_json(USERS_FILE)
    if users[server_id][user_id]["inventory"][item_id]["quantity"] == quantity:
        del users[server_id][user_id]["inventory"][item_id]
    else:
        users[server_id][user_id]["inventory"][item_id]["quantity"] -= quantity
        if users[server_id][user_id]["inventory"][item_id]["name"] != name:
            users[server_id][user_id]["inventory"][item_id]["name"] = name
    
    await async_save_json(USERS_FILE, users)

async def handle_auction_item(message):
    users = await async_load_json(USERS_FILE)
    user_id = str(message.author.id)
    server_id = str(message.guild.id)
    channel_id = message.channel.id
    pattern = r"^!auction_item\s+\(([^)]+)\)\s+(\d+)\s+(\d+)\s+(\d+)$"
    match = re.match(pattern, message.content.strip())
    if not match:
        await send_message("Invalid syntax. [SYNTAX] !auction_item (<name_of_item>) <quantity> <starting_bid> <number_of_minutes>", channel_id)
        return

    item_name = match.group(1)
    quantity = int(match.group(2))
    starting_bid = int(match.group(3))
    duration_minutes = int(match.group(4))
    item_id = None
    value = None

    users_inventory = users[server_id][user_id]["inventory"]
    found = False
    for id, item in users_inventory.items():
        if item["name"] == item_name:
            found = True
            item_id = id
            value = item["value"]
            if item["quantity"] < quantity:
                await send_message(f"You do not have {quantity} {item_name}s.", channel_id)
                return
            elif item["quantity"] == quantity:
                del item
                break
            else:
                item["quantity"] -= quantity
                break
    
    if found:
        await async_save_json(USERS_FILE, users)
        await create_auction(item_name, item_id, quantity, starting_bid, value, duration_minutes, user_id, server_id)
        await send_message(f"Auction created for {quantity} {item_name}{"s" if quantity > 1 else ""} with starting bid of {starting_bid}. Auction ends in {f"{duration_minutes} minutes." if duration_minutes < 60 else f"{duration_minutes / 60} hour{"s." if duration_minutes / 60 != 1 else "."}"}", channel_id)
    else:
        await send_message(f"You do not have any {item_name}s.", channel_id)


async def auction_timer(server_id, auction_id, end_time):
    end_utc = datetime.fromisoformat(end_time)
    now_utc = datetime.now(timezone.utc)
    seconds_remaining = (end_utc - now_utc).total_seconds()
    seconds_remaining = int(seconds_remaining)
    if seconds_remaining <= 0:
        await resolve_auction(server_id, auction_id)
        return
    if DEBUG:
        print(f"[green]Seconds remaining for auction: {seconds_remaining}")

    await asyncio.sleep(seconds_remaining)
    await resolve_auction(server_id, auction_id)


async def resolve_auction(server_id, auction_id):
    auction_id = str(auction_id)
    shop, users, settings = await asyncio.gather(async_load_json(SHOP_FILE), async_load_json(USERS_FILE), async_load_json(SETTINGS_FILE))
    auction = shop[server_id]["Auctions"][auction_id]
    
    item = auction["item"]
    item_id = auction["item_id"]
    quantity = auction["quantity"]
    value = auction["value"]
    auctioner_user_id = auction["user_id"]
    number_of_bids = auction["number_of_bids"]
    highest_bid = auction["current_bid"]
    highest_bid_user_id = auction["current_highest_bidder_id"]
    bids = auction.get("bids", {})

    default_channel = settings[server_id]["Default Commerce Channel ID"]

    success = False
    winner_id = None
    winner_user = None
    early_failure_reason = ""

    # No bids
    if number_of_bids == 0:
        if auctioner_user_id:
            early_failure_reason = f"🕰️ The auction for {quantity} {item}{'s' if quantity > 1 else ''} has come to an end. No bids were placed, so the item{'s' if quantity > 1 else ''} return{'s' if quantity == 1 else ''} to the owner."
        else:
            early_failure_reason = f"🕰️ The auction for {quantity} {item}{'s' if quantity > 1 else ''} has come to an end. No bids were placed, so the item{'s' if quantity > 1 else ''} vanish into the aether."
    # One bid, but bidder can't pay
    elif highest_bid_user_id in users[server_id] and users[server_id][highest_bid_user_id]["wallet"] < highest_bid:
        if number_of_bids == 1:
            if auctioner_user_id:
                early_failure_reason = f"🕰️ The auction for {quantity} {item}{'s' if quantity > 1 else ''} has come to an end. The highest bidder couldn't afford it, so the item{'s' if quantity > 1 else ''} return{'s' if quantity == 1 else ''} to the owner."
            else:
                early_failure_reason = f"🕰️ The auction for {quantity} {item}{'s' if quantity > 1 else ''} has come to an end. The highest bidder couldn't afford it, so the item{'s' if quantity > 1 else ''} vanish into the aether."
        else:
            # Multiple bids: try to find the next highest bidder with enough wallet
            for bid_id, bid in reversed(list(bids.items())):
                user_id = bid["user_id"]
                amount = bid["amount"]
                if users[server_id].get(user_id, {}).get("wallet", 0) >= amount:
                    winner_id = user_id
                    winner_user = await get_display_name(int(server_id), int(winner_id))
                    highest_bid = amount
                    users[server_id][user_id]["wallet"] -= amount
                    success = True
                    break
            if not success:
                if auctioner_user_id:
                    early_failure_reason = f"🕰️ The auction for {quantity} {item}{'s' if quantity > 1 else ''} has come to an end. None of the bidders had enough in their wallets, so the item{'s' if quantity > 1 else ''} return{'s' if quantity == 1 else ''} to the owner."
                else:
                    early_failure_reason = f"🕰️ The auction for {quantity} {item}{'s' if quantity > 1 else ''} has come to an end. None of the bidders had enough in their wallets, so the item{'s' if quantity > 1 else ''} vanish into the aether."
    # Highest bidder can pay
    elif users[server_id].get(highest_bid_user_id, {}).get("wallet", 0) >= highest_bid:
        winner_id = highest_bid_user_id
        winner_user = await get_display_name(int(server_id), int(winner_id))
        users[server_id][winner_id]["wallet"] -= highest_bid
        users[server_id][auctioner_user_id]["wallet"] += highest_bid
        success = True

    # If auction failed, return item to original owner
    if not success:
        if auctioner_user_id:
            inventory = users[server_id][auctioner_user_id].setdefault("inventory", {})
            if item_id in inventory:
                inventory[item_id]["quantity"] += quantity
            else:
                inventory[item_id] = {
                    "name": item,
                    "quantity": quantity,
                    "value": value
                }
            # Send failure message
            if default_channel:
                await send_message(early_failure_reason, default_channel)
            else:
                if DEBUG:
                    print("[yellow]DEFAULT CHANNEL NOT SET!", early_failure_reason)
        else:
            if default_channel:
                await send_message(early_failure_reason, default_channel)
            else:
                if DEBUG:
                    print("[yellow]DEFAULT CHANNEL NOT SET!", early_failure_reason)
    else:
        # Send winner announcement
        success_message = (
            f"🕰️ The auction for {quantity} {item}{'s' if quantity > 1 else ''} has officially ended!\n"
            f"🏆 The highest valid bid was placed by {winner_user} for ${highest_bid:,}. Congratulations!"
        )
        if default_channel:
            await send_message(success_message, default_channel)
        else:
            if DEBUG:
                print("[yellow]DEFAULT CHANNEL NOT SET!", success_message)

    # Final cleanup: delete the auction and save
    del shop[server_id]["Auctions"][auction_id]
    await asyncio.gather(
        async_save_json(SHOP_FILE, shop),
        async_save_json(USERS_FILE, users)
    )


async def handle_my_bets(message):
    user_id = str(message.author.id)
    server_id = str(message.guild.id)
    channel_id = message.channel.id
    user_bets_summary = []

    predictions = await async_load_json(PREDICTIONS_FILE)


    server_predictions = predictions.get(server_id, {}).get("Predictions", {})

    for pred_id, prediction in server_predictions.items():
        if prediction.get("open", False):  # Only include open predictions
            user_bet = prediction.get("user_bets", {}).get(user_id)
            if user_bet:
                option_num = user_bet["option"]
                option_label = prediction["options"].get(option_num, "Unknown Option")
                amount = user_bet["amount"]
                title = prediction["title"]

                user_bets_summary.append(f"**{title}**\n🪙 Bet `{amount}` on **{option_label}**\n")

    if not user_bets_summary:
        embed = discord.Embed(
            title="📊 Your Current Bets",
            description="You have no active bets right now.",
            color=discord.Color.gold()
        )
    else:
        embed = discord.Embed(
            title="📊 Your Current Bets",
            description="\n".join(user_bets_summary),
            color=discord.Color.gold()
        )

    await send_embed_message(embed, channel_id)



async def create_auction(name, item_id, quantity, starting_bid, value, duration_minutes, user_id, server_id):
    shop = await async_load_json(SHOP_FILE)
    auction_id = shop[server_id]["Next Auction ID"]
    now_utc = datetime.now(timezone.utc)
    end_time_utc = now_utc + timedelta(minutes = duration_minutes)
    shop[server_id]["Auctions"][auction_id] = {
        "item": name,
        "item_id": item_id,
        "quantity": quantity,
        "current_bid": starting_bid,
        "value": value,
        "bids": {},
        "auction_end": end_time_utc.isoformat(),
        "user_id": user_id,
        "current_highest_bidder_id": None,
        "number_of_bids": 0
    }
    shop[server_id]["Next Auction ID"] += 1
    await async_save_json(SHOP_FILE, shop)
    asyncio.create_task(auction_timer(server_id, auction_id, end_time_utc.isoformat()))

async def handle_bid(message): #!bid <auction_id> <amount_of_money>
    channel_id = message.channel.id
    server_id = str(message.guild.id)
    user_id = str(message.author.id)
    pattern = r"^!bid\s+(\d+)\s+(\d+)"
    match = re.match(pattern, message.content.strip())
    if not match:
        await send_message("Invalid syntax. [SYNTAX] !bid <auction_id> <amount_of_money>", channel_id)
        return
    auction_id = match.group(1)
    shop = await async_load_json(SHOP_FILE)
    if auction_id in shop[server_id]["Auctions"]:
        if user_id == shop[server_id]["Auctions"][auction_id]["user_id"]:
            await send_message(f"You can not bid on your own auction.", channel_id)
        users = await async_load_json(USERS_FILE)
        amount = int(match.group(2))
        if user_id in users[server_id]:
            if users[server_id][user_id]["wallet"] < amount:
                await send_message(f"You do not have {amount} in your wallet, please try again.", channel_id)
                return
            else:
                if amount <= shop[server_id]["Auctions"][auction_id]["current_bid"]:
                    await send_message(f"Your bid needs to be higher than the current highest bid. Current highest bid: {shop[server_id]["Auctions"][auction_id]["current_bid"]}.", channel_id)
                    return
                else:
                    shop[server_id]["Auctions"][auction_id]["bids"][shop[server_id]["Auctions"][auction_id]["number_of_bids"] + 1] = {
                        "user_id": user_id,
                        "user_name": await get_display_name(server_id, int(user_id)),
                        "amount": amount,
                        "date/time": datetime.now(timezone.utc).isoformat()
                    }
                    shop[server_id]["Auctions"][auction_id]["number_of_bids"] += 1
                    shop[server_id]["Auctions"][auction_id]["current_bid"] = amount
                    shop[server_id]["Auctions"][auction_id]["current_highest_bidder_id"] = user_id
                    await async_save_json(SHOP_FILE, shop)
        else:
            if DEBUG:
                print("[red][ERROR] User not found in users.json. Was there an issue with the create_user method?")
    else:
        await send_message(f"Auction ID {auction_id} does not exist or has already ended, please try again.", channel_id)
        return
    await send_message(f"Bid of {amount} successful.", channel_id)

async def handle_create_auction(message): #!create_auction(<name_of_item>) <quantity> <starting_bid> <number_of_minutes>
    server_id = str(message.guild.id)
    channel_id = message.channel.id
    pattern = r"^!create_auction\s+\(([^)]+)\)\s+(\d+)\s+(\d+)\s+(\d+)$"
    match = re.match(pattern, message.content.strip())
    if not match:
        await send_message("Invalid syntax. [SYNTAX] !create_auction (<name_of_item>) <quantity> <starting_bid> <number_of_minutes>", channel_id)
        return

    item_name = match.group(1)
    quantity = int(match.group(2))
    starting_bid = int(match.group(3))
    duration_minutes = int(match.group(4))
    item_id = None
    value = starting_bid
    shop = await async_load_json(SHOP_FILE)
    items = shop[server_id]["Items"]
    found = False
    for id, item in items.items():
        if item["name"].lower() == item_name.lower():
            item_id = id
            item_name = item["name"] #normalizes the name
            value = int(round(item["price"] * 0.25))
            found = True
            break

    if not found:
        next_item_id = shop[server_id]["Next Shop ID"]
        shop[server_id]["Items"][next_item_id] = {
        "name": item_name,
        "price": starting_bid * 4,
        "quantity": "Unlimited",
        "refresh_time": "Never",
        "active": False
        }
        shop[server_id]["Next Shop ID"] += 1
        await async_save_json(SHOP_FILE, shop)

    await create_auction(item_name, item_id, quantity, starting_bid, value, duration_minutes, None, server_id)
    await send_message(f"Auction created for {quantity} {item_name}{"s" if quantity > 1 else ""} with starting bid of {starting_bid}. Auction ends in {f"{duration_minutes} minutes." if duration_minutes < 60 else f"{duration_minutes / 60} hour{"s." if duration_minutes / 60 != 1 else "."}"}", channel_id)
    

async def handle_create_shop_item(message): #!create_shop_item (<name_of_item>) <price> <optional_quantity> <optional_refresh_time_days>
    content = message.content.strip()
    channel_id = message.channel.id
    pattern = r"^!create_shop_item\s+\(([^)]+)\)\s+(\d+)\s*(\d+)?\s*(\d+)?$"
    match = re.match(pattern, content)
    if not match:
        await send_message("Invalid syntax. [SYNTAX] !create_shop_item (<name_of_item>) <price_int> <OPTIONAL_quantity> <OPTIONAL_refresh_time_in_days>", channel_id)
        return
    
    if match:
        name = match.group(1)
        price = int(match.group(2))
        quantity = int(match.group(3)) if match.group(3) else "Unlimited"
        refresh_time = int(match.group(4)) if match.group(4) else "Never"
    
    shop = await async_load_json(SHOP_FILE)
    server_id = message.guild.id
    for key, item in shop[str(server_id)]["Items"].items():
        if item["name"].lower() == name.lower():
            await send_message(f"{name} already exists in the shop. Use !edit_shop_item if you want to change it.", channel_id)
            return
    item_id = shop[str(server_id)]["Next Shop ID"]
    if price == 0:
        price = "Free"
    shop[str(server_id)]["Items"][item_id] = {
        "name": name,
        "price": price,
        "quantity": quantity,
        "refresh_time": refresh_time,
        "active": True
    }
    shop[str(server_id)]["Next Shop ID"] += 1
    await async_save_json(SHOP_FILE, shop)
    await send_message(f"{name} has been added to the shop.", channel_id)

async def handle_delete_shop_item(message): #!delete_shop_item (<name_of_item>)
    content = message.content.strip()
    channel_id = message.channel.id
    pattern = r"^!delete_shop_item\s+\(([^)]+)\)"
    match = re.match(pattern, content)
    if not match:
        await send_message("Invalid syntax. [SYNTAX] !delete_shop_item (<name_of_item>)", channel_id)
        return
    
    if match:
        name = match.group(1)

    shop = await async_load_json(SHOP_FILE)
    server_id = message.guild.id
    found = False
    for key, item in shop[str(server_id)]["Items"].items():
        if item["name"].lower() == name.lower():
            shop[str(server_id)]["Items"][key]["active"] = False
            found = True
            break
    if found:
        await async_save_json(SHOP_FILE, shop)
        await send_message(f"{name} successfully removed from the shop.", channel_id)
    else:
        await send_message(f"{name} is not currently in the shop.", channel_id)

async def handle_edit_shop_item(message):
    content = message.content.strip()
    channel_id = message.channel.id
    pattern = r"^!edit_shop_item\s+\(([^)]+)\)(?:\s+\(([^)]+)\)\s+\(([^)]+)\))+"
    match = re.match(pattern, content)
    changes_made = False
    changes_skipped = False
    if not match:
        await send_message("Invalid syntax. [SYNTAX] !edit_shop_item (<name_of_item>) (<name|price|quantity|refresh_time>) (<new_value>)... e.g !edit_shop_item (Cool Item) (name) (Even Cooler Item) (price) (500)", channel_id)
        return
    
    server_id = message.guild.id
    shop = await async_load_json(SHOP_FILE)

    
    if match:
        name = match.group(1)
        if DEBUG:
            print(name)

    found = False
    for key, item in shop[str(server_id)]["Items"].items():
        if name.lower() == item["name"].lower():
            item_id = key
            found = True
            break
    if not found:
        await send_message(f"{name} is not currently in the shop.", channel_id)
        return

    tail = content[match.end(1):]
    attr_val_pattern = r"\(([^)]+)\)\s+\(([^)]+)\)"
    attr_val_matches = re.findall(attr_val_pattern, tail)
    updates = {attr: val for attr, val in attr_val_matches}
    if DEBUG:
        print(updates)

    for attr, val in updates.items():
        if attr.lower() in ["name", "price", "quantity", "refresh_time"]:
            if not val.isdigit() and attr.lower() != "name":
                await send_message(f"{attr.capitalize()} needs to be a number.", channel_id)
                return
            if attr.lower() == "quantity" and val == "0":
                val = "Unlimited"
            elif attr.lower() == "refresh_time" and val == "0":
                val = "Never"
            elif attr.lower() == "price" and val == "0":
                val = "Free"
            elif attr.lower() != "name":
                val = int(val)
        else:
            changes_skipped = True
            continue
        shop[str(server_id)]["Items"][item_id][attr.lower()] = val
        changes_made = True

    shop[str(server_id)]["Items"][item_id]["active"] = True

    await async_save_json(SHOP_FILE, shop)
    if changes_made:
        if not changes_skipped:
            await send_message(f"{name} successfully edited.", channel_id)
        else:
            await send_message(f"{name} successfully edited. Some requested changes were invalid, and skipped.", channel_id)
    else:
        await send_message(f"There were no valid attributes to change in the command.", channel_id)

async def handle_reset_user_inventory(message):
    content = message.content.strip()
    channel_id = message.channel.id
    server_id = str(message.guild.id)
    pattern = r"^!reset_user_inventory\s+\(([^)]+)\)$"
    match = re.match(pattern, content)
    user_id = None
    user_name = None
    if not match:
        await send_message("Invalid syntax. [SYNTAX] !reset_user_inventory (<name_of_user OR user_id>)", channel_id)
        return
    
    if match.group(1).isdigit():
        user_id = match.group(1)
    else:
        user_name = match.group(1)

    users = await async_load_json(USERS_FILE)
    found = False
    if user_id:
        if user_id in users[server_id]:
            users[server_id][user_id]["inventory"] = {}
            found = True
            user_name = users[server_id][user_id]["display_name"]
    elif user_name:
        for uid, user_data in users[server_id].items():
            if user_data["display_name"].lower() == user_name.lower() or user_data["user_name"].lower() == user_name.lower():
                users[server_id][uid]["inventory"] = {}
                found = True
                user_name = user_data["display_name"]
                break

    if found:
        await send_message(f"{user_name}'s inventory has been cleared.", channel_id)
    else:
        await send_message(f"{user_name if user_name else user_id} was not found.", channel_id)
    await async_save_json(USERS_FILE, users) 

async def handle_reset_user(message):
    content = message.content.strip()
    channel_id = message.channel.id
    server_id = str(message.guild.id)
    pattern = r"^!reset_user\s+\(([^)]+)\)$"
    match = re.match(pattern, content)
    user_id = None
    user_name = None
    if not match:
        await send_message("Invalid syntax. [SYNTAX] !reset_user (<name_of_user OR user_id>)", channel_id)
        return
    
    if match.group(1).isdigit():
        user_id = match.group(1)
    else:
        user_name = match.group(1)

    users = await async_load_json(USERS_FILE)
    found = False
    if user_id:
        if user_id in users[server_id]:
            del users[server_id][user_id]
            found = True
    elif user_name:
        for uid, user_data in users[server_id].items():
            if user_data["display_name"].lower() == user_name.lower() or user_data["user_name"].lower() == user_name.lower():
                del users[server_id][uid]
                found = True
                user_id = uid
                break
    
    if found:
        await async_save_json(USERS_FILE, users)
        await add_user_to_json(server_id, user_id)
        if not user_name:
            user_name = await get_display_name(int(server_id), int(user_id))
        await send_message(f"{user_name} has been reset.", channel_id)
    else:
        await send_message(f"{user_name if user_name else user_id} was not found.", channel_id)
    #Currently does not reset bets done by the user on predictions

async def handle_purge_deprecated_users(message):
    server_id = str(message.guild.id)
    channel_id = message.channel.id
    guild = bot.get_guild(int(server_id))
    if not guild:
        if DEBUG:
            print(F"[red][ERROR] Could not fetch guild! Is Discord down?")
        return
    members = []
    try:
        async for member in guild.fetch_members(limit=None): members.append(member)
        current_member_ids = {str(member.id) for member in members}
    except Exception as e:
        if DEBUG:
            print(f"[red][ERROR] Failed to fetch members: {e}")
        return


    users = await async_load_json(USERS_FILE)
    if server_id not in users:
        await send_message("No user data found for this servercha.", channel_id)
        return
    
    removed_users = []
    for user_id in list(users[server_id].keys()):
        if user_id not in current_member_ids:
            del users[server_id][user_id]
            removed_users.append(user_id)

    await async_save_json(USERS_FILE, users)
    await send_message(f"Removed {len(removed_users)} user{"s" if len(removed_users) > 1 or len(removed_users) == 0 else ""} no longer in the server.", channel_id)

async def handle_set_default_channel(message):
    content = message.content
    settings = await async_load_json(SETTINGS_FILE)
    args = content.split()
    if len(args) > 1:
        if args[1].isdigit():
            channel_id = int(args[1])
            channel_name = await get_channel_name(channel_id)
            if not channel_name:
                channel_id = message.channel.id
                await send_message("Invalid channel id. Try again, or go to the channel you want as default and use command !set_default_channel.", channel_id)
                return
            else:
                settings[str(message.guild.id)]["Default Commerce Channel ID"] = channel_id
    else:
        channel_id = message.channel.id
        channel_name = await get_channel_name(channel_id)
        settings[str(message.guild.id)]["Default Commerce Channel ID"] = channel_id

    await send_message(f"{channel_name} has been set as the default channel.", message.channel.id)
    await async_save_json(SETTINGS_FILE, settings)

async def get_channel_name(channel_id):
    channel_id = int(channel_id)
    channel = await bot.fetch_channel(channel_id)
    channel_name = channel.name
    return channel_name

async def handle_toggle_command(message):
    content = message.content.strip()
    channel_id = message.channel.id
    server_id = str(message.guild.id)

    # Match repeating pairs of: (!command) (true/false)
    pattern = r"!toggle_command(?:\s+\(([^)]+)\)\s+\(([^)]+)\))+"
    matches = re.findall(r"\(([^)]+)\)\s+\(([^)]+)\)", content)

    if not matches:
        await send_message("Invalid syntax. [SYNTAX] !toggle_command (!command) (true/false) [...]", channel_id)
        return

    settings = await async_load_json(SETTINGS_FILE)

    if server_id not in settings:
        await send_message("Server settings not found.", channel_id)
        return

    updated = []
    failed = []

    for command, toggle_value in matches:
        toggle_value = toggle_value.lower()

        found = False
        for section in ("User Commands", "Privileged Commands"):
            if command.lower() in settings[server_id][section] and command.lower() != "!toggle_command":
                if toggle_value not in ["true", "false"]:
                    found = True
                    failed.append((f"`{command.lower()}` was not set to the value of... **{toggle_value}**"))
                    break
                if toggle_value == "true":
                    toggle_value = True
                else:
                    toggle_value = False
                settings[server_id][section][command] = toggle_value
                updated.append(f"`{command.lower()}` set to **{toggle_value}**")
                found = True
                break
        if not found:
            failed.append(f"`{command.lower()}` not found in settings")

    await async_save_json(SETTINGS_FILE, settings)
    await set_enabled_commands(message)

    result = ""
    if updated:
        result += "**✅ Updated:**\n" + "\n".join(updated) + "\n"
    if failed:
        result += "**⚠️ Failed:**\n" + "\n".join(failed)

    await send_message(result, channel_id)


async def command_loop():
    while True:
        while not COMMAND_QUEUE:
            await asyncio.sleep(1)
        await check_for_command(COMMAND_QUEUE[0])
        COMMAND_QUEUE.pop(0)

async def start_auction_timers():
    shop = await async_load_json(SHOP_FILE)
    if not shop:
        return
    for server_id, server_data in shop.items():
        auctions = server_data.get("Auctions", {})
        if auctions:
            for auction_id, auction in auctions.items():
                end_time = auction["auction_end"]
                asyncio.create_task(auction_timer(server_id, auction_id, end_time))

@bot.event
async def on_ready():
    print(f"[green]Logged in as {bot.user}")
    asyncio.create_task(command_loop())
    await start_auction_timers()

@bot.event
async def on_message(message):
    asyncio.create_task(handle_message(message))

async def get_message_ids(message):
    return message.guild.id, message.author.id

async def send_message(message_to_send = "", channel_id = 0, pin = False):
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception as e:
            if DEBUG:
                print(f"[red][ERROR] Could not fetch channel {channel_id}: {e}")
            return
    sent = await channel.send(message_to_send)
    if pin == True: #Assuming if pinning, want everything else from the bot unpinned except the first message.
        await unpin_bot_messages(channel_id)
        await sent.pin()
    return sent.id

async def pin_message(message_id, channel_id, pin = True):
    channel = await bot.fetch_channel(channel_id)
    message = await channel.fetch_message(message_id)
    if pin:
        await message.pin()
    else:
        await message.unpin()

async def edit_message(content, channel_id, message_id):
    channel = await bot.fetch_channel(channel_id)
    message = await channel.fetch_message(message_id)
    await message.edit(content = content)

#Sends a message to discord as an embed
async def send_embed_message(embed_message, channel_id, pin = False):
    channel = bot.get_channel(channel_id)
    sent = await channel.send(embed = embed_message)
    if pin == True:
        await unpin_bot_messages(channel_id)
        await sent.pin()

async def validate_user_permission(server_id, user_id):
    guild = bot.get_guild(server_id)
    if not guild:
        if DEBUG:
            print("[red]Server not found")
    user = await guild.fetch_member(user_id)
    if not user:
        if DEBUG:
            print("[red]User not found")
    if user.guild_permissions.manage_channels:
        return True
    else:
        return False
    
async def unpin_bot_messages(channel_id, is_reset = False):
    pst = ZoneInfo("America/Los_Angeles")
    today_pst = datetime.now(pst).date()
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception as e:
            if DEBUG:
                print(f"[red][ERROR][bot.py][unpin_bot_messages] Could not fetch channel {channel_id}")
            return
    pinned_messages = await channel.pins()
    bot_user = bot.user

    for message in pinned_messages:
        if message == pinned_messages[0] and is_reset == False: #Skip first pinned message
            continue
        message_time_pst = message.created_at.astimezone(pst).date()
        if message_time_pst == today_pst and is_reset == False:
            continue
        if message.author == bot_user:
            try:
                await message.unpin()
            except Exception as e:
                if DEBUG:
                    print(f"[red]Failed to unpin message: {e}")

async def send_batch_embeds(list_of_embeds, channel_id):
    channel = bot.get_channel(channel_id)
    for i in range(0, len(list_of_embeds), 10):
        await channel.send(embeds = list_of_embeds[i:i + 10])

async def get_display_name(server_id, user_id):
    guild = await get_guild(server_id)
    user = await guild.fetch_member(int(user_id))
    return user.display_name

async def get_user_name(server_id, user_id):
    guild = await get_guild(server_id)
    user = await guild.fetch_member(int(user_id))
    return user.name

async def get_guild(server_id):
    server_id = int(server_id)
    guild = await bot.fetch_guild(server_id)
    return guild

async def get_user(server_id, user_id):
    guild = await get_guild(int(server_id))
    return await guild.fetch_member(int(user_id))

async def get_user_id_from_username(server_id, name):
    guild = await get_guild(int(server_id))
    members = [member async for member in guild.fetch_members(limit=None)]
    if DEBUG:
        print(f"[green]Fetched {len(members)} members")
    for member in members:
        if member.name.lower() == name.lower() or member.display_name.lower() == name.lower():
            return member.id
    return None

if __name__ == '__main__':
    asyncio.run(populate_data_folder())
    bot.run(TOKEN)

