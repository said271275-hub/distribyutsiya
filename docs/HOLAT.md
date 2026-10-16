# Loyiha holati

## Mavjud ishlar

- **0–2-bosqichlar:** boshlang‘ich skelet, ma’lumotlar modeli, autentifikatsiya va ruxsatlar tayyor.
- **3-bosqich (do‘konchi paneli):** profil va xarita/GPS, katalog, savat va buyurtma, buyurtmalar tarixi, cut-off, moliya balansi, IDOR himoyasi mavjud. Oxirgi buyurtmani savatga takrorlash ham qo‘shilgan.

## Qolgan ishlar

- Ruscha tarjimani to‘liq qilish.
- Oxirgi buyurtmani takrorlash uchun frontend testi yozish.
- **4-bosqich:** dispetcher paneli va marshrut.
- **5-bosqich:** haydovchi paneli va PWA.
- **6-bosqich:** boshlanmagan.
- Eskiz SMS integratsiyasi ulanmagan.

## Lokal ishga tushirish (PowerShell)

PostgreSQL xizmatini tekshirib, o‘rnatilgan xizmat nomi bilan ishga tushiring:

```powershell
Get-Service *postgres*
Start-Service <PostgreSQL-xizmati-nomi>
```

Root papkada maxfiy qiymatlarsiz namuna nusxasini oling, o‘zingizning maxfiy qiymatlaringizni kiriting va sozlamalarni joriy terminalga yuklang:

```powershell
Copy-Item backend\dev_env.example.ps1 backend\dev_env.ps1
notepad backend\dev_env.ps1
. .\backend\dev_env.ps1
```

Backend:

```powershell
Set-Location backend
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Yangi PowerShell terminalida frontend:

```powershell
Set-Location frontend
npm.cmd run dev
```

## Ogohlantirishlar

- `DEV_OTP_ENABLED` odatda o‘chiq tursin. Dev OTP kodini production’da albatta o‘chiring; Eskiz integratsiyasi ulanmagan.
- Docker orqali ishga tushirish tekshirilmagan.

## Keyingi qadam

4-bosqichni ikkiga bo‘lib boshlash.
