# 4A-QISM: Admin API, xodimlar, yuklash ro'yxati va to'lov/qarz (faqat backend)

(Avval `00_umumiy_kontekst.md` va `docs/HOLAT.md` ni o'qi. 1-3 bosqichlar tayyor. Faqat shu qismni bajar: marshrutlash, reys tuzish va frontend keyingi qismlarda. Katta so'rovlardan qoch, kredit limiti kichik.)

## Maqsad
Dispetcher/admin uchun asosiy boshqaruv API'sini qur: buyurtmalar, katalog va narxlar, do'konlar, transport, xodimlar, to'lov va qarz, hamda yuklash ro'yxati.

## Vazifalar

1. **Buyurtmalar (admin):** ro'yxat (filtr: sana, tuman, holat, do'kon; qidiruv; sahifalash), tafsilot, holatni o'zgartirish (Yangi → Tasdiqlandi → Yuklandi → Yo'lda → Yetkazildi / Bekor), tasdiqlash/bekor qilish (sabab bilan), ommaviy tasdiqlash. Holat o'zgarishlari tarixi (kim, qachon, qaysi holatdan qaysisiga) saqlansin va audit logga yozilsin.
2. **CRUD (faqat o'z kompaniyasi doirasida):** mahsulotlar, do'kon narxi/chegirmasi (`ShopPrice`), do'konlar (arxivlash, o'chirish emas), mashinalar, haydovchilar.
3. **Xodim yaratish:** admin dispetcher va haydovchi akkauntini yaratadi (telefon, rol, vaqtinchalik parol, kompaniyaga bog'lash). `company_admin` `super_admin` rolini bera olmaydi, boshqa kompaniyaga xodim qo'sha olmaydi. Xodimni bloklash/faolsizlantirish bor.
4. **Lokal sinov uchun xodim parollari:** seed'dagi dispetcher va haydovchilar `/staff/login` orqali kira olishi uchun parolni `DEV_STAFF_PASSWORD` (dev_env.ps1) dan o'rnatadigan xavfsiz usul. Faqat `DEBUG=True` va `DEV_OTP_ENABLED=True` bo'lganda ishlasin, production'da ishlamasin (ishga tushishda xato bersin). Qaysi telefon raqamlar kimniki ekanini ayt.
5. **To'lov va qarz (nasiya):**
   - To'lovni **faqat kompaniya xodimlari** kiritadi (admin/dispetcher, haydovchi esa faqat o'z reysidagi do'kondan pul olganda). Do'konchi to'lov yarata olmaydi, faqat o'z qarz balansi va tarixini ko'radi.
   - Har to'lov va buyurtma `BalanceEntry` (ledger) yozuvini yaratadi, `ShopBalance` yangilanadi; to'lov qattiq o'chirilmaydi.
   - Do'kon uchun qarz limiti: limitdan oshsa yangi buyurtma tasdiqlashda ogohlantirish (dispetcher qaror qiladi).
6. **Yuklash ro'yxati (picking list):** tanlangan kun yoki reys uchun mahsulotlar bo'yicha jami miqdor (masalan Coca-Cola 1.5L: 240 quti), birlik bo'yicha, mashina sig'imi bilan solishtirish uchun jami hajm/og'irlik maydoni (agar mahsulotda bo'lsa).
7. **Xavfsizlik tekshiruvlari:**
   - Dispetcher faqat o'z kompaniyasiga ulangan do'konlarni (`CompanyShopLink`) va faqat o'z kompaniyasi buyurtmalarini ko'radi.
   - `/api/docs/` va `/api/schema/` production'da yopiq.
   - Har bir admin harakati audit logda.
8. **Testlar:** kompaniya izolyatsiyasi (A kompaniya admini B ma'lumotini ko'ra olmaydi), rol cheklovlari, to'lovni do'konchi yarata olmasligi, picking list yig'indisi to'g'riligi, holat o'tishlari (noto'g'ri o'tish rad etiladi).

## Qabul mezoni
- Swagger'da barcha yangi endpointlar ko'rinadi va ishlaydi (lokalda).
- Barcha backend testlari o'tadi, natijani ko'rsat.
- Seed dispetcher `/staff/login` orqali kira oladi.

## Qilma
Marshrutlash, guruhlash, reys, xarita va frontend sahifalarini hozir yozma.
