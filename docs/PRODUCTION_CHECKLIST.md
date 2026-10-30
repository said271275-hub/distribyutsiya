# Ishlab chiqarishga chiqarish tekshiruv ro‘yxati

Har bir band bajarilganini operator dalil bilan tasdiqlasin. Ishlab chiqarish
serveriga sinov yoki mahalliy buyruqlarni yo‘naltirmang.

## Sozlamalar va maxfiy qiymatlar

- [ ] `DJANGO_ENV=production` va `DJANGO_DEBUG=False`; Django ishlab chiqarish
  sozlamalari bilan `DEBUG=True` bo‘lsa ishga tushishni rad etishi tekshirildi.
- [ ] `DJANGO_SECRET_KEY` yangi va tasodifiy; avvalgi muhitda ishlatilmagan,
  kod omboriga qo‘shilmagan va jurnalda ko‘rinmaydi.
- [ ] `DEV_OTP_ENABLED=False`; `DEV_STAFF_PASSWORD` bo‘sh. Har ikkala
  ishlab chiqish sozlamasi ishlab chiqarishda ishga tushishni to‘xtatishi
  tasdiqlandi.
- [ ] `OTP_PROVIDER=apps.accounts.sms.EskizOtpProvider`; Eskiz sozlanmagan
  bo‘lsa ishlab chiqarish ishga tushmasligi tekshirildi.
- [ ] Domenlar `DJANGO_ALLOWED_HOSTS` ichida aniq ko‘rsatilgan; yulduzcha
  ishlatilmagan.
- [ ] `DJANGO_CSRF_TRUSTED_ORIGINS` ichidagi har bir manzil `https://` bilan
  boshlanadi. CORS qo‘shilgan bo‘lsa, u ham faqat kerakli HTTPS manzillari.
- [ ] `DJANGO_SECURE_SSL_REDIRECT=True`, `DJANGO_SECURE_COOKIES=True`,
  `AUTH_COOKIE_SECURE=True`, HSTS kamida bir yil; ishlab chiqarish sozlamasi
  ushbu talablarni o‘zi ham tekshiradi.
- [ ] HSTS subdomenlar va oldindan yuklash sozlamalari faqat barcha tegishli
  subdomenlar HTTPS ishlatishi tasdiqlanganda yoqiladi; aks holda tegishli
  `check --deploy` ogohlantirishlari ongli ravishda qabul qilinadi.
- [ ] Kirish yangilash cookie’si `Secure`, `HttpOnly`, `SameSite=Lax`;
  sessiya cookie’si ham `Secure` va `HttpOnly`.
- [ ] Yordamchi muhit fayli faqat bo‘sh namunaviy qiymatlar bilan kuzatiladi;
  haqiqiy `/etc/distribyutsiya/production.env` maxfiy, `0640` yoki undan
  qattiq huquqqa ega va Git’dan tashqarida.

## Tarmoq va kirish nazorati

- [ ] HTTPS sertifikati amalda; HTTP so‘rovi HTTPS’ga yo‘naltiriladi; PWA
  HTTPS orqali ochiladi.
- [ ] `/api/docs/` va `/api/schema/` `DEBUG=False` da yopiq ekanligi
  tekshirildi.
- [ ] `/admin/` faqat Nginx boshqaruv IP ro‘yxatidagi manzillardan ochiladi;
  ro‘yxatda keraksiz manzil yo‘q.
- [ ] Nginx kirish, OTP, ro‘yxatdan o‘tish va tiklash yo‘llariga tezlik
  cheklovini qo‘llaydi; serverdagi telefon bo‘yicha kirish va OTP cheklovlari
  ham faol.
- [ ] Nginx 80/443-portlargagina ochiq; Gunicorn `127.0.0.1:8000` da.
- [ ] PostgreSQL `localhost` orqali tinglaydi; 5432-port tashqi tarmoqqa
  yopiq. Ilova roli faqat o‘z bazasiga ega, superuser emas.

## Ma’lumotlar va xizmatlar

- [ ] Ishlab chiqarish bazasi sinov uchun ishlatilmaydi; migratsiyadan oldin
  ma’lumotlar bazasi va media zaxirasi muvaffaqiyatli olingan.
- [ ] `seed_demo` bajarilmagan; demo akkauntlari, jumladan
  `+998900009901`, `+998900030001` va `+998900030002`, bazada yo‘q.
- [ ] `distribyutsiya-web` va `distribyutsiya-sms` `systemd` xizmatlari faol.
- [ ] Takroriy buyurtma, kunlik tozalash va zaxira `systemd` taymerlari
  yoqilgan; keyingi ish vaqti ko‘rinadi.
- [ ] Eskiz uchun ishlab chiqarish sozlamalari xavfsiz kiritilgan; SMS
  shablonlariga tegilmagan va ularning matni tasdiqlanmagan holda
  o‘zgartirilmagan.
- [ ] Tashqi marshrutlash o‘chiq yoki faqat o‘zingiz boshqaradigan OSRM
  manziliga yo‘naltirilgan; ommaviy xizmatni ishlatishdan avval koordinatlar
  tashqariga yuborilishini hisobga oling.
- [ ] `STATIC_ROOT` va `MEDIA_ROOT` to‘g‘ri; Nginx statik va media fayllarni
  kerakli huquqlar bilan xizmat qiladi.
- [ ] Ilova va Nginx jurnallarida parol, token, OTP, to‘liq telefon raqami yoki
  so‘rov tanasi yo‘qligi tekshirildi.
- [ ] Birinchi boshqaruvchi hisobi yaratildi; uning paroli ombor yoki
  jurnallarga kiritilmadi.

## Zaxira, tiklash va tekshiruv

- [ ] `age` ochiq qabul qiluvchi qiymati muhitda; maxfiy ochish kaliti
  serverdan alohida joyda saqlanadi.
- [ ] Kunlik zaxira PostgreSQL va media’ni alohida shifrlaydi, 30 kundan eski
  mahalliy nusxalarni o‘chiradi, shifrlangan nusxalar esa serverdan tashqariga
  ham uzatiladi.
- [ ] Eng so‘nggi baza zaxirasini ochib ro‘yxatini o‘qish, media zaxirasini
  ochib tarkibini ko‘rish sinovi bajarildi.
- [ ] Baza alohida sinov bazasiga tiklandi; media alohida sinov papkasiga
  tiklandi. Ishlab chiqarish ma’lumotlari mahalliy yoki avtomatik sinovga
  berilmadi.
- [ ] Joylashtirishdan avval `manage.py check --deploy`, server sinovlari,
  veb sinovlari va `npm run build` bajarilib, natijalar qayd qilindi.

Sinov foydalanuvchilari, soxta SMS xizmati yoki demo ma’lumotlarini
ishlab chiqarish ma’lumotlariga aralashtirmang.
