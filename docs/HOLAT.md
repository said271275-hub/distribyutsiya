# Loyiha holati

## Mavjud ishlar

- **0–2-bosqichlar:** boshlang‘ich skelet, ma’lumotlar modeli, autentifikatsiya va ruxsatlar tayyor.
- **3-bosqich (do‘konchi oynasi):** profil, xarita/GPS, katalog, savat va buyurtma, buyurtmalar tarixi, buyurtma berishning oxirgi vaqti, moliya balansi va IDOR himoyasi mavjud. Oxirgi buyurtmadagi mahsulotlarni savatga takror qo‘shish ham bor.
- **4A-qism (faqat server tomoni):** boshqaruv API’sida buyurtmalar va holat tarixi, katalog/narxlar, do‘konlar, transport/haydovchilar, xodimlar, to‘lov/qarz hamda yuklash ro‘yxati mavjud. API’lar kompaniya doirasida cheklangan, o‘zgarishlar nazorat jurnaliga yoziladi; sinov xodimlari uchun mahalliy kirish sozlamasi bor.
- **4B-qism (faqat server tomoni):** reys yaratish, tahrirlash, bekor qilish va tasdiqlash; to‘xtash nuqtalari va buyurtmalarni bog‘lash; kunlik guruhlash taklifi; yo‘l tartibi va yetib borish vaqti; haydovchining faqat o‘z reyslarini ko‘rishi; do‘kon buyurtmasidagi yetib borish vaqti va boshqaruv yig‘ma ko‘rsatkichlari API’lari mavjud. Yuk sig‘imi barcha mahsulotlarda vazn bo‘lsa vazn bilan, aks holda barcha mahsulotlarda hajm bo‘lsa hajm bilan tekshiriladi; o‘lchovlar aralash yoki yetishmasa sig‘im noma’lum qoladi. OSRM ishlamasa to‘g‘ri chiziq masofasi va kompaniya tezligi bilan zaxira hisob ishlaydi.

## Qolgan ishlar

- Ruscha tarjimani to‘liq qilish.
- Oxirgi buyurtmani takrorlash uchun foydalanuvchi oynasi sinovini yozish.
- **4C-qism:** dispetcher oynasi va xarita.
- **4B sinovlari:** 2026-10-17 holatiga ko‘ra serverdagi barcha 72 sinov muvaffaqiyatli yakunlangan.
- **5-bosqich:** haydovchi paneli va PWA.
- **6-bosqich:** boshlanmagan.
- Eskiz SMS integratsiyasi ulanmagan.

## Mahalliy ishga tushirish (PowerShell)

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

4A boshqaruv API’si mahalliy muhitda Swagger orqali ko‘rinadi. Sinov xodimlariga kirish
parolini faqat mahalliy `backend\dev_env.ps1` faylida `DEV_STAFF_PASSWORD`
orqali o‘rnating; `DJANGO_DEBUG=True` va `DEV_OTP_ENABLED=True` bo‘lishi
shart. Dispetcher: `+998900009901`; haydovchilar: `+998900030001`,
`+998900030002`. Parolni kod omboriga qo‘shmang.

Server qismi:

```powershell
Set-Location backend
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Yangi PowerShell terminalida foydalanuvchi oynasini ishga tushiring:

```powershell
Set-Location frontend
npm.cmd run dev
```

## Ogohlantirishlar

- `DEV_OTP_ENABLED` odatda o‘chiq tursin. Sinov OTP kodini ishlab chiqarish muhitida albatta o‘chiring; Eskiz SMS xizmati ulanmagan.
- Docker orqali ishga tushirish tekshirilmagan.

4B yo‘nalish hisoblash sozlamalari `.env` orqali beriladi: `ROUTING_EXTERNAL_ENABLED`,
`OSRM_BASE_URL`, `ROUTING_TIMEOUT_SECONDS`, `ROUTE_START_TIME`,
`ETA_WINDOW_MINUTES` va `TRIP_CLUSTER_RADIUS_KM`. Mahalliy sinovda umumiy OSRM
sinov serveri standart; ishlab chiqarish muhitida o‘zingiz boshqaradigan OSRM’dan
foydalaning. OpenRouteService joriy OSRM so‘rov formatiga bevosita mos emas va
alohida moslashtirgich talab qiladi. Umumiy sinov serveridan ishlab chiqarishda
foydalanmang. Tashqi yo‘nalish xizmati o‘chirilganida ham zaxira hisob ishlaydi.

## Keyingi qadam

4C qism: dispetcher oynasi va xarita.
