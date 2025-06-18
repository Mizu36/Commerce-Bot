🛒 Commerce Bot
===============

A fully-featured Discord bot for running a simulated economy, complete with betting, predictions, auctions, shop items, and inventory tracking. Built using `discord.py` and `asyncio`, the bot supports both user and moderator commands with customizable permissions.

* * * * *

📦 Features
-----------

-   💵 Virtual currency system with wallets and payouts

-   📊 Predictions and betting with odds-based payouts

-   🧾 Item shop with timed restocks

-   🔄 Auctions with real-time timers

-   🎒 Inventories with buy/sell mechanics

-   ⚙️ Moderator-only command toggles

-   🔐 Persistent JSON-based data storage

* * * * *

🛠 Installation
---------------

### 1\. Clone the repository

`git clone https://github.com/YourUsername/Commerce-Bot.git
cd Commerce-Bot`

### 2\. Run Setup Script (Recommended for Windows)

Use the provided setup script to automatically:

-   Install Python 3.12.4

-   Set up a virtual environment

-   Install dependencies

-   Generate a `.env` file

`setup_bot.bat`

This script deletes itself after setup.

* * * * *

✅ Manual Setup (Optional)
-------------------------

If you prefer a manual setup or you're not on Windows:

### 1\. Install Python 3.12.4

Download and install Python 3.12.4 from [python.org](https://www.python.org/downloads/release/python-3124/).

Make sure to check **"Add Python to PATH"** during installation.

### 2\. Create a Virtual Environment

`python -m venv venv`

### 3\. Activate the Environment

-   Windows:

    `venv\Scripts\activate`

-   macOS/Linux:

    `source venv/bin/activate`

### 4\. Install Required Packages

`pip install -r requirements.txt`

* * * * *

🔑 Discord Bot Setup
--------------------

### 1\. Go to the Discord Developer Portal

-   Click **New Application**

-   Go to the **Bot** tab and click **Add Bot**

### 2\. Enable Bot Intents

Under the Bot settings, enable:

-   `MESSAGE CONTENT INTENT`

-   `SERVER MEMBERS INTENT`

-   `GUILD PRESENCE INTENT` (optional)

### 3\. Copy the Bot Token

Go to the **Bot** tab → Click **Reset Token** → Copy the token

### 4\. Create `.env` File

The setup script generates one automatically, but you can manually create `.env` with:


`DISCORD_TOKEN=your_bot_token_here`

* * * * *

🔗 Invite the Bot
-----------------

Use this URL format to invite the bot to your server:


`https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&scope=bot&permissions=277025508352`

Recommended permissions:

-   Read Messages

-   Send Messages

-   Manage Messages (for unpinning)

-   Embed Links

-   Read Message History

-   Mention Everyone (optional)

* * * * *

⚙️ Commands & Usage
-------------------

### 🧑‍💼 User Commands

| Command | Description |
| --- | --- |
| `!wallet` | View wallet balance |
| `!shop` | View available items |
| `!buy` | Buy an item |
| `!sell` | Sell an item |
| `!inventory` | View your inventory |
| `!bet` | Place a bet on a prediction |
| `!predictions` | View current predictions |
| `!auction_item` | Start an auction |
| `!auctions` | View active auctions |
| `!bid` | Place a bid on an auction |

### 🔧 Moderator Commands

| Command | Description |
| --- | --- |
| `!create_shop_item` | Add a new shop item |
| `!edit_shop_item` | Edit an item |
| `!delete_shop_item` | Remove an item |
| `!create_prediction` | Start a betting event |
| `!close_prediction` | Close a prediction without resolving |
| `!resolve_prediction` | Close and resolve a prediction |
| `!create_auction` | Creates a new auction |
| `!reward` | Grant money to a user |
| `!toggle_command` | Enable/disable commands |
| `!reset_user_inventory` | Clear a user's inventory |
| `!reset_user` | Reset a user's data |
| `!purge_deprecated_users` | Remove users not in server |
| `!set_default_channel` | Sets a channel for auction announcements |

* * * * *

🧪 Development & Debugging
--------------------------

-   Enable `DEBUG = True` to print debug output.

-   All commands queue through a command loop for async safety.

-   Fully async file I/O using `aiofiles`.

* * * * *

✨ Contributing
--------------

Pull requests welcome! Fork the repo and make your changes on a new branch.

* * * * *

🛡 License
----------

This project is open source and uses the MIT License.
