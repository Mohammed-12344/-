import discord
from discord.ext import commands
import requests
from bs4 import BeautifulSoup
import json
import os
import re
from typing import Dict, Any

# ============================================
# 1. الإعدادات والتهيئة
# ============================================

# إعداد البوت
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# ============================================
# 2. دوال المساعدة (تحليل الروابط)
# ============================================

class WebAnalyzer:
    @staticmethod
    async def analyze_url(url: str) -> Dict[str, Any]:
        """تحليل رابط معين واستخراج المعلومات"""
        try:
            response = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            response.raise_for_status()
            
            # تحليل المحتوى حسب نوعه
            content_type = response.headers.get('content-type', '').lower()
            
            # إذا كان ملف Lua أو نصي
            if 'text' in content_type or url.endswith(('.lua', '.txt', '.json', '.py')):
                return await WebAnalyzer.analyze_text_file(url, response.text)
            
            # إذا كان صفحة HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # استخراج المعلومات
            title = soup.find('title')
            title_text = title.string.strip() if title else "لا يوجد عنوان"
            
            # محاولة استخراج الوصف
            description = None
            for meta in soup.find_all('meta'):
                if meta.get('name', '').lower() in ['description', 'og:description']:
                    description = meta.get('content', '')
                    break
            
            if not description:
                first_p = soup.find('p')
                description = first_p.text.strip()[:200] if first_p else "لا يوجد وصف"
            
            # استخراج الصور والروابط
            images = []
            for img in soup.find_all('img')[:3]:
                src = img.get('src')
                if src and not src.startswith('data:'):
                    images.append(src)
            
            links = []
            for link in soup.find_all('a')[:5]:
                href = link.get('href')
                if href and href.startswith('http'):
                    links.append(href)
            
            return {
                'type': 'html',
                'title': title_text,
                'description': description[:500] + '...' if len(description) > 500 else description,
                'images': images,
                'links': links,
                'success': True
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    async def analyze_text_file(url: str, content: str) -> Dict[str, Any]:
        """تحليل الملفات النصية"""
        lines = content.split('\n')
        
        # تحليل خاص لملفات Lua
        if url.endswith('.lua'):
            # عد الأيقونات في ملف lucide.lua
            icon_count = len(re.findall(r'\["(.*?)"\]', content))
            icon_names = re.findall(r'\["(.*?)"\]', content)[:10]  # أول 10 أيقونات
            
            return {
                'type': 'lua',
                'title': f'📁 {url.split("/")[-1]}',
                'description': f'ملف Lua يحتوي على {icon_count} أيقونة',
                'details': f'أمثلة: {", ".join(icon_names)}',
                'lines': len(lines),
                'size': len(content),
                'success': True
            }
        
        # ملفات نصية عامة
        return {
            'type': 'text',
            'title': f'📄 {url.split("/")[-1]}',
            'description': f'ملف نصي يحتوي على {len(lines)} سطر',
            'preview': '\n'.join(lines[:5]) + ('...' if len(lines) > 5 else ''),
            'size': len(content),
            'success': True
        }

# ============================================
# 3. أوامر البوت
# ============================================

@bot.event
async def on_ready():
    print(f'✅ البوت {bot.user} جاهز للعمل!')
    await bot.change_presence(activity=discord.Game(name="!help | تحليل الروابط"))

@bot.command(name='explain')
async def explain_link(ctx, url: str):
    """!explain <رابط> - يشرح محتوى الرابط"""
    
    # رسالة انتظار
    msg = await ctx.send("🔍 جاري تحليل الرابط...")
    
    # تحليل الرابط
    result = await WebAnalyzer.analyze_url(url)
    
    if not result['success']:
        await msg.edit(content=f"❌ عذراً، حدث خطأ: {result['error']}")
        return
    
    # إذا كان ملف Lua
    if result.get('type') == 'lua':
        embed = discord.Embed(
            title=result['title'],
            description=result['description'],
            color=discord.Color.green()
        )
        embed.add_field(
            name="📊 تفاصيل الملف",
            value=f"- عدد الأسطر: {result.get('lines', 0)}\n- حجم الملف: {result.get('size', 0)} حرف",
            inline=False
        )
        embed.add_field(
            name="🎨 الأيقونات الموجودة",
            value=result.get('details', 'لا يوجد'),
            inline=False
        )
        await msg.edit(content=None, embed=embed)
        return
    
    # إذا كان ملف نصي
    if result.get('type') == 'text':
        embed = discord.Embed(
            title=result['title'],
            description=result['description'],
            color=discord.Color.blue()
        )
        embed.add_field(
            name="📝 معاينة",
            value=f"```\n{result.get('preview', '')}\n```",
            inline=False
        )
        await msg.edit(content=None, embed=embed)
        return
    
    # إذا كان صفحة HTML
    embed = discord.Embed(
        title=f"📄 {result['title']}",
        description=result['description'],
        color=discord.Color.blue(),
        url=url
    )
    
    if result.get('images'):
        embed.set_thumbnail(url=result['images'][0] if result['images'][0].startswith('http') else '')
    
    embed.add_field(
        name="🔗 الروابط الموجودة",
        value="\n".join(result.get('links', [])[:3]) or "لا يوجد روابط",
        inline=False
    )
    
    embed.set_footer(text=f"تم التحليل بواسطة {bot.user.name}")
    embed.timestamp = discord.utils.utcnow()
    
    await msg.edit(content=None, embed=embed)

@bot.command(name='help')
async def help_command(ctx):
    """!help - عرض الأوامر المتاحة"""
    embed = discord.Embed(
        title="🤖 أوامر البوت",
        description="البوت المخصص لتحليل الروابط",
        color=discord.Color.gold()
    )
    embed.add_field(
        name="📌 الأوامر",
        value="`!explain <رابط>` - شرح محتوى الرابط\n"
              "`!help` - عرض هذه الرسالة",
        inline=False
    )
    embed.add_field(
        name="📁 أنواع الروابط المدعومة",
        value="- صفحات HTML\n- ملفات Lua\n- ملفات نصية",
        inline=False
    )
    await ctx.send(embed=embed)

@bot.command(name='ping')
async def ping(ctx):
    """!ping - اختبار سرعة البوت"""
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 بونق! سرعة الاستجابة: {latency}ms")

# ============================================
# 4. تشغيل البوت
# ============================================

# اقرأ التوكن من متغير بيئة أو من ملف
TOKEN = os.getenv('MTUxNzcxODMyMzE0NjUyNjcyMA.Gmo8Xa.NnHEnJ2zHgOnxTsx2OtrAJ_27XBZ_H-jV2mcew')

if not TOKEN:
    # إذا لم يوجد متغير بيئة، حاول قراءة من ملف
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            TOKEN = config.get('token')
    except:
        print("❌ لم يتم العثور على التوكن!")
        print("ضع التوكن في متغير البيئة DISCORD_TOKEN أو في ملف config.json")
        exit()

# تشغيل البوت
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ خطأ في التوكن! تأكد من أنه صحيح")
    except Exception as e:
        print(f"❌ حدث خطأ: {e}")
