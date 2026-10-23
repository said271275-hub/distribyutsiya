# Loyiha holati

## Bajarilgan va qisman bajarilgan ishlar

- **0–2-bosqichlar — bajarildi:** loyiha poydevori, ma’lumotlar modeli, kirish tizimi, rollar va kompaniyalar bo‘yicha ma’lumotlarni ajratish tayyor.
- **3-bosqich — qisman:** do‘konchi profili, katalog, savat, buyurtma, buyurtmalar tarixi, oxirgi buyurtmani takrorlash va moliya oynasi mavjud. Oxirgi buyurtmani takrorlash oynasining foydalanuvchi oqimi sinovi yetishmaydi; ruscha tarjima ham to‘liq emas.
- **4A — yozilgan:** boshqaruv API’sida buyurtmalar va ularning holat tarixi, katalog va narxlar, do‘konlar, transport va haydovchilar, xodimlar, to‘lovlar, qarz hamda yuklash ro‘yxati mavjud. Kompaniya doirasidagi ruxsatlar va asosiy server sinovlari bor.
- **4B — yozilgan:** reyslarni boshqarish, buyurtmalarni guruhlash, marshrut tartibi va yetib borish vaqtini hisoblash, sig‘imni tekshirish, haydovchining o‘z reyslarini ko‘rishi va boshqaruv ko‘rsatkichlari tayyor. Tashqi yo‘nalish xizmati ishlamasa zaxira hisob qo‘llanadi. Server sinovlari mavjud.
- **4C-1 — yozilgan:** dispetcher oynasi, boshqaruv ko‘rsatkichlari va buyurtmalar jadvali mavjud. Buyurtmani tanlashdan tasdiqlash yoki bekor qilishgacha bo‘lgan foydalanuvchi oqimi sinovlari yetishmaydi.
- **4C-2 — yozilgan:** reys tuzish, avtomatik guruhlash taklifi, marshrut va xarita mavjud. Reysni tuzishdan tasdiqlashgacha bo‘lgan foydalanuvchi oqimi sinovlari yetishmaydi.
- **4C-3 — yozilgan:** mahsulot va narxlar, do‘konlar, transport va haydovchilar, xodimlar, qarz va to‘lov sahifalari mavjud. Sahifalardagi yaratish, tahrirlash va to‘lov kiritish foydalanuvchi oqimi sinovlari yetishmaydi.
- **5-bosqich, 1-bo‘lak — qisman:** haydovchi oynasi o‘z reyslarini, to‘xtashlarini va yuklash ro‘yxatini ko‘rsatadi. Yetkazilgan deb belgilash, qisman yetkazish, to‘lov va qaytarilgan idishlarni qayd etish hali bajarilmagan.
- **5-bosqich, PWA va oflayn ish — boshlanmagan:** ilovani o‘rnatish, oflayn foydalanish, harakatlarni navbatga olish va keyin sinxronlash yo‘q.
- **6-bosqich — boshlanmagan:** qo‘shimcha imkoniyatlar keyingi bosqichda bajariladi.

## Sinovlar va tekshirilmagan ishlar

- So‘nggi tekshiruvda server sinovlaridan **85**, veb sinovlaridan **35** tasi muvaffaqiyatli o‘tdi.
- Oxirgi buyurtmani takrorlash, dispetcherning buyurtmani boshqarish, reysni tuzish va 4C-3 sahifalarining to‘liq foydalanuvchi oqimlari uchun veb sinovlari yetishmaydi.
- Haydovchi oynasining hozirgi ko‘rinishi bor, ammo haydovchining yetkazish amallari va oflayn sinxronlash tekshirilmagan, chunki ular hali yozilmagan.
- Eskiz SMS xizmati ulanmagan. Docker orqali ishga tushirish tekshirilmagan.
- Reys sig‘imi barcha mahsulotlarda vazn bo‘lsa vazn, aks holda barcha mahsulotlarda hajm bo‘yicha tekshiriladi. O‘lchovlar aralash yoki yetishmasa sig‘im noma’lum deb qoladi.

## Ochiq qarorlar

- Buyurtma tasdiqlanganda qarzga yozish hozirgi tizimda qo‘llanadi. Egasi bu qoida va qarz limitidan oshgandagi dispetcher tasdig‘ini yakuniy tasdiqlashi kerak.
- Qisman yetkazilgan buyurtmada qarz va to‘lov qanday hisoblanishi, qolgan mahsulotlar uchun yangi yetkazish belgilanishi kerakmi — aniqlashtirish kerak.
- Qaytariladigan idishlar bo‘yicha hisob va qarz/tara depozitining o‘zaro bog‘liqligi — yakuniy kelishuv talab qiladi.
- Oflayn bajarilgan harakatlar serverdagi o‘zgarishlar bilan to‘qnashsa, qaysi qiymat ustun bo‘lishi va foydalanuvchiga qanday xabar berilishi — oldindan belgilanishi kerak.

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

Mahalliy muhitda boshqaruv API’sini Swagger orqali ko‘rish mumkin. Sinov xodimlariga kirish parolini faqat mahalliy `backend\dev_env.ps1` faylidagi `DEV_STAFF_PASSWORD` orqali o‘rnating; `DJANGO_DEBUG=True` va `DEV_OTP_ENABLED=True` bo‘lishi shart. Dispetcher: `+998900009901`; haydovchilar: `+998900030001`, `+998900030002`. Parolni kod omboriga qo‘shmang.

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

- `DEV_OTP_ENABLED` odatda o‘chiq tursin. Sinov OTP kodini ishlab chiqarish muhitida yoqmang; Eskiz SMS xizmati ulanmagan.
- `ROUTING_EXTERNAL_ENABLED`, `OSRM_BASE_URL`, `ROUTING_TIMEOUT_SECONDS`, `ROUTE_START_TIME`, `ETA_WINDOW_MINUTES` va `TRIP_CLUSTER_RADIUS_KM` yo‘nalish hisoblash sozlamalaridir. Mahalliy sinovda umumiy OSRM sinov serveri ishlatilishi mumkin; ishlab chiqarish muhitida o‘zingiz boshqaradigan OSRM’dan foydalaning. OpenRouteService’ni ulash uchun alohida moslashtirgich kerak. Umumiy sinov serveridan ishlab chiqarishda foydalanmang. Tashqi yo‘nalish xizmati o‘chirilganida ham zaxira hisob ishlaydi.

## Keyingi qadam

Avval 4C-1, 4C-2 va 4C-3 sahifalarining foydalanuvchi oqimi sinovlarini, shuningdek do‘konchining oxirgi buyurtmani takrorlash sinovini yozish. Keyin haydovchining yetkazish amallari va tegishli server sinovlarini bajarish; undan so‘ng PWA va oflayn sinxronlashni boshlash.
