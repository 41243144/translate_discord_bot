import os
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator
from dotenv import load_dotenv
intents = discord.Intents.default()
intents.message_content = True

# 載入 .env 中的環境變數
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")  # 請在 .env 中填入你的機器人 Token

# 設定指令前綴
bot = commands.Bot(command_prefix="!", intents=intents)

# 構建代碼到名稱的映射
_tmp_translator = GoogleTranslator(source='auto', target='zh-TW')
_supported = _tmp_translator.get_supported_languages(as_dict=True)
# 反轉為 code->language name
CODE_TO_NAME = {code: name for name, code in _supported.items()}
# 使用 deep_translator 進行英文翻譯
en_translator = GoogleTranslator(source='auto', target='en')

@bot.event
async def on_ready():
    print(f"{bot.user} 已上線")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    # 若為指令則先處理
    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return
    if message.content.strip():
        try:
            trans_zh = GoogleTranslator(source='auto', target='zh-TW').translate(message.content)
            trans_en = en_translator.translate(message.content)
            # 美化自動翻譯的 Embed
            embed = discord.Embed(
                title="🌐 Translate",
                description=f"```{message.content}```",
                color=0x2ecc71,
                timestamp=message.created_at
            )
            embed.set_author(name=message.author.display_name, icon_url=message.author.avatar.url)
            text = message.content 
            # embed.add_field(name="", value=text, inline=False)
            embed.add_field(name="🇹🇼 中文", value=trans_zh, inline=True)
            embed.add_field(name="🇬🇧 English", value=trans_en, inline=True)
            await message.channel.send(embed=embed)
        except Exception:
            pass
    # 處理其他指令
    await bot.process_commands(message)

# 啟動 Bot
bot.run(TOKEN)
