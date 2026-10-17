# 5-BOSQICH: Haydovchi paneli va PWA (offline imkoniyat)

(Avval `00_umumiy_kontekst.md`, keyin shuni. 1-4 bosqichlar tayyor bo'lishi kerak.)

## Maqsad
Haydovchi/yuklovchi daftarsiz, faqat telefon bilan ishlasin. Sirdaryodagi sust yoki uzilib qoladigan internetda ham asosiy funksiyalar ishlasin.

## Backend

1. Haydovchi API: faqat **o'z bugungi reysi** (yuklash ro'yxati, to'xtashlar tartibi, do'kon nomi, manzil, lat/lng, telefon). Reys tugagach kirish yopiladi.
2. Yuklash belgisi (har mahsulot "yuklandi"), reysni boshlash ("yo'lga chiqdi").
3. Har bir to'xtash uchun: **"Yetkazildi"** (haqiqiy vaqt va GPS nuqta bilan), qisman yetkazish (nechta berildi), muammo izohi (do'kon yopiq, pul yo'q va h.k.), to'lov olindi belgisi, qaytarilgan tara miqdori.
4. Oflayn belgilashlar uchun **sinxronlash endpoint'i** (bir nechta voqeani birdan qabul qiladi, takroriy yuborishdan himoya, ziddiyatni hal qilish qoidasi).
5. Holat o'zgarganda do'konchiga ko'rinadigan holat yangilanadi (Yo'lda, Yetkazildi).
6. Haydovchi boshqa haydovchi reysini ko'ra olmasligi testlari.

## Frontend (mobil-birinchi)

1. **Bugungi reys:** yuklash ro'yxati (checkbox bilan), yig'ilgan/yuklangan progress.
2. **Marshrut:** keyingi do'kon katta kartada: nomi, manzil, ETA, kerakli mahsulotlar. Tugmalar: **"Qo'ng'iroq qilish"** (`tel:`), **"Xaritada ochish"** (Google Maps / Yandex Navigator link), **"Yetkazildi"**.
3. Yetkazish oynasi: miqdor tasdiqlash, to'lov, tara qaytarish, izoh, ixtiyoriy imzo yoki GPS belgisi.
4. Katta tugmalar, yuqori kontrast (quyoshda o'qiladigan), bir qo'lda ishlatishga qulay.
5. **PWA:**
   - `manifest.json` va ikonlar, "Bosh ekranga qo'shish" taklifi (do'konchi va haydovchi uchun).
   - Service worker: ilova qobig'i (app shell) va bugungi reys ma'lumotlari keshlanadi, **oflayn rejimda** ro'yxatni ko'rish va "yetkazildi" belgilash mumkin.
   - Oflayn bajarilgan harakatlar IndexedDB'da navbatda turadi va internet qaytganda avtomatik sinxronlanadi; foydalanuvchiga "Oflayn / Sinxronlanmoqda / Sinxronlandi" holati ko'rsatiladi.
6. Real vaqt yangilanish: dispetcher reysni o'zgartirsa, haydovchi ekrani yangilanadi (polling yoki WebSocket, tavsiya ber).

## Qabul mezoni
- Haydovchi telefonida PWA o'rnatib, reysni ochib, internetni o'chirgan holda 3 ta do'konni "yetkazildi" qila oladi; internet qaytganda hammasi serverga tushadi.
- Dispetcher va do'konchi yangi holatlarni ko'radi.
- Lighthouse PWA tekshiruvi o'tadi.
- Haydovchi faqat o'z reysini ko'radi.

## Keyin
Shundan keyin 6-bosqich (SMS/Telegram, hisobotlar, takroriy buyurtmalar va h.k.) boshlanadi.
