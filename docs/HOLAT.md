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
- **6-bosqich, SMS (Eskiz) — bajarildi:** ro‘yxatdan o‘tish va kirish OTP kodi,
  buyurtma holati SMS’lari, do‘konchi uchun bildirishnoma sozlamasi va
  xabarlarni navbatdan qayta yuborish qo‘shildi. Eskiz haqiqiy chaqiruvi
  maxfiy muhit sozlamalari va tasdiqlangan SMS matnlari mavjud bo‘lganda ishlaydi.
- **6-bosqich, hisobotlar — bajarildi:** dispetcher/admin uchun yetkazilgan
  savdo, bekor qilingan va muammoli buyurtmalar, qarzdorlar va oldindan
  to‘lovlar, haydovchilar hamda mahsulotlar bo‘yicha o‘qish hisobotlari va
  Excel’da ochiladigan CSV eksporti qo‘shildi.
- **6-bosqich, takroriy buyurtmalar — bajarildi:** do‘konchi haftalik jadval
  yaratadi, tahrirlaydi, pauza qiladi yoki arxivlaydi. Tizim kelgusi yetkazish
  kunlari uchun tasdiqlash kutilayotgan qoralamalarni yaratadi; tasdiqlanmagan
  qoralamalar buyurtma, reys yoki qarzga ta’sir qilmaydi.
  `create_recurring_orders` buyrug‘i dublikat yaratmaydi, tasdiqlash esa amaldagi
  narx va chegirmani, kompaniya aloqasini hamda buyurtma vaqt chegarasini qayta
  tekshiradi.
- **6-bosqich, ombor hisobi — bajarildi:** mahsulot qoldig‘i o‘chirilmaydigan
  harakatlar jurnalidan hisoblanadi, tezkor qoldiq esa jurnal yig‘indisiga mos
  yangilanadi. Dispetcher kirim, chiqim va sababli tuzatish kiritadi, mahsulot
  harakatlarini ko‘radi va xato yozuvni teskari yozuv bilan tuzatadi. Minimal
  qoldiq ogohlantirishi hamda reys tasdiqlashdagi zaxira, yetkazilgan miqdor
  chiqimi, yetkazilmagan qismni va muammoli/bekor qilingan reysdagi zaxirani
  qaytarish qo‘shildi.
- **6-bosqichning qolgan imkoniyatlari — bajarilmagan:** yetkazish isboti va
  ishlab chiqarishga chiqarish.

## Sinovlar va tekshirilmagan ishlar

- Ombor va reys oqimi bo‘yicha maqsadli server sinovlaridan **31** tasi o‘tdi.
  Veb sinovlaridan **44** tasi o‘tdi va veb to‘plami yig‘ildi.
- To‘liq server sinovlarida **150** ta topilib, **146** tasi bajarildi; **8**
  xato bilan yakunlandi. Ulardan biri hisobot sinovining 18:00 buyurtma
  chegarasidan keyin bajarilganidir; yana biri mavjud `reset_dev_users`
  sinovidagi mahsulot berilmagan buyurtma bandidir. Qolgan **6** xato takroriy
  buyurtma va SMS sinovlarida PostgreSQL’ning `FOR UPDATE` so‘rovidagi mavjud
  tashqi ulanish cheklovidan kelib chiqdi. Ombor/reys maqsadli sinovlari to‘liq
  o‘tdi.
- Veb tekshiruv vositasi avvaldan mavjud to‘rtta ogohlantirishni ko‘rsatdi;
  yangi ombor sahifasi bo‘yicha ogohlantirish chiqmadi.
- Oxirgi buyurtmani takrorlash, dispetcherning buyurtmani boshqarish, reysni tuzish va 4C-3 sahifalarining to‘liq foydalanuvchi oqimlari uchun veb sinovlari yetishmaydi.
- Haydovchi oynasining hozirgi ko‘rinishi bor, ammo haydovchining yetkazish amallari va oflayn sinxronlash tekshirilmagan, chunki ular hali yozilmagan.
- Eskiz SMS provayderi mock bilan sinovdan o‘tkaziladi; haqiqiy SMS yuborish
  maxfiy Eskiz sozlamalari va akkauntda tasdiqlangan SMS matnlarini talab qiladi.
  SMS navbatining doimiy qayta ishlashi uchun `process_sms_outbox --loop`
  buyrug‘i alohida ishchi sifatida ishlashi kerak. Docker orqali ishga tushirish
  tekshirilmagan.
- Takroriy buyurtma qoralamalarini har kuni yaratish va muddati o‘tganlarini
  yangilash uchun `python manage.py create_recurring_orders` buyrug‘ini kuniga
  bir marta ishga tushiring. Buyruq o‘z-o‘zidan rejalashtirilmaydi; avtomatik
  ishga tushirish joylashtirish sozlamasida bajariladi.
- Reys sig‘imi barcha mahsulotlarda vazn bo‘lsa vazn, aks holda barcha mahsulotlarda hajm bo‘yicha tekshiriladi. O‘lchovlar aralash yoki yetishmasa sig‘im noma’lum deb qoladi.

## Ochiq qarorlar

- Qarz yozish qoidasi tasdiqlandi: qarz buyurtma yetkazilganda, faqat yetkazilgan miqdor bo‘yicha yoziladi. Yetkazilmagan, bekor qilingan yoki do‘kon qabul qilmagan buyurtmaga qarz yozilmaydi. Yetkazilgandan keyingi bekor qilish teskari balans yozuvi bilan qaytariladi; `ShopBalance` jurnaldagi o‘tkazilgan yozuvlar yig‘indisiga teng bo‘lishi kerak.
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

- `DEV_OTP_ENABLED` odatda o‘chiq tursin. Sinov OTP kodini ishlab chiqarish muhitida yoqmang. Eskiz sozlamalarini faqat muhit o‘zgaruvchilarida saqlang.
- `ROUTING_EXTERNAL_ENABLED`, `OSRM_BASE_URL`, `ROUTING_TIMEOUT_SECONDS`, `ROUTE_START_TIME`, `ETA_WINDOW_MINUTES` va `TRIP_CLUSTER_RADIUS_KM` yo‘nalish hisoblash sozlamalaridir. Mahalliy sinovda umumiy OSRM sinov serveri ishlatilishi mumkin; ishlab chiqarish muhitida o‘zingiz boshqaradigan OSRM’dan foydalaning. OpenRouteService’ni ulash uchun alohida moslashtirgich kerak. Umumiy sinov serveridan ishlab chiqarishda foydalanmang. Tashqi yo‘nalish xizmati o‘chirilganida ham zaxira hisob ishlaydi.

## Keyingi qadam

Avval 4C-1, 4C-2 va 4C-3 sahifalarining foydalanuvchi oqimi sinovlarini, shuningdek do‘konchining oxirgi buyurtmani takrorlash sinovini yozish. Keyin haydovchining yetkazish amallari va tegishli server sinovlarini bajarish; undan so‘ng PWA va oflayn sinxronlashni boshlash.
