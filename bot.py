import discord
from discord.ext import commands
from discord.ui import Button, View

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
cevaplar = {}

@bot.event
async def on_ready():
    print(f"Bot giriş yaptı: {bot.user}")

class QuizView(View):
    def __init__(self, soru_no):
        super().__init__()
        self.soru_no = soru_no

        if soru_no == 1:
            self.add_item(Button(label="İngilizceyi çok iyi konuşurum", style=discord.ButtonStyle.primary, custom_id="q1_a"))
            self.add_item(Button(label="Orta seviyedeyim", style=discord.ButtonStyle.primary, custom_id="q1_b"))
            self.add_item(Button(label="Başlangıç seviyesindeyim", style=discord.ButtonStyle.primary, custom_id="q1_c"))
            self.add_item(Button(label="hic bilmiyorum", style=discord.ButtonStyle.primary, custom_id="q1_d"))
        elif soru_no == 2:
            self.add_item(Button(label="Matematik", style=discord.ButtonStyle.primary, custom_id="q2_a"))
            self.add_item(Button(label="Sanat/Tasarım", style=discord.ButtonStyle.primary, custom_id="q2_b"))
            self.add_item(Button(label="Sosyal Bilimler", style=discord.ButtonStyle.primary, custom_id="q2_c"))
            self.add_item(Button(label="Spor dalı", style=discord.ButtonStyle.primary, custom_id="q2_d"))

        elif soru_no == 3:
            self.add_item(Button(label="Akademisyen olmak isterim", style=discord.ButtonStyle.primary, custom_id="q3_a"))
            self.add_item(Button(label="Şirketlerde çalışmak isterim", style=discord.ButtonStyle.primary, custom_id="q3_b"))
            self.add_item(Button(label="Kendi işimi kurmak isterim", style=discord.ButtonStyle.primary, custom_id="q3_c"))
            self.add_item(Button(label="sporcu olmak isterim", style=discord.ButtonStyle.primary, custom_id="q3_d"))

@bot.command()
async def quiz(ctx):
    await ctx.send(" Kariyer ve Eğitim Quizi Başlıyor!\n\n**1. Soru:** İngilizce seviyeniz nedir?", view=QuizView(1))

class IksirView(View):
    def __init__(self):
        super().__init__()
        self.add_item(Button(label="Yazılım Geliştirici", style=discord.ButtonStyle.primary, custom_id="yazilim"))
        self.add_item(Button(label="Veri Bilimci", style=discord.ButtonStyle.primary, custom_id="veribilim"))
        self.add_item(Button(label="Dijital Pazarlama", style=discord.ButtonStyle.primary, custom_id="pazarlama"))
        self.add_item(Button(label="Tasarımcı / UX", style=discord.ButtonStyle.primary, custom_id="tasarim"))
        self.add_item(Button(label="Girişimci", style=discord.ButtonStyle.primary, custom_id="girisim"))

@bot.command()
async def kariyer(ctx):
    await ctx.send("Kariyer yolları için bir buton seçin:", view=IksirView())

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return

    user_id = interaction.user.id
    cid = interaction.data["custom_id"]

    # Quiz için cevaplar
    if cid.startswith("q1_") or cid.startswith("q2_") or cid.startswith("q3_"):
        if user_id not in cevaplar:
            cevaplar[user_id] = []
        cevaplar[user_id].append(cid)

        if cid.startswith("q1_"):
            await interaction.response.send_message("**2. Soru:** Hangi alanda daha iyisiniz?", view=QuizView(2), ephemeral=True)
        elif cid.startswith("q2_"):
            await interaction.response.send_message("**3. Soru:** Kariyer hedefiniz nedir?", view=QuizView(3), ephemeral=True)
        elif cid.startswith("q3_"):
            sonuc = cevaplar[user_id]
            if "q1_a" in sonuc:
                dil = "İleri Seviye"; uni = "Boğaziçi Üniversitesi,yurtdışı üniversiteleri "
            elif "q1_b" in sonuc:
                dil = "Orta Seviye"; uni = "Ankara Üniversitesi"
            elif "q1_c" in sonuc:
                dil = "Başlangıç"; uni = "Yerel üniversiteler (hazırlık programlı)"
            else:
                dil = "hiç bilmiyor"; uni = "gidebileceğin çok bir yer yok biraz geliştir"

            if "q2_a" in sonuc:
                meslek = "Mühendislik / Yazılım"
            elif "q2_b" in sonuc:
                meslek = "Tasarım / Sanat"
            elif "q3_c" in sonuc:
                meslek = "Psikoloji / Sosyoloji / Hukuk"
            else:
                meslek = "beden eğitimi öğretmeni/futbolcu"

            await interaction.response.send_message(
                f" Quiz tamamlandı!\n\n"
                f" Dil seviyen: **{dil}**\n"
                f" Gidebileceğin üniversite: **{uni}**\n"
                f" Uygun meslek: **{meslek}**"
            )
        return

    # Kariyer butonları için cevaplar
    cevaplar2 = {
        "yazilim": " Yazılım geliştirici olmak için Python, JavaScript gibi dillerle başlayabilirsin.",
        "veribilim": " Veri bilimci olmak için istatistik, makine öğrenmesi ve Python kütüphaneleri (pandas, sklearn) öğrenmelisin.",
        "pazarlama": " Dijital pazarlama kariyeri için SEO, sosyal medya yönetimi ve reklam analizi çok önemli.",
        "tasarim": " UX/UI tasarımcı olmak için Figma, Photoshop ve kullanıcı deneyimi ilkelerine hakim olmalısın.",
        "girisim": " Girişimci olmak için iş fikrini geliştir, iş planı yap ve yatırım/mentor desteği bulmayı hedefle."
    }

    if cid in cevaplar2:
        await interaction.response.send_message(cevaplar2[cid])

bot.run("")