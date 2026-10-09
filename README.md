# Song Bot (Vercel par chalne wala)

Song ka naam likho -> bot database se dhoondh kar buttons deta hai -> button dabane par song milta hai.
Group mein song group mein hi aata hai (PM mein nahi). Group mein `/play@BotName song ka naam` likhne par best song seedha aa jata hai. MyTunes zip ka movie wala hissa hata kar, Vercel ke liye naya (webhook) banaya gaya hai.

## Vercel mein ye Environment Variables daalein
| Naam | Kya daalein |
|---|---|
| BOT_TOKEN | BotFather ka token |
| MONGO_URI | MongoDB Atlas ka connection link (mongodb+srv://...) |
| ADMINS | Aapki Telegram user ID (kai ho to space se alag) |
| WEBHOOK_SECRET | Koi bhi lamba random text (sirf letters/numbers/_) |
| CHANNELS | (optional) Songs wale channel ki ID, jaise -1001234567890 |
| FSUB_CHANNELS | (optional) Force subscribe channel ID ya @username |
| FSUB_LINKS | (optional) Private channel ka invite link |
| GROUP_SEARCH | (optional) 0 = group mein search band |
| PROTECT_CONTENT | (optional) 1 = song forward/save nahi hoga |
| PLAY_NEEDS_MENTION | (optional) 1 (default) = group mein /play tabhi chale jab bot ko @mention kiya ho; 0 = bina mention ke bhi |

## Setup
1. Saari files GitHub repo mein daalein (app.py repo ke upar hi dikhna chahiye).
2. Vercel -> Add New -> Project -> repo chunein -> Environment Variables bharein -> Deploy.
3. Browser mein kholein (EK baar): `https://AAPKA-APP.vercel.app/api/setup?key=WEBHOOK_SECRET`
   `{"webhook": ..., "commands": "set"}` aaye to ho gaya.
4. Bot ko apne songs channel mein ADMIN banayein. Ab channel mein jo naya song aayega wo apne aap save hoga.

## Purane songs database mein kaise daalein
Channel kholein -> songs select karein (100 tak ek saath) -> bot ke private chat mein FORWARD karein.
Har song par bot 👍 reaction dega (naya) ya 👌 (pehle se tha). Sirf ADMINS ke forward hi save hote hain.

## Commands
/play@BotName song naam  (group ya private)

## Commands (admin)
/stats  /delete <naam>  /deleteall  /ban <id>  /unban <id>
