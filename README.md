# Distribyutsiya boshqaruv tizimi

Django REST API, React + TypeScript frontend va PostgreSQL bilan mahalliy
rivojlantirish uchun boshlang‘ich loyiha tuzilmasi.

## Docker Compose orqali ishga tushirish

Docker Desktop o‘rnatilgan bo‘lishi kerak. Loyihaning asosiy papkasida:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

So‘ng frontendni `http://localhost:5173`, backendni
`http://localhost:8000/api/health/`, Swagger hujjatlarini esa
`http://localhost:8000/api/docs/` manzilida oching.

To‘xtatish uchun `Ctrl+C`, konteynerlarni o‘chirish uchun `docker compose down`
ishlatiladi. PostgreSQL ma’lumotlari nomlangan Docker volume’da saqlanadi.
Ma’lumotlar volume’ini o‘chirmasdan tozalash uchun `docker compose down -v`
buyrug‘ini ishlatmang.

Har bir qism bo‘yicha qo‘llanma: [backend/README.md](backend/README.md) va
[frontend/README.md](frontend/README.md).

## Eslatma

`.env.example` ichidagi qiymatlar faqat mahalliy ishlab chiqish uchun.
Joylashtirishdan oldin maxfiy kalit/parollarni yangilang, HTTPS va xavfsiz
cookie sozlamalarini yoqing. Ishlab chiqarish serveri O‘zbekistondagi hostingda
joylashtirilishi kerakmi — bu bosqich doirasida huquqiy talablar yoki hosting
provayderlari tekshirilmadi; joylashtirishdan oldin O‘zbekistonning amaldagi
shaxsiy ma’lumotlar talablari va server lokatsiyasini mutaxassis bilan
tekshiring.
