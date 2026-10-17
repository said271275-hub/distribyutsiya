# 2-BOSQICH: Auth va Multi-Tenant (JWT, ikki alohida kirish, akkaunt hayotiy sikli)

(Avval `00_umumiy_kontekst.md`, keyin shuni. 1-bosqich tayyor bo'lishi kerak.)

## Maqsad
Kirish tizimini, rollarni, kompaniyalar izolyatsiyasini va xavfsizlikni backend va frontendda to'liq sozla.

## Backend

1. **JWT autentifikatsiya:** access (qisqa muddat) + refresh (`HttpOnly`, `Secure`, `SameSite` cookie). Token yangilash va chiqish (logout, refresh'ni bekor qilish).
2. **Do'konchi:** `/register` (telefon + SMS kod/OTP yoki parol; SMS provayder hozircha mock/interfeys, keyin Eskiz.uz ulanadi), `/login`. **Bitta telefon = bitta akkaunt**, takroriy ro'yxatdan o'tish bloklanadi.
3. **Xodimlar:** `/staff/login` alohida endpoint; ro'yxatdan o'tish yo'q; xodimni faqat admin yaratadi.
4. **Multi-tenant middleware/permission:** har so'rovda foydalanuvchi kompaniyasi aniqlanadi, queryset'lar avtomatik `company` bo'yicha filtrlanadi. Boshqa kompaniya ma'lumotiga kirish mumkin emas.
5. **Rol va ob'ekt darajasidagi ruxsatlar** (DRF permission classes): do'konchi faqat o'z ma'lumotini, haydovchi faqat o'z reysini, dispetcher faqat o'z kompaniyasini ko'radi. IDOR himoyasi.
6. **Akkaunt o'chirish (do'konchi):**
   - Profilda "Akkauntni o'chirish": sabab tanlanadi (do'kon yopildi, ko'chdi, kerak emas, boshqa) + parol/SMS kod bilan tasdiq.
   - Ochiq buyurtma yoki to'lanmagan qarz bo'lsa, ruxsat berilmaydi va sababi tushuntiriladi.
   - Tasdiqdan keyin akkaunt bloklanadi, **30 kun kutish muddati**, shu vaqtda qayta tiklash mumkin.
   - 30 kundan keyin shaxsiy ma'lumotlar o'chiriladi/anonimlashtiriladi (buyurtma va to'lov yozuvlari "O'chirilgan do'kon #id" ko'rinishida qoladi). Buni bajaradigan rejalashtirilgan vazifa (management command + cron/Celery).
7. **Himoya:** parol hash (Argon2), login urinishiga limit (5 xatodan keyin vaqtincha blok), SMS kod limiti, audit log (kirish, o'chirish, rol o'zgarishi).
8. **Testlar:** IDOR (A do'kon B do'kon buyurtmasini ocha olmasligi), kompaniya izolyatsiyasi, rol ruxsatlari, akkaunt o'chirish oqimi.

## Frontend

1. Vite + React + Tailwind sozlamalari, React Router, TanStack Query, axios/fetch wrapper (token yangilash avtomatik).
2. Sahifalar: `/login`, `/register` (do'konchi), `/staff/login` (xodim), profil sahifasi (akkauntni o'chirish oqimi bilan).
3. **Himoyalangan marshrutlar (ProtectedRoute):** rolga qarab yo'naltirish. Har rol faqat o'z paneliga o'tadi (hozircha bo'sh panel sahifalari).
4. React Hook Form + Zod validatsiya, o'zbek tilida tushunarli xato xabarlari, telefon raqam maskasi (+998).
5. Mobil-birinchi dizayn, dark/light rejim, yuklanish holati.

## Qabul mezoni
- Do'konchi ro'yxatdan o'tadi, kiradi, chiqadi; xodim `/staff/login` orqali kiradi.
- Do'konchi xodim sahifalariga, xodim esa do'konchi sahifalariga o'ta olmaydi.
- A kompaniya admini B kompaniya ma'lumotini ko'ra olmasligi testda isbotlangan.
- Akkaunt o'chirish oqimi (sabab → tasdiq → 30 kun → anonimlashtirish) ishlaydi.
- Barcha testlar o'tadi.

## Qilma
Katalog, buyurtma va marshrutlash sahifalarini hozir yozma.
