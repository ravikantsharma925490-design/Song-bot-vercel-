Song Bot (runs on Vercel)

Type a song name -> the bot searches its database and shows buttons -> tap a button to get the song. In a group, the song is sent in the group (not in PM). In a group, writing /play@BotName song name sends the best match straight away. The movie part of the MyTunes zip was removed, and this version was rebuilt for Vercel (webhook).

Add these Environment Variables in Vercel
Name	What to put
BOT_TOKEN	Token from BotFather
MONGO_URI	MongoDB Atlas connection link (mongodb+srv://...)
ADMINS	Your Telegram user ID (separate several with spaces)
WEBHOOK_SECRET	Any long random text (letters/numbers/_ only)
CHANNELS	(optional) ID of the songs channel, e.g. -1001234567890
FSUB_CHANNELS	(optional) Force-subscribe channel ID or @username
FSUB_LINKS	(optional) Invite link for a private channel
GROUP_SEARCH	(optional) 0 = turn off search in groups
PROTECT_CONTENT	(optional) 1 = songs can't be forwarded or saved
PLAY_NEEDS_MENTION	(optional) 1 (default) = in groups, /play works only when the bot is @mentioned; 0 = works without a mention too
Setup
Put all the files in a GitHub repo (app.py must be at the top level of the repo).
Vercel -> Add New -> Project -> pick the repo -> fill in the Environment Variables -> Deploy.
Open this in your browser (ONCE): https://YOUR-APP.vercel.app/api/setup?key=WEBHOOK_SECRET If you see {"webhook": ..., "commands": "set"}, it worked.
Make the bot an ADMIN in your songs channel. Any new song posted in the channel will be saved automatically.
How to add old songs to the database

Open the channel -> select songs (up to 100 at a time) -> FORWARD them to the bot's private chat. For each song the bot reacts with 👍 (new) or 👌 (already saved). Only forwards from ADMINS are saved.

Commands

/play@BotName song name (group or private)

Commands (admin)

/stats /delete <name> /deleteall /ban <id> /unban <id>
