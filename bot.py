import os
import re
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator, exceptions
from dotenv import load_dotenv

# 1. 載入環境變數
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# 2. Discord Bot 基本設定
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 3. 先用一個實例抓支援語言表
_tmp = GoogleTranslator(source="auto", target="en")
_supported = _tmp.get_supported_languages(as_dict=True)  # {'afrikaans':'af', ..., 'chinese (traditional)':'zh-TW', ...}

# 4. 建 code->name 字典，以及支援 code 集合
CODE_TO_NAME = {code: name for name, code in _supported.items()}
SUPPORTED_CODES = set(CODE_TO_NAME.keys())  # e.g. {'af','sq',...,'zh-TW','zh-CN','en',...}

# 5. 建「別名(小寫連字號)→正規 code」映射
def normalize_code(code: str) -> str:
    return code.strip().lower().replace('_', '-')

ALIAS_TO_CODE = {normalize_code(c): c for c in SUPPORTED_CODES}
ALIAS_TO_CODE['auto'] = 'auto'  # 允許 auto 偵測

ROLE_NAME = "Translator"
GUILD_LANG_SETTINGS = {}

def get_source_language(text: str) -> str:
    """先偵測，如果含 CJK 漢字就當 zh-tw，否則用 deep-translator detect()"""
    if re.search(r'[\u4e00-\u9fff]', text):
        return 'zh-tw'
    detector = GoogleTranslator(source='auto', target='en')
    try:
        lang = detector.detect(text)  # 回傳 e.g. 'en','fr','zh-cn'
    except Exception:
        return 'auto'
    return lang.lower()

def translate_text(text: str, target_alias: str) -> str:
    """
    1. 先把 alias 轉成正規 code (如 'zh-tw'→'zh-TW')
    2. 把來源也做 alias→code
    3. 送進 GoogleTranslator()
    4. 若翻回來一樣且含漢字，就做一次 zh-cn → tgt fallback
    """
    tgt = ALIAS_TO_CODE.get(normalize_code(target_alias))
    if not tgt:
        return text  # 不支援的 target

    # 來源
    src_alias = get_source_language(text)
    src = ALIAS_TO_CODE.get(src_alias, 'auto')

    try:
        tr = GoogleTranslator(source=src, target=tgt)
        out = tr.translate(text)
    except exceptions.NotValidPayload as e:
        print(f"[Payload Error] src={src}, tgt={tgt}, err={e}")
        return text
    except Exception as e:
        print(f"[Translate Error] src={src}, tgt={tgt}, err={e}")
        return text

    # fallback：若翻譯後沒變且含漢字，就試 zh-CN→tgt
    if out == text and re.search(r'[\u4e00-\u9fff]', text) and src != 'zh-cn':
        try:
            fallback = GoogleTranslator(source='zh-CN', target=tgt)
            return fallback.translate(text)
        except Exception as e:
            print(f"[Fallback Error] err={e}")
    return out

@bot.event
async def on_guild_join(guild):
    role = discord.utils.get(guild.roles, name=ROLE_NAME)
    if not role:
        await guild.create_role(name=ROLE_NAME)
        print(f"在伺服器「{guild.name}」中已建立身分組：{ROLE_NAME}")

def has_translator_or_admin():
    async def predicate(ctx):
        perms = ctx.author.guild_permissions
        has_role = any(r.name == ROLE_NAME for r in ctx.author.roles)
        return perms.administrator or has_role
    return commands.check(predicate)

@bot.command(name="setlang")
@has_translator_or_admin()
async def setlang(ctx, *langs: str):
    invalid = [c for c in langs if normalize_code(c) not in ALIAS_TO_CODE]
    if invalid:
        await ctx.send(f"不支援語言代碼: {', '.join(invalid)}")
        return
    GUILD_LANG_SETTINGS[ctx.guild.id] = list(langs)
    names = [f"{CODE_TO_NAME[ALIAS_TO_CODE[normalize_code(c)]]} ({c})" for c in langs]
    await ctx.send(f"已將翻譯語言設定為: {', '.join(names)}")

@bot.command(name="rmlang")
@has_translator_or_admin()
async def rmlang(ctx, lang: str):
    lst = GUILD_LANG_SETTINGS.get(ctx.guild.id, ["zh-TW", "en"])
    if lang not in lst:
        await ctx.send(f"翻譯清單中沒有語言: {lang}")
        return
    lst.remove(lang)
    GUILD_LANG_SETTINGS[ctx.guild.id] = lst
    await ctx.send(f"已移除翻譯語言: {lang}")

@bot.command(name="addlang")
@has_translator_or_admin()
async def addlang(ctx, *langs: str):
    current = GUILD_LANG_SETTINGS.get(ctx.guild.id, ["zh-TW", "en"])
    new = []
    for c in langs:
        if normalize_code(c) not in ALIAS_TO_CODE:
            await ctx.send(f"不支援語言代碼: {c}")
            return
        if c not in current:
            new.append(c)
    GUILD_LANG_SETTINGS[ctx.guild.id] = current + new
    names = [f"{CODE_TO_NAME[ALIAS_TO_CODE[normalize_code(c)]]} ({c})"
             for c in GUILD_LANG_SETTINGS[ctx.guild.id]]
    await ctx.send(f"目前翻譯清單: {', '.join(names)}")

@bot.command(name="listlangs")
async def listlangs(ctx):
    lines = [f"{code}: {name}" for code, name in sorted(CODE_TO_NAME.items())]
    embed = discord.Embed(
        title="🌐 支援語言列表",
        description="```\n" + "\n".join(lines) + "\n```",
        color=0x3498db
    )
    await ctx.send(embed=embed)

@bot.event
async def on_ready():
    print(f"{bot.user} 已上線")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return

    text = message.content.strip()
    if text:
        langs = GUILD_LANG_SETTINGS.get(message.guild.id, ["zh-TW", "en"])
        src_alias = get_source_language(text)
        embed = discord.Embed(
            title="🌐 Translate",
            description=f"```{text}```",
            color=0x2ecc71,
            timestamp=message.created_at
        )
        embed.set_author(name=message.author.display_name,
                         icon_url=message.author.avatar.url)

        for code in langs:
            out = translate_text(text, code)
            name = CODE_TO_NAME.get(ALIAS_TO_CODE[normalize_code(code)], code)
            embed.add_field(name=f"{name} ({code})", value=out, inline=True)

        await message.channel.send(embed=embed)

    await bot.process_commands(message)

bot.run(TOKEN)
