# Foydalanuvchi qismi

React + TypeScript + Vite mijoz dasturi. U server bilan `/api/` ostidagi
REST manzillari orqali ishlaydi; ishlab chiqish vaqtida Vite bu so‘rovlarni
serverga yo‘naltiradi. Tailwind CSS Vite qo‘shimchasi orqali sozlangan.

## Mahalliy ishga tushirish

```powershell
npm.cmd install
npm.cmd run dev
```

Vite serveri `http://localhost:5173` manzilida ishlaydi. Ishlab chiqarish
uchun yig‘ilmani tayyorlash uchun `npm.cmd run build` buyrug‘ini bajaring.

Mijoz dasturida do‘kon egalari va xodimlar uchun alohida kirish, telefon va
bir martalik kod orqali ro‘yxatdan o‘tish, rol bo‘yicha himoyalangan namunaviy
oynalar hamda hisobni o‘chirish va tiklash jarayoni bor. Yangilash belgisi
HttpOnly brauzer cookie’sida saqlanadi; kirish belgilari xotirada turadi va
API vositasi orqali yangilanadi. Katalog, buyurtma va reys sahifalari bu
bosqichga kirmaydi. Ma’lumotlar bazasiga kirish va maxfiy qiymatlar server
tomonida bo‘lishi, brauzer kodiga kiritilmasligi kerak.
