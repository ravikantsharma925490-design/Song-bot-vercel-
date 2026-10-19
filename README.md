# Song Bot (runs on Vercel)

Type a song name -> the bot searches its database and shows buttons -> tap a button to get the song.
In a group, the song is sent in the group (not in PM). In a group, writing `/play@BotName song name` sends the best match straight away. The movie part of the MyTunes zip was removed, and this version was rebuilt for Vercel (webhook).

## Add these Environment Variables in Vercel
| Name | What to put |
|---|---|
| BOT_TOKEN | Token from BotFather |
| MONGO_URI | MongoDB Atlas connection link (mongodb+srv://...) |
| ADMINS | Your Telegram user ID (separate several with spaces) |
| WEBHOOK_SECRET | Any long random text (letters/numbers/_ only) |
| CHANNELS | (optional) ID of the songs channel, e.g. -1001234567890 |
| FSUB_CHANNELS | (optional) Force-subscribe channel ID or @username |
| FSUB_LINKS | (optional) Invite link for a private channel |
| GROUP_SEARCH | (optional) 0 = turn off search in groups |
| PROTECT_CONTENT | (optional) 1 = songs can't be forwarded or saved |
| YT_DOWNLOAD | (optional) 1 (default) = if a song is not in the database, get it from YouTube; 0 = turn off |
| YOUTUBE_COOKIES | Cookies of a SEPARATE Google/YouTube account (see below). Without them YouTube usually blocks Vercel |
| YT_MAX_MINUTES | (optional) Longest video to download, in minutes (default 10) |
| YT_SAVE_CHANNEL | (optional) Channel where downloaded songs are posted (default: the first ID in CHANNELS) |
| PLAY_NEEDS_MENTION | (optional) 1 (default) = in groups, /play works only when the bot is @mentioned; 0 = works without a mention too |

## Setup
1. Put all the files in a GitHub repo (app.py must be at the top level of the repo).
2. Vercel -> Add New -> Project -> pick the repo -> fill in the Environment Variables -> Deploy.
3. Open this in your browser (ONCE): `https://YOUR-APP.vercel.app/api/setup?key=WEBHOOK_SECRET`
   If you see `{"webhook": ..., "commands": "set"}`, it worked.
4. Make the bot an ADMIN in your songs channel. Any new song posted in the channel will be saved automatically.

## How to add old songs to the database
Open the channel -> select songs (up to 100 at a time) -> FORWARD them to the bot's private chat.
For each song the bot reacts with 👍 (new) or 👌 (already saved). Only forwards from ADMINS are saved.

## Commands
/play@BotName song name  (group or private)

## Commands (admin)
/stats  /delete <name>  /deleteall  /ban <id>  /unban <id>


## YouTube download (new)
`/play@BotName song name` -> the bot checks the database first. If the song is not there, it searches YouTube,
downloads the audio (m4a), **sends it to the user first**, then posts it to the songs channel and saves it in the
database - so the next request for the same song comes straight from the database.
In private chat, if a typed search finds nothing, a "⬇️ Get it from YouTube" button appears. `/play <YouTube link>` also works.

### Setup
1. Make a NEW Google account only for the bot (never use your main account).
2. Log in to youtube.com with it, then export the cookies with a browser extension such as "Get cookies.txt".
3. In Vercel -> Settings -> Environment Variables, add `YOUTUBE_COOKIES` and paste the whole text of the cookies file.
   (Vercel's variables are limited to 64 KB in total, so export only the youtube.com cookies.) Never put cookies on GitHub.
4. Make the bot an admin of the songs channel with permission to post (set `CHANNELS` or `YT_SAVE_CHANNEL`).
5. Redeploy. Function time on Vercel Hobby with Fluid Compute is up to 300 s (it is on by default for new projects).

### Good to know
- A new song takes roughly 10-30 s the first time; songs already in the database arrive in 1-2 s.
- If YouTube starts blocking downloads, the bot tells LOG_CHANNEL (if set). Export fresh cookies and update `YOUTUBE_COOKIES`.
- If downloads suddenly break after YouTube changes something, just redeploy: `yt-dlp` is not pinned, so a redeploy installs the newest version.
- Songs are saved as m4a (no ffmpeg on Vercel). Limit: 50 MB and `YT_MAX_MINUTES`.
- Downloading from YouTube may go against YouTube's terms and copyright rules - that is your responsibility.
