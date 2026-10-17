# Distribyutsiya boshqaruv tizimi

Django REST API, React + TypeScript foydalanuvchi oynasi va PostgreSQL bilan
mahalliy ishlab chiqish uchun boshlang‘ich loyiha tuzilmasi.

## Docker Compose orqali ishga tushirish

Docker Desktop o‘rnatilgan bo‘lishi kerak. Loyihaning asosiy jildida:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

So‘ng foydalanuvchi oynasini `http://localhost:5173`, server API’sini
`http://localhost:8000/api/health/`, Swagger hujjatlarini esa
`http://localhost:8000/api/docs/` manzilida oching.

To‘xtatish uchun `Ctrl+C`, konteynerlarni o‘chirish uchun `docker compose down`
ishlatiladi. PostgreSQL ma’lumotlari Docker’ning nomlangan saqlash jildida
saqlanadi. Ma’lumotlar jildini o‘chirmasdan tozalash uchun `docker compose down -v`
buyrug‘ini ishlatmang.

Har bir qism bo‘yicha qo‘llanma: [backend/README.md](backend/README.md) va
[frontend/README.md](frontend/README.md).

Loyiha konteksti va tasdiqlangan ERD/API taklifi:
[docs/00_umumiy_kontekst.md](docs/00_umumiy_kontekst.md),
[docs/01_erd_va_api_sxemasi.md](docs/01_erd_va_api_sxemasi.md).

## Eslatma

`.env.example` ichidagi qiymatlar faqat mahalliy ishlab chiqish uchun.
Joylashtirishdan oldin maxfiy kalit va parollarni yangilang, HTTPS hamda
xavfsiz brauzer cookie sozlamalarini yoqing. Ishlab chiqarish serverini
O‘zbekistondagi ma’lumotlar markaziga joylashtirish zarurmi — bu bosqichda
huquqiy talablar yoki xizmat ko‘rsatuvchilar tekshirilmadi. Joylashtirishdan
oldin O‘zbekistonning amaldagi shaxsiy ma’lumotlar talablarini va server
joylashuvini mutaxassis bilan tekshiring.
