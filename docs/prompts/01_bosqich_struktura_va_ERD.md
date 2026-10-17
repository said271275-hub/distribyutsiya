# 1-BOSQICH: Loyiha strukturasi, ma'lumotlar bazasi (ERD) va API sxemasi

(Avval `00_umumiy_kontekst.md` ni bering, keyin shuni.)

## Maqsad
Hech qanday interfeys yozmasdan, loyihaning **poydevorini** qur: papka tuzilishi, Django modellari, ERD va API sxemasi.

## Nima qilish kerak

1. **Papka tuzilishi:** `backend/` (Django + DRF, ilovalar: `accounts`, `companies`, `catalog`, `orders`, `logistics`, `payments`, `audit`) va `frontend/` (Vite + React + Tailwind bo'sh skelet). Docker Compose (PostgreSQL + backend), `.env.example`.
2. **Ma'lumotlar bazasi sxemasi (ERD)** matn yoki Mermaid diagramma ko'rinishida. Men tasdiqlamaguncha modellarga o'tma.
3. **Django modellari** (har bir kompaniyaga bog'liq jadvalda `company` majburiy):
   - `Company`: nomi, logo, brend rangi, aloqa telefoni, faol/nofaol.
   - `User` (custom): telefon bilan kirish, `role` (super_admin, company_admin, driver, shop_owner), faol/bloklangan, o'chirish holati.
   - `Shop`: egasi (User), nomi, 1-2 telefon, manzil, tuman, kenglik/uzunlik (lat/lng), holat; bitta telefon = bitta do'kon.
   - `CompanyShopLink` (do'kon qaysi kompaniyalar bilan ishlaydi), `ShopPrice` (do'kon uchun alohida narx/chegirma).
   - `Product`: kompaniya, nomi, rasm, birlik (dona/quti/blok), narx, faol.
   - `Order` va `OrderItem`: do'kon, kompaniya, holat (yangi, tasdiqlandi, yuklandi, yo'lda, yetkazildi, bekor), yetkazish sanasi, vaqt oralig'i, jami narx.
   - `Vehicle` (sig'im), `DriverProfile`, `Trip` (reys: sana, mashina, haydovchi), `TripStop` (reysdagi do'kon, tartib, ETA, haqiqiy yetkazilgan vaqt, izoh).
   - `Payment` va do'kon qarz balansi (nasiya), `ReturnableContainer` (tara hisobi).
   - `AuditLog`, `DeletionRequest` (akkaunt o'chirish: sabab, 30 kunlik muddat).
4. **API sxemasi:** endpointlar ro'yxati (URL, metod, kim kira oladi, kirish/chiqish maydonlari) jadval ko'rinishida, hali kod yozmasdan. OpenAPI (Swagger) sozlansin.
5. **Seed ma'lumotlar** (management command): 1 kompaniya, 10 mahsulot, 20 test do'kon (Sirdaryo koordinatalari bilan), 2 mashina, 2 haydovchi, 1 dispetcher.
6. Modellar uchun migratsiyalar va asosiy testlar (kompaniya izolyatsiyasi modeli darajasida).

## Qabul mezoni
- `docker compose up` bilan baza va backend ishga tushadi, migratsiyalar xatosiz o'tadi.
- Seed buyrug'i test ma'lumotlarni yaratadi.
- ERD va API jadvali hujjat ko'rinishida (`docs/`) mavjud.
- Hech qanday UI yozilmagan.

## Qilma
Autentifikatsiya, frontend sahifalari va marshrutlash logikasini hozir yozma, ular keyingi bosqichlarda.
