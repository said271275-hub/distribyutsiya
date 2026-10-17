# Server qismi

Django REST Framework API. Ishlab chiqish serverida API
`http://localhost:8000/api/` manzilida, OpenAPI sxemasi va Swagger oynasi esa
`/api/schema/` hamda `/api/docs/` manzillarida ochiladi.

## Mahalliy ishga tushirish

Loyiha asosiy jildida `.env.example` faylidan `.env` nusxasini yarating, so‘ng
Docker Compose orqali PostgreSQL xizmatini ishga tushiring:

```powershell
Copy-Item .env.example .env
docker compose up -d db
```

Boshqa PowerShell oynasida:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:POSTGRES_HOST = "localhost"
python manage.py migrate
python manage.py runserver
```

API holatini tekshirish manzili: `GET /api/health/`. Biznes modellari
`apps/accounts`, `apps/companies`, `apps/catalog`, `apps/orders`,
`apps/logistics`, `apps/payments` va `apps/audit` jildlariga ajratilgan.
Kirish, do‘kon egasi API’lari, 4A boshqaruv API’lari va 4B reys rejalash
API’lari mavjud. Dispetcher oynasi va xarita bu bosqich doirasiga kirmaydi.

## Foydalanuvchini aniqlash

- Do‘kon egalari telefon raqami, bir martalik SMS kodi va parol orqali
  `POST /api/auth/register/otp/` hamda `POST /api/auth/register/` manzillarida
  ro‘yxatdan o‘tadi.
- Do‘kon egasi va xodim alohida manzillar orqali tizimga kiradi:
  `/api/auth/login/` va `/api/auth/staff/login/`. Kompaniya boshqaruvchilari
  xodimlarni kirish huquqi talab qilinadigan `/api/v1/admin/staff/` manzillari
  orqali yaratadi va boshqaradi; xodimlar uchun ochiq o‘z-o‘zini ro‘yxatdan
  o‘tkazish manzili yo‘q.
- Kirish JWT belgisi 10 daqiqa amal qiladi va javob tarkibida qaytariladi.
  Yangilanib turadigan JWT belgisi faqat HttpOnly va SameSite xususiyatli
  cookie’da `/api/auth/refresh/` manzili uchun saqlanadi; tizimdan chiqishda
  yangilash belgisi bekor qilinadi. Ma’lumotni o‘zgartiruvchi kirish so‘rovlari
  `GET /api/auth/csrf/` orqali olinadigan CSRF belgisini talab qiladi.
- Bir martalik kodni yetkazish usuli `OTP_PROVIDER` import yo‘li orqali
  tanlanadi. Ishlab chiqish usuli SMS yubormaydi; `DEV_OTP_ENABLED=True`
  bo‘lganda muhitdagi `DEV_OTP_CODE` qiymatini qabul qiladi. Bu sozlama
  odatda o‘chiq va `DEBUG=False` bo‘lganda yoqilmaydi.
- Muvaffaqiyatsiz besh kirish urinishidan so‘ng telefon va IP manzili
  birikmasi 15 daqiqaga bloklanadi; ro‘yxatdan o‘tish kodi har bir telefon
  raqamiga 15 daqiqada ko‘pi bilan uch marta yuboriladi.
- Hisobni o‘chirish so‘rovi joriy parol bilan tasdiqlanadi. Har kuni
  rejalashtiruvchidan `python manage.py process_account_deletions` buyrug‘ini
  ishga tushirib, 30 kunlik tiklash muddati tugagan so‘rovlar ma’lumotlarini
  shaxssizlantiring. `python manage.py cleanup_auth_records` buyrug‘ini ham
  har kuni rejalashtiring.

Mahalliy ishlab chiqishdan tashqarida `AUTH_COOKIE_SECURE=True` qilib, HTTPS
ishlating. Boshqa manbadan keladigan so‘rovlar uchun ruxsat etilgan CORS va
CSRF manzillarini aniq sozlang. Yangilash cookie’lari
`AUTH_COOKIE_SAMESITE` siyosatiga amal qiladi.

## 4A boshqaruv API’si va mahalliy sinov xodimlari

`DEBUG=True` bo‘lganda boshqaruv API’lari `/api/docs/` manzilidagi Swagger’da
hujjatlashtiriladi. Unda faqat o‘z kompaniyasiga tegishli buyurtmalar va
holatlar tarixi, mahsulotlar ro‘yxati va do‘kon narxlari, do‘konni arxivlash
va qarz chegaralari, transport vositalari va haydovchilar, xodimlarni
boshqarish, to‘lovlar, balanslar hamda sana bo‘yicha yuklash yig‘indilari bor.
Boshqaruvdagi o‘zgarishlar nazorat jurnaliga yoziladi. Do‘kon egasi va
haydovchi hisoblari faqat boshqaruvchilarga ruxsat etilgan mahsulot, buyurtma,
xodim va balans manzillaridan foydalana olmaydi; haydovchi to‘lovni faqat o‘z
reysidagi do‘kon uchun qayd eta oladi.

Mahalliy sinov xodimlari tizimga kirishi uchun kod omborida kuzatilmaydigan
`backend/dev_env.ps1` faylida `DEV_STAFF_PASSWORD` uchun maxfiy, vaqtinchalik
qiymat belgilang; `DJANGO_DEBUG=True` va `DEV_OTP_ENABLED=True` ikkalasi ham
yoqilgan bo‘lsin. So‘ng faylni PowerShell muhitiga yuklab,
`python manage.py seed_demo` buyrug‘ini qayta bajaring. Parol saqlashdan oldin
xeshlanadi. Ishga tushish vaqtida ikkala ishlab chiqish sozlamasi yoqilmagan
bo‘lsa `DEV_STAFF_PASSWORD`, `DEBUG=False` bo‘lsa `DEV_OTP_ENABLED` rad
etiladi; bu sozlamalarni ishlab chiqarish muhitida yoqmang.

Sinov xodimlari `/api/auth/staff/login/` manzilidan foydalanadi:

| Vazifasi | Telefon raqami |
|---|---|
| Dispetcher (`company_admin`) | `+998900009901` |
| 1-haydovchi | `+998900030001` |
| 2-haydovchi | `+998900030002` |

## 4B reyslar, guruhlash va yo‘nalish hisoblash

Kompaniya doirasida cheklangan boshqaruv API’lari:

- `GET/POST /api/v1/admin/trips/`, `GET/PATCH /api/v1/admin/trips/{id}/`
- `POST /api/v1/admin/trips/suggest/` tasdiqlangan buyurtmalarni tuman va
  koordinatalar yaqinligiga ko‘ra guruhlash taklifini qaytaradi; reys yaratishdan
  oldin javobni ko‘rib chiqing.
- `POST /api/v1/admin/trips/{id}/stops/`,
  `POST /api/v1/admin/trips/{id}/stops/reorder/`,
  `DELETE /api/v1/admin/trips/{id}/stops/{stop_id}/` va
  `PUT /api/v1/admin/trips/{trip_id}/stops/{stop_id}/orders/`
- `POST /api/v1/admin/trips/{id}/confirm/`, `/cancel/` va `/route/`
- `GET /api/v1/admin/dashboard/`, `GET/PATCH /api/v1/admin/route-settings/`,
  hamda faqat o‘qish uchun `GET /api/v1/driver/trips/`.

Do‘kon buyurtmasi tafsiloti va ro‘yxati yetib borish taxminiy vaqti hamda uning
oralig‘ini faqat tasdiqlangan yoki yo‘ldagi reyslar uchun ko‘rsatadi. Reys
API’lari kompaniya doirasini tekshiradi; haydovchilar faqat o‘z reyslarini
ko‘radi. Reysni o‘zgartiruvchi amallar nazorat jurnaliga yoziladi.

Guruhlashda do‘konlar avval tuman bo‘yicha, so‘ng geografik radius bo‘yicha
klasterlanadi; har bir klasterdagi nuqtalar eng yaqin qo‘shnini tanlash usuli
bilan tartiblanadi. Bir do‘konning bir nechta buyurtmasi bitta to‘xtash
nuqtasiga birlashtiriladi. Barcha buyurtmada vazn ma’lumoti bo‘lsa transport
sig‘imi umumiy vazn bilan, aks holda barcha buyurtmada hajm ma’lum bo‘lsagina
hajm bilan solishtiriladi. O‘lchovlar aralash yoki yetishmayotgan bo‘lsa,
turli birliklar aralashtirilmaydi va sig‘im noma’lum qoladi. Bitta to‘xtashdagi
yuk sig‘imdan oshsa, ogohlantirish beriladi; boshqa to‘xtashlar alohida
takliflarga bo‘linadi.

Yo‘nalish hisoblash sozlamalari:

| Muhit o‘zgaruvchisi | Standart qiymat | Vazifasi |
|---|---:|---|
| `ROUTING_EXTERNAL_ENABLED` | `DJANGO_DEBUG` | Tashqi OSRM so‘rovlarini yoqish |
| `OSRM_BASE_URL` | Ishlab chiqishda umumiy sinov manzili; aks holda bo‘sh | OSRM serverining asosiy manzili |
| `ROUTING_TIMEOUT_SECONDS` | `5` | OSRM so‘rovining kutish vaqti |
| `ROUTE_START_TIME` | `08:00` | Mahalliy reys boshlanish vaqti |
| `ETA_WINDOW_MINUTES` | `45` | Yetib borish taxminining ikki tomonlama oralig‘i |
| `TRIP_CLUSTER_RADIUS_KM` | `8` | Geografik guruhlash radiusi |

OSRM ishlamasa yoki o‘chirilgan bo‘lsa, yo‘nalish Yer sharining egriligi
hisobga olingan to‘g‘ri chiziq masofasi va kompaniyada belgilangan o‘rtacha
tezlik bo‘yicha baholanadi. Ommaviy OSRM sinov xizmati faqat mahalliy sinov
uchun; ishlab chiqarishda o‘zingiz boshqaradigan OSRM’dan foydalaning.
OpenRouteService alohida moslashtirgich talab qiladi va hozirgi OSRM so‘rov
shakliga to‘g‘ridan-to‘g‘ri mos kelmaydi. So‘rovlarga faqat koordinatalar
qo‘shiladi, mijoz ismi yoki telefon raqami hech qachon yuborilmaydi. Bu
o‘zgaruvchilarni `.env` faylida yoki jarayon muhitida belgilang.

## Namuna ma’lumotlari va sinovlar

Ma’lumotlar bazasi o‘zgarishlarini qo‘llagach, takroran xavfsiz yuklanadigan
mahalliy namuna ma’lumotlarini kiriting:

```powershell
python manage.py seed_demo
```

Mahalliy PostgreSQL serversiz sinovlarni xotiradagi SQLite sozlamalari bilan
ishga tushiring:

```powershell
$env:DJANGO_SECRET_KEY = "local-test-only"
python manage.py test apps.core --settings=config.test_settings
```

Tasdiqlangan ERD va API manzillari taklifi quyidagi fayllarda:
[`../docs/00_umumiy_kontekst.md`](../docs/00_umumiy_kontekst.md) and
[`../docs/01_erd_va_api_sxemasi.md`](../docs/01_erd_va_api_sxemasi.md).

## Xavfsizlik va joylashtirish

`.env.example` qiymatlari faqat mahalliy ishlab chiqish uchun. Joylashtirishdan
oldin takrorlanmaydigan, kuchli `DJANGO_SECRET_KEY`, ishlab chiqarish xostlari
va HTTPS sozlamalarini kiriting. `.env` faylini kod omboriga qo‘shmang.
Ishlab chiqarish muhitida Django’ning ishlab chiqish serveridan foydalanmang.

Ishlab chiqarishga chiqarishdan oldin `DEV_OTP_ENABLED=false` qiling va
`EskizOtpProvider` xizmatini ulang.
