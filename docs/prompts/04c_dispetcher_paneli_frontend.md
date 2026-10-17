# 4C-QISM: Dispetcher paneli (frontend, xarita, marshrut ko'rinishi)

(Avval `00_umumiy_kontekst.md` va `docs/HOLAT.md` ni o'qi. 4A va 4B qismlar tayyor bo'lishi kerak. Faqat shu qismni bajar. Katta so'rovlardan qoch, kredit limiti kichik: avval skelet va asosiy sahifalar, keyin xarita va reys ekrani.)

## Maqsad
Dispetcher bitta panelda ertangi buyurtmalarni, jami yuklash ro'yxatini, reyslarni va marshrutni ko'rib boshqarsin.

## Vazifalar

1. **Panel skeleti:** `/staff/login` orqali kirgan dispetcher/admin uchun alohida panel (yon menyu, mobil/planshetda ham ishlaydi). Rolga qarab menyu (haydovchi bu panelga kira olmaydi). Marshrutlar ProtectedRoute bilan himoyalangan.
2. **Dashboard:** kartalar: bugungi buyurtmalar soni, jami hajm, yetkazilgan/kutilayotgan, kechikkan to'xtashlar; reyslar bo'yicha qisqa holat.
3. **Buyurtmalar jadvali:** filtr (sana, tuman, holat, do'kon), qidiruv, sahifalash, holat o'zgartirish, ommaviy tasdiqlash, bekor qilish (sabab so'raladi). Buyurtma tafsiloti va holat tarixi.
4. **Reys tuzish ekrani:** chapda buyurtmalar ro'yxati, o'ngda **xarita (react-leaflet + OpenStreetMap)** do'kon pinlari bilan. Do'konlarni reysga tanlab/sudrab biriktirish, "avtomatik guruhlash" tugmasi (taklifni ko'rsatadi, dispetcher tasdiqlaydi yoki o'zgartiradi), mashina sig'imi indikatori (oshganda ogohlantirish), mashina va haydovchi tanlash.
5. **Marshrut ko'rinishi:** xaritada yo'l chizig'i, to'xtashlar tartibi (raqamlangan), har biri uchun ETA va vaqt oralig'i, reysni tasdiqlash tugmasi.
6. **Yuklash ro'yxati sahifasi:** mahsulotlar bo'yicha jami miqdor, chop etish (print) uchun toza ko'rinish.
7. **Boshqaruv sahifalari:** do'konlar (xaritada ham), mahsulotlar va narxlar, mashinalar, haydovchilar va xodimlar (yaratish, bloklash), qarz va to'lov kiritish (do'kon qarz balansi, qarzdorlar ro'yxati).
8. **Sifat:** skeleton yuklanish holatlari, xato va bo'sh holat sahifalari, o'zbekcha xabarlar, dark/light rejim, React Hook Form + Zod, TanStack Query. Tailwind bilan bir xil dizayn uslubi (do'konchi panelidagi kabi).
9. **Testlar:** asosiy komponentlar va himoyalangan marshrutlar uchun (rol cheklovi, reys tuzish oqimi), frontend build toza.

## Qabul mezoni
- Dispetcher `/staff/login` orqali kirib, ertangi buyurtmalardan avtomatik reyslar tuzadi, yuklash ro'yxatini va ETA'li marshrutni xaritada ko'radi.
- Sig'imdan oshganda tizim ogohlantiradi.
- Reys tasdiqlansa, do'konchi o'z panelida buyurtma holati va yetib borish vaqtini ko'radi.
- Frontend testlari va build muvaffaqiyatli; brauzerda qo'lda tekshirish qadamlari ro'yxatini ber.

## Qilma
Haydovchi paneli va PWA hozir kerak emas (5-bosqich).
