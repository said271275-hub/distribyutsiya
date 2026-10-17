# 4B-QISM: Reyslar, avtomatik guruhlash, marshrut va ETA (faqat backend)

(Avval `00_umumiy_kontekst.md` va `docs/HOLAT.md` ni o'qi. 4A-qism tayyor bo'lishi kerak. Faqat shu qismni bajar: frontend va xarita sahifalari 4C-qismda. Katta so'rovlardan qoch, kredit limiti kichik.)

## Maqsad
Tasdiqlangan buyurtmalarni reyslarga bo'lish, har reys uchun marshrut tartibi va yetib borish vaqtini (ETA) hisoblash, reysni boshqarish va dashboard ma'lumotlarini berish.

## Vazifalar

1. **Reys boshqaruvi:** reys yaratish (sana, mashina, haydovchi), to'xtash nuqtasi (`TripStop`) qo'shish/olib tashlash/qayta tartiblash, bir `TripStop`ga bir nechta buyurtma bog'lash (`TripStopOrder`). Mashina va haydovchi reys kompaniyasiga tegishli bo'lishi shart. Reysni tasdiqlash: tasdiqlanganda buyurtmalar "Tasdiqlandi" bo'ladi va do'konchiga ko'rinadigan yetib borish vaqti oralig'i yoziladi. Reysni bekor qilish va buyurtmalarni qayta tarqatish mumkin.
2. **Avtomatik guruhlash algoritmi:**
   - Tanlangan kunning tasdiqlangan buyurtmalarini tuman va lokatsiya yaqinligi bo'yicha reyslarga bo'lish (oddiy va tushunarli usul tanlang, masalan tuman bo'yicha, keyin geografik klasterlash; tanlovni qisqa asoslab bering).
   - **Mashina sig'imi tekshiruvi:** sig'imdan oshsa ogohlantirish, qolgan buyurtmalarni keyingi reysga taklif qilish.
   - Natija **taklif** sifatida qaytadi (saqlashdan oldin dispetcher ko'radi va o'zgartiradi: do'konni boshqa reysga ko'chirish mumkin).
3. **Marshrut tartibi va ETA:**
   - Do'konlar orasidagi masofa/vaqt OSRM orqali (sozlanadigan URL, standart: OSRM ommaviy demo serveri faqat lokal sinov uchun, productionda o'z serveringiz yoki OpenRouteService; shuni README'ga yoz).
   - Eng qisqa tartib: nearest-neighbor yoki undan yaxshiroq heuristika; sodda va tushunarli bo'lsin.
   - Har `TripStop` uchun taxminiy yetib borish vaqti (ETA) va **vaqt oralig'i** (masalan 14:00–15:30). Do'konga to'xtash/tushirish vaqti sozlama bo'lsin (kompaniya sozlamasi).
   - **OSRM ishlamasa zaxira:** to'g'ri chiziq masofasi va o'rtacha tezlik bo'yicha taxmin; tashqi tarmoqqa chiqish sozlamasi o'chirilsa ham tizim ishlasin.
   - Do'konchi buyurtma holati/ETA'ni o'z panelida ko'ra oladigan API tayyor bo'lsin.
4. **Dashboard ma'lumotlari (API):** bugungi buyurtmalar soni, jami hajm, yetkazilgan va kutilayotgan, kechikkan to'xtashlar, reyslar bo'yicha holat.
5. **Xavfsizlik:** barcha endpointlar kompaniya doirasida; haydovchi faqat o'z reysini ko'radi (o'qish); tashqi OSRM so'rovlarida foydalanuvchi shaxsiy ma'lumoti (ism, telefon) yuborilmasin, faqat koordinatalar.
6. **Testlar:** guruhlash (sig'im chegarasi, bo'sh kun, bitta do'konga ko'p buyurtma), marshrut tartibi (kichik qo'lda tekshiriladigan misol bilan), ETA hisobi, OSRM zaxira rejimi (tashqi so'rovni mock qil), kompaniya izolyatsiyasi, reys tasdiqlanganda holat o'zgarishi.

## Qabul mezoni
- Swagger orqali: tasdiqlangan buyurtmalar uchun guruhlash taklifi olinadi, reys saqlanadi, marshrut va ETA hisoblanadi.
- Sig'imdan oshganda API ogohlantirish qaytaradi.
- OSRM o'chiq bo'lsa ham zaxira rejimda ishlaydi.
- Barcha backend testlari o'tadi, natijani ko'rsat.

## Qilma
Frontend sahifalari va xaritani hozir yozma (4C-qism).
