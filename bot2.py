import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Modal, TextInput
import sqlite3
import hashlib
import os
import datetime
from collections import defaultdict

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)


def get_db_connection():
    conn = sqlite3.connect('bot_users.db')
    conn.row_factory = sqlite3.Row
    return conn

def setup_database():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password BLOB NOT NULL,
            email TEXT,
            discord_id INTEGER,
            quiz_results TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print("Veritabanı kurulumu tamamlandı.")

def hash_password(password):
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt + key

def verify_password(stored_password, provided_password):
    salt = stored_password[:32]
    stored_key = stored_password[32:]
    key = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt, 100000)
    return key == stored_key

def register_user(username, password, email, discord_id):
    try:
        conn = get_db_connection()
        hashed_password = hash_password(password)
        conn.execute('INSERT INTO users (username, password, email, discord_id) VALUES (?, ?, ?, ?)',
                    (username, hashed_password, email, discord_id))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        print(f"Kayıt hatası: {e}")
        return False

def verify_user(username, password):
    try:
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and verify_password(user['password'], password):
            return True
        return False
    except Exception as e:
        print(f"Doğrulama hatası: {e}")
        return False

# --- Uygulama içi durum (bellek) ---
logged_in_users = {}  # user_id -> bool
quiz_history = defaultdict(list)  # user_id -> list of dicts {kategori, sonuc, tarih}
user_activity_count = defaultdict(int)  # basit aktivite sayacı
user_goals = defaultdict(list)  # user_id -> list of goals: {id, text, due_date, completed}
friends = defaultdict(set)  # user_id -> set of user_ids
mentors = set()  # kullanıcı id'leri mentor olmak için kayıtlı
mentor_requests = defaultdict(list)  # mentor_id -> list of mentee user_ids waiting
mentor_pairs = {}  # mentee_id -> mentor_id
daily_reward_claim = {}  # user_id -> date of last claim (YYYY-MM-DD)
resource_bank = {
    "yazilim": ["https://www.freecodecamp.org", "https://docs.python.org/3/"],
    "veribilim": ["https://www.kaggle.com", "https://scikit-learn.org"],
    "pazarlama": ["https://moz.com/learn/seo", "https://www.hubspot.com/resources"],
    "tasarim": ["https://www.figma.com/resources/learn-design/", "https://www.behance.net"],
    "girisim": ["https://www.ycombinator.com/library", "https://hbr.org"]
}

# Basit id üretimi için sayaç
_goal_id_counter = 1

# --- UI Bileşenleri ---
class LoginView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="Giriş Yap", style=discord.ButtonStyle.primary, custom_id="login"))
        self.add_item(Button(label="Kayıt Ol", style=discord.ButtonStyle.secondary, custom_id="register"))

class LoginModal(Modal):
    def __init__(self):
        super().__init__(title="Giriş Yap", timeout=None)
        self.username = TextInput(label="Kullanıcı Adı", required=True)
        self.password = TextInput(label="Şifre", style=discord.TextStyle.short, required=True)
        self.add_item(self.username)
        self.add_item(self.password)

    async def on_submit(self, interaction: discord.Interaction):
        username = self.username.value
        password = self.password.value
        if verify_user(username, password):
            logged_in_users[interaction.user.id] = True
            conn = get_db_connection()
            conn.execute('UPDATE users SET discord_id = ? WHERE username = ?', (interaction.user.id, username))
            conn.commit()
            conn.close()
            await interaction.response.send_message("Başarıyla giriş yaptınız! Artık diğer komutları kullanabilirsiniz.", ephemeral=True)
        else:
            logged_in_users[interaction.user.id] = False
            await interaction.response.send_message("Kullanıcı adı veya şifre hatalı. Lütfen tekrar deneyin.", ephemeral=True)

class RegisterModal(Modal):
    def __init__(self):
        super().__init__(title="Kayıt Ol", timeout=None)
        self.username = TextInput(label="Kullanıcı Adı", required=True, min_length=3)
        self.password = TextInput(label="Şifre", style=discord.TextStyle.short, required=True, min_length=4)
        self.email = TextInput(label="E-posta", required=False)
        self.add_item(self.username)
        self.add_item(self.password)
        self.add_item(self.email)

    async def on_submit(self, interaction: discord.Interaction):
        username = self.username.value
        password = self.password.value
        email = self.email.value
        if register_user(username, password, email, interaction.user.id):
            logged_in_users[interaction.user.id] = False
            await interaction.response.send_message("Başarıyla kayıt oldunuz! `!giris` ile giriş yapabilirsiniz.", ephemeral=True)
        else:
            await interaction.response.send_message("Kullanıcı adı zaten kullanımda. Farklı bir kullanıcı adı deneyin.", ephemeral=True)

class QuizView(View):
    def __init__(self, soru_no, kategori="kariyer"):
        super().__init__(timeout=None)
        self.soru_no = soru_no
        self.kategori = kategori
        if soru_no == 1:
            self.add_item(Button(label="İngilizceyi çok iyi konuşurum", style=discord.ButtonStyle.primary, custom_id=f"{kategori}_q1_a"))
            self.add_item(Button(label="Orta seviyedeyim", style=discord.ButtonStyle.primary, custom_id=f"{kategori}_q1_b"))
            self.add_item(Button(label="Başlangıç seviyesindeyim", style=discord.ButtonStyle.primary, custom_id=f"{kategori}_q1_c"))
            self.add_item(Button(label="Hiç bilmiyorum", style=discord.ButtonStyle.primary, custom_id=f"{kategori}_q1_d"))
        elif soru_no == 2:
            self.add_item(Button(label="Matematik", style=discord.ButtonStyle.primary, custom_id=f"{kategori}_q2_a"))
            self.add_item(Button(label="Sanat/Tasarım", style=discord.ButtonStyle.primary, custom_id=f"{kategori}_q2_b"))
            self.add_item(Button(label="Sosyal Bilimler", style=discord.ButtonStyle.primary, custom_id=f"{kategori}_q2_c"))
            self.add_item(Button(label="Spor dalı", style=discord.ButtonStyle.primary, custom_id=f"{kategori}_q2_d"))
        elif soru_no == 3:
            self.add_item(Button(label="Akademisyen olmak isterim", style=discord.ButtonStyle.primary, custom_id=f"{kategori}_q3_a"))
            self.add_item(Button(label="Şirketlerde çalışmak isterim", style=discord.ButtonStyle.primary, custom_id=f"{kategori}_q3_b"))
            self.add_item(Button(label="Kendi işimi kurmak isterim", style=discord.ButtonStyle.primary, custom_id=f"{kategori}_q3_c"))
            self.add_item(Button(label="Sporcu olmak isterim", style=discord.ButtonStyle.primary, custom_id=f"{kategori}_q3_d"))

class CareerChoiceView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="Yazılım Geliştirici", style=discord.ButtonStyle.primary, custom_id="yazilim"))
        self.add_item(Button(label="Veri Bilimci", style=discord.ButtonStyle.primary, custom_id="veribilim"))
        self.add_item(Button(label="Dijital Pazarlama", style=discord.ButtonStyle.primary, custom_id="pazarlama"))
        self.add_item(Button(label="Tasarımcı / UX", style=discord.ButtonStyle.primary, custom_id="tasarim"))
        self.add_item(Button(label="Girişimci", style=discord.ButtonStyle.primary, custom_id="girisim"))


@bot.event
async def on_ready():
    print(f"Bot giriş yaptı: {bot.user}")
    setup_database()
    daily_goal_reminder.start()
    print("Zamanlayıcı başlatıldı.")


@bot.check
async def global_check(ctx):
    if ctx.command and ctx.command.name == "giris":
        return True
    if not logged_in_users.get(ctx.author.id, False):
        await ctx.send("Bu komutu kullanabilmek için önce `!giris` yaparak doğru şifreyle giriş yapmalısınız.")
        return False
    return True

@bot.command()
async def giris(ctx):
    await ctx.send("Lütfen giriş yapın veya kayıt olun:", view=LoginView())

@bot.command()
async def cikis(ctx):
    """Kullanıcı çıkış yapar (session sonlandırma)"""
    if logged_in_users.get(ctx.author.id, False):
        logged_in_users[ctx.author.id] = False
        await ctx.send("Başarıyla çıkış yaptınız.")
    else:
        await ctx.send("Zaten girişli değilsiniz.")

@bot.command()
async def quiz(ctx, kategori: str = "kariyer"):
    """Quiz başlat (kategori: kariyer, ilgi, iki farklı kategori örneği)"""
    if not logged_in_users.get(ctx.author.id, False):
        await ctx.send("Önce `!giris` yapmalısınız.")
        return
    kategori = kategori.lower()
    if kategori not in ["kariyer", "ilgi"]:
        await ctx.send("Geçersiz kategori. Desteklenenler: kariyer, ilgi")
        return
    user_activity_count[ctx.author.id] += 1
    await ctx.send(f"{kategori} quizi başlıyor. 1. soru:", view=QuizView(1, kategori))

@bot.command()
async def kariyer(ctx):
    if not logged_in_users.get(ctx.author.id, False):
        await ctx.send("Önce `!giris` yapmalısınız.")
        return
    await ctx.send("Kariyer yolları için bir buton seçin:", view=CareerChoiceView())

@bot.command()
async def profil(ctx, member: discord.Member = None):
    """Gelişmiş profil gösterimi"""
    if not logged_in_users.get(ctx.author.id, False):
        await ctx.send("Önce `!giris` yapmalısınız.")
        return
    if member is None:
        member = ctx.author
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE discord_id = ?', (member.id,)).fetchone()
    conn.close()
    if not user:
        await ctx.send("Profil bilgileri bulunamadı.")
        return

    
    history = quiz_history.get(member.id, [])
    goals = user_goals.get(member.id, [])
    friend_count = len(friends.get(member.id, set()))
    activity = user_activity_count.get(member.id, 0)

    embed = discord.Embed(title="Profil Bilgileri", color=discord.Color.blue())
    embed.add_field(name="Kullanıcı Adı", value=user['username'], inline=True)
    embed.add_field(name="E-posta", value=user['email'] or "Belirtilmemiş", inline=True)
    embed.add_field(name="Kayıt Tarihi", value=user['created_at'], inline=False)
    embed.add_field(name="Quiz Geçmişi (adet)", value=str(len(history)), inline=True)
    embed.add_field(name="Aktivite Sayacı", value=str(activity), inline=True)
    embed.add_field(name="Arkadaş Sayısı", value=str(friend_count), inline=True)
    embed.add_field(name="Aktif Hedefler", value=str(len([g for g in goals if not g.get('completed', False)])), inline=True)
    embed.add_field(name="Son Quiz Sonucu", value=user['quiz_results'] or "Henüz yok", inline=False)

    await ctx.send(embed=embed)

@bot.command()
async def leaderboard(ctx, limit: int = 10):
    """Basit leaderboard: quiz yapan veya aktif kullanıcılar sıralaması"""
    sorted_users = sorted(user_activity_count.items(), key=lambda x: x[1], reverse=True)
    lines = []
    count = 0
    for uid, score in sorted_users:
        member = ctx.guild.get_member(uid)
        name = member.display_name if member else str(uid)
        lines.append(f"{name}: {score}")
        count += 1
        if count >= limit:
            break
    if not lines:
        await ctx.send("Henüz leaderboard verisi yok.")
    else:
        await ctx.send("Leaderboard:\n" + "\n".join(lines))

@bot.command()
async def kaynaklar(ctx, alan: str = "yazilim"):
    """Kategoriye göre kaynak önerileri"""
    alan = alan.lower()
    if alan not in resource_bank:
        await ctx.send("Geçersiz alan. Mevcut: " + ", ".join(resource_bank.keys()))
        return
    links = resource_bank[alan]
    await ctx.send(f"{alan} için kaynaklar:\n" + "\n".join(links))

@bot.command()
async def set_goal(ctx, *, args: str):
    """Hedef oluştur: !set_goal <hedef metni> | <YYYY-MM-DD optional>
       Örnek: !set_goal Python öğren | 2025-12-31
    """
    global _goal_id_counter
    parts = args.split("|")
    text = parts[0].strip()
    due = None
    if len(parts) > 1:
        try:
            due = datetime.datetime.strptime(parts[1].strip(), "%Y-%m-%d").date()
        except:
            await ctx.send("Tarih formatı hatalı. YYYY-MM-DD kullanın.")
            return
    goal = {"id": _goal_id_counter, "text": text, "due_date": due, "created_at": datetime.date.today(), "completed": False}
    _goal_id_counter += 1
    user_goals[ctx.author.id].append(goal)
    await ctx.send(f"Hedef kaydedildi. ID: {goal['id']}")

@bot.command()
async def list_goals(ctx):
    goals = user_goals.get(ctx.author.id, [])
    if not goals:
        await ctx.send("Hiç hedefiniz yok.")
        return
    lines = []
    for g in goals:
        status = "Tamamlandı" if g.get('completed') else "Aktif"
        due = g['due_date'].isoformat() if g['due_date'] else "Belirtilmemiş"
        lines.append(f"ID {g['id']} - {g['text']} - Durum: {status} - Bitiş: {due}")
    await ctx.send("\n".join(lines))

@bot.command()
async def complete_goal(ctx, goal_id: int):
    goals = user_goals.get(ctx.author.id, [])
    for g in goals:
        if g['id'] == goal_id:
            g['completed'] = True
            await ctx.send(f"Hedef ID {goal_id} tamamlandı.")
            return
    await ctx.send("Hedef bulunamadı.")

@bot.command()
async def be_mentor(ctx):
    """Kullanıcı mentor olarak kayıt olur"""
    mentors.add(ctx.author.id)
    await ctx.send("Mentor olarak kayıt oldunuz. Menteeler sizi isteyebilir.")

@bot.command()
async def request_mentor(ctx):
    """Kullanıcı mentor talep eder; rastgele bir mentor sıraya konulur"""
    if ctx.author.id in mentor_pairs:
        await ctx.send("Zaten bir mentora eşleştirilmişsiniz.")
        return
    if not mentors:
        await ctx.send("Şu anda mentor yok. Daha sonra tekrar deneyin.")
        return
    
    mentor_list = list(mentors)
    mentor = min(mentor_list, key=lambda m: len(mentor_requests[m]))
    mentor_requests[mentor].append(ctx.author.id)
    await ctx.send("Mentorluk isteğiniz alındı. Mentor uygun olduğunda size dönecektir.")
    
    guild = ctx.guild
    mentor_member = guild.get_member(mentor)
    if mentor_member:
        try:
            await mentor_member.send(f"{ctx.author.display_name} mentorluk talebinde bulundu. Onaylamak için `!accept_mentee {ctx.author.id}` komutunu kullanabilirsiniz.")
        except:
            pass

@bot.command()
async def accept_mentee(ctx, mentee_id: int):
    """Mentor, kendisine gelen isteği kabul eder"""
    if ctx.author.id not in mentors:
        await ctx.send("Bu komutu kullanmak için mentor olmalısınız ( !be_mentor ).")
        return
    if mentee_id not in mentor_requests.get(ctx.author.id, []):
        await ctx.send("Bu mentee size istek göndermemiş veya zaten alındı.")
        return
    mentor_requests[ctx.author.id].remove(mentee_id)
    mentor_pairs[mentee_id] = ctx.author.id
    try:
        guild = ctx.guild
        mentee_member = guild.get_member(mentee_id)
        if mentee_member:
            await mentee_member.send(f"{ctx.author.display_name} sizi mentee olarak kabul etti.")
    except:
        pass
    await ctx.send("Mentee kabul edildi ve eşleştirildi.")

@bot.command()
async def add_friend(ctx, member: discord.Member):
    """Kullanıcı arkadaş ekler (karşılıklı onay yok - basit)"""
    friends[ctx.author.id].add(member.id)
    await ctx.send(f"{member.display_name} arkadaş listesine eklendi.")

@bot.command()
async def friends_list(ctx):
    fset = friends.get(ctx.author.id, set())
    if not fset:
        await ctx.send("Arkadaş listeniz boş.")
        return
    names = []
    for uid in fset:
        m = ctx.guild.get_member(uid)
        names.append(m.display_name if m else str(uid))
    await ctx.send("Arkadaşlarınız:\n" + "\n".join(names))

@bot.command()
async def claim_daily(ctx):
    """Günlük ödül (basit): her gün bir kez kullanılabilir"""
    today = datetime.date.today().isoformat()
    last = daily_reward_claim.get(ctx.author.id)
    if last == today:
        await ctx.send("Bugün zaten ödülünüzü aldınız.")
        return
    daily_reward_claim[ctx.author.id] = today
    
    user_activity_count[ctx.author.id] += 1
    await ctx.send("Günlük ödül alındı. Aktivite sayacınız arttı.")


@bot.event
async def on_interaction(interaction: discord.Interaction):
    if not interaction.data or 'custom_id' not in interaction.data:
        return
    cid = interaction.data["custom_id"]
    user_id = interaction.user.id

    
    if cid == "login":
        await interaction.response.send_modal(LoginModal())
        return
    if cid == "register":
        await interaction.response.send_modal(RegisterModal())
        return

    if not logged_in_users.get(user_id, False):
        await interaction.response.send_message("Önce `!giris` yapmalısınız.", ephemeral=True)
        return

    
    if "_q" in cid:
        parts = cid.split("_q")
        kategori = parts[0]
        rest = parts[1]  
        q_no = int(rest.split("_")[0])
        
        now = datetime.datetime.utcnow().isoformat()
        quiz_history[user_id].append({"kategori": kategori, "question": q_no, "choice": rest.split("_")[1], "tarih": now})
        user_activity_count[user_id] += 1

        
        if q_no == 1:
            await interaction.response.send_message("2. soru:", view=QuizView(2, kategori), ephemeral=True)
            return
        if q_no == 2:
            await interaction.response.send_message("3. soru:", view=QuizView(3, kategori), ephemeral=True)
            return
        if q_no == 3:
            
            sonuc = quiz_history[user_id][-3:]  
         
            if any(c['choice'] == 'a' for c in sonuc if c['question'] == 1):
                dil = "İleri Seviye"
                uni = "Boğaziçi Üniversitesi veya yurtdışı"
            elif any(c['choice'] == 'b' for c in sonuc if c['question'] == 1):
                dil = "Orta Seviye"
                uni = "Ankara Üniversitesi"
            elif any(c['choice'] == 'c' for c in sonuc if c['question'] == 1):
                dil = "Başlangıç"
                uni = "Yerel üniversiteler"
            else:
                dil = "Başlangıç (geliştirme gerekiyor)"
                uni = "Hazırlık programları önerilir"

            if any(c['choice'] == 'a' for c in sonuc if c['question'] == 2):
                meslek = "Mühendislik / Yazılım"
            elif any(c['choice'] == 'b' for c in sonuc if c['question'] == 2):
                meslek = "Tasarım / Sanat"
            elif any(c['choice'] == 'c' for c in sonuc if c['question'] == 2):
                meslek = "Sosyal Bilimler"
            else:
                meslek = "Spor / Beden eğitimi"

            
            conn = get_db_connection()
            summary = f"Dil: {dil}, Üniversite: {uni}, Meslek: {meslek}"
            conn.execute('UPDATE users SET quiz_results = ? WHERE discord_id = ?', (summary, user_id))
            conn.commit()
            conn.close()

           
            guild = interaction.guild
            if guild:
                role_name_map = {
                    "Mühendislik / Yazılım": "Yazılım Adayı",
                    "Tasarım / Sanat": "Tasarım Adayı",
                    "Sosyal Bilimler": "Sosyal Aday",
                    "Spor / Beden eğitimi": "Sporcu Aday"
                }
                role_name = role_name_map.get(meslek)
                if role_name:
                  
                    role = discord.utils.get(guild.roles, name=role_name)
                    if role is None:
                        try:
                            role = await guild.create_role(name=role_name)
                        except Exception as e:
                            print(f"Rol oluşturulamadı: {e}")
                            role = None
                   
                    if role:
                        member = guild.get_member(user_id)
                        if member:
                            try:
                                await member.add_roles(role)
                            except Exception as e:
                                print(f"Rol verilemedi: {e}")


            alan_key = None
            if "Yazılım" in meslek:
                alan_key = "yazilim"
            elif "Tasarım" in meslek:
                alan_key = "tasarim"
            elif "Veri" in meslek:
                alan_key = "veribilim"
            elif "Pazarlama" in meslek:
                alan_key = "pazarlama"
            else:
                alan_key = "girisim"

            resources = resource_bank.get(alan_key, [])

            quiz_history[user_id].append({"kategori": kategori, "result_summary": summary, "tarih": now})
            await interaction.response.send_message(
                f"Quiz tamamlandı!\nDil: {dil}\nÖnerilen Üniversite: {uni}\nUygun meslek: {meslek}\nKaynaklar:\n" + "\n".join(resources)
            )
            return


    cevaplar2 = {
        "yazilim": "Yazılım geliştirici olmak için Python, JavaScript gibi dillerle başlayabilirsiniz. Kaynaklar için: !kaynaklar yazilim",
        "veribilim": "Veri bilimci olmak için istatistik, makine öğrenmesi ve Python kütüphaneleri (pandas, sklearn) öğrenin. Kaynaklar: !kaynaklar veribilim",
        "pazarlama": "Dijital pazarlama için SEO, sosyal medya ve reklam analizi öğrenin. Kaynaklar: !kaynaklar pazarlama",
        "tasarim": "Tasarımcı olmak için Figma, Photoshop ve UX ilkelerini öğrenin. Kaynaklar: !kaynaklar tasarim",
        "girisim": "Girişimcilik için iş planı ve müşteri doğrulama yapın. Kaynaklar: !kaynaklar girisim"
    }
    if cid in cevaplar2:
        await interaction.response.send_message(cevaplar2[cid])
        return


@tasks.loop(minutes=60)
async def daily_goal_reminder():
    
    now = datetime.date.today()
    for user_id, goals in user_goals.items():
        for g in goals:
            if g.get("completed"):
                continue
            due = g.get("due_date")
            if due and (due - now).days in (1, 0): 
                
                for guild in bot.guilds:
                    member = guild.get_member(user_id)
                    if member:
                        try:
                            if (due - now).days == 0:
                                await member.send(f"Hedefinizin son günü: {g['text']}")
                            else:
                                await member.send(f"Hedefinize 1 gün kaldı: {g['text']}")
                        except:
                            pass


if __name__ == "__main__":
    bot.run("")