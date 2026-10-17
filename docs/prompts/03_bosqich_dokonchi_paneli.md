# 3-BOSQICH: Do'konchi paneli (profil, katalog, savat, buyurtma)

(Avval `00_umumiy_kontekst.md`, keyin shuni. 1 va 2-bosqichlar tayyor bo'lishi kerak.)

## Maqsad
Do'konchi telefonida qulay ishlaydigan to'liq panel: profilni to'ldirish, katalogdan tanlash, buyurtma berish va kuzatish.

## Backend (API)

1. Do'kon profili: ko'rish/tahrirlash (nomi, egasi, 1-2 telefon, manzil, tuman, lat/lng).
2. Mahsulotlar katalogi: kompaniya bo'yicha, do'kon uchun alohida narx/chegirma hisobga olinadi.
3. Buyurtma yaratish, ko'rish, tahrirlash va bekor qilish (admin tasdiqlamaguncha). Buyurtma tarixi, **"oxirgi buyurtmani takrorlash"**.
4. **Buyurtma qabul qilish vaqti (cut-off):** masalan ertangi yetkazish uchun bugun 18:00 gacha; sozlama kompaniyada. Undan keyin buyurtma yopiladi va tizim aniq xabar beradi.
5. Buyurtma holatlari: Yangi → Tasdiqlandi → Yuklandi → Yo'lda → Yetkazildi / Bekor. Holat o'zgarishi tarixi.
6. Do'konchi qarz balansini va to'lovlar tarixini ko'ra oladi (faqat o'qish).
7. Xavfsizlik: faqat o'z do'koni va buyurtmalari (IDOR testlari), qiymatlar serverda qayta tekshiriladi (narxni klientdan olma).

## Frontend (React + Tailwind)

1. **Profil sahifasi:** forma (React Hook Form + Zod), **xaritada lokatsiya tanlash** (react-leaflet: pin qo'yish + "mening joylashuvim" GPS tugmasi), telefon maskasi.
2. **Katalog:** mahsulot kartalari (rasm, narx, birlik), qidiruv, kompaniya bo'yicha filtr, miqdor tanlash (+/− tugmalar, quti/dona).
3. **Savat va buyurtma formasi:** jami narx avtomatik, yetkazish sanasi va qulay vaqt oralig'i tanlash, izoh maydoni, tasdiqlash oynasi.
4. **Buyurtmalarim:** ro'yxat + holat belgilari (rangli), tafsilot sahifasi, **yetib borish vaqti oralig'i**, haydovchi telefoni, bekor qilish, takrorlash tugmasi.
5. **"Yordam / Aloqa"** tugmasi: bosilganda to'g'ridan-to'g'ri qo'ng'iroq (`tel:` link).
6. Skeleton yuklanish holatlari, xatolik/bo'sh holat sahifalari, mobil-birinchi (katta tugmalar), dark/light rejim.
7. Tillar: o'zbek (lotin) asosiy, rus tili uchun i18n tayyorlab qo'y (tarjimalar fayli).

## Qabul mezoni
- Yangi do'konchi 2 daqiqada ro'yxatdan o'tib, lokatsiya kiritib, birinchi buyurtmasini bera oladi.
- Buyurtma admin ro'yxatida paydo bo'lishi uchun API tayyor (admin UI keyingi bosqichda).
- Cut-off vaqtidan keyin buyurtma berib bo'lmaydi.
- Do'konchi boshqa do'kon buyurtmasini ocha olmasligi testda tasdiqlangan.

## Qilma
Admin/dispetcher paneli va marshrutlashni hozir yozma.
