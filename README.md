# 🎬 Professional Telegram Kino Bot (SaraFilm Clone)

Telegram uchun zamonaviy, tezkor va to'liq avtomatlashtirilgan kino bot.

---

## 🚀 Imkoniyatlar va Funksiyalar

1. **🎬 Kinolarni qidirish va ko'rish:**
   - **Kod orqali qidirish:** Kinoning maxsus kodini yuborganda (masalan: `58365`) post shaklida sifatli video/fayl taqdim etiladi.
   - **Nom orqali qidirish:** Shunchaki kino nomini yozganda mos keluvchi kinolar ro'yxati taqdim etiladi.
   - **Telegram Inline Qidiruv (`Inline Mode`):** 
     - `@bot top_films` — Eng ko'p ko'rilgan Top kinolar ro'yxati.
     - `@bot saved_films` — Foydalanuvchining shaxsiy saqlagan kinolari.
     - `@bot genre:<nomi>` — Janr bo'yicha filter.
     - `@bot <nomi>` — Qidiruv.

2. **💎 Premium Obuna Tizimi:**
   - Tariflar: 1 oy (15 000 UZS), 3 oy (40 000 UZS), 6 oy (75 000 UZS), 12 oy (140 000 UZS).
   - Foydalanuvchi chek yuboradi ➡️ Bot chekni **Admin Guruhiga** jo'natadi.
   - Admin guruhida `[✅ Tasdiqlash]` va `[❌ Rad qilish]` tugmalari.
   - Rad qilinganda admin sababini yozadi va bot uni to'g'ridan-to'g'ri foydalanuvchiga yuboradi.
   - **Premium foydalanuvchilar:** Majburiy kanallarga a'zo bo'lmasdan to'g'ridan-to'g'ri kinolarni tomosha qiladi!

3. **📢 Majburiy A'zo Bo'lish (Arizalarni ham hisobga oluvchi):**
   - Ochiq va maxfiy (private) kanallarni qo'llab-quvvatlaydi.
   - Agar foydalanuvchi maxfiy kanalga a'zo bo'lish uchun ariza (zapros) yuborsa ham, bot uni avtomatik hisobga oladi va kinoni ochib beradi.

4. **👑 Qulay Admin Paneli (`/admin`):**
   - **🎬 Kino qo'shish (FSM Wizard):**
     1. Video / fayl yuborish
     2. Nomini kiritish
     3. Sifatini kiritish (masalan: `1080Hd`)
     4. Tilini kiritish (masalan: `O'zbek`)
     5. Janrini kiritish (masalan: `Jangari`)
     6. Kod kiritish yoki `Avto` deb avtomatik yaratish
     7. Post oldindan ko'rinishi (Preview) va `[✅ Ha, saqlash]` orqali tasdiqlash
   - **🗑 Kino o'chirish** (kod orqali).
   - **📊 Statistika va Monitoring:** Jami foydalanuvchilar, bugungi faollar, premiumlar, jami kinolar va ko'rishlar soni.
   - **📢 Majburiy kanallar boshqaruvi** (qo'shish va o'chirish).
   - **👥 Adminlar boshqaruvi** (yangi admin qo'shish va o'chirish).
   - **✉️ Xabar tarqatish (Broadcast)**.
   - **💳 Karta ma'lumotlarini sozlash**.

---

## 🛠 O'rnatish va Ishga Tushirish

### 1. Mahalliy (Kompyuteringizda):
Loyihada tayyor `run.bat` fayli mavjud. Uni ikki marta bosish orqali botni ishga tushirishingiz mumkin.
Yoki terminalda:
```powershell
.venv\Scripts\python.exe bot.py
```

### 2. `@BotFather` Sozlamalari (Muhim!):
Botning Inline funksiyasi (`Top Filmlar`, `Saqlanganlar`, `Filter`) ishlashi uchun:
1. Telegramda `@BotFather` ga kiring.
2. `/mybots` ni tanlang va o'z botingizni tanlang.
3. **Bot Settings** ➡️ **Inline Mode** ➡️ **Turn on** tugmasini bosing!
4. **Edit Inline Placeholder** ni bosib `Kino nomi yoki kodini kiriting...` deb yozing.

---

## 🌐 24/7 Bepul Serverga Joylash (Hosting)

Ushbu botni bepul serverlarga (masalan: **Render.com**, **Railway.app** yoki **VPS**) joylab 24/7 uzluksiz ishlatishingiz mumkin:

1. **GitHub** ga repozitoriy ochib ushbu kodlarni yuklang.
2. **Render.com** saytiga kiring:
   - "New +" ➡️ "Background Worker" (yoki Web Service).
   - GitHub repozitoriyangizni ulang.
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python bot.py`
   - Environment Variables bo'limiga `.env` dagi ma'lumotlarni (`BOT_TOKEN`, `ADMIN_IDS` va hk) kiriting.
3. Deploy tugmasini bosing! Bot 24/7 rejimda bepul ishlay boshlaydi.
