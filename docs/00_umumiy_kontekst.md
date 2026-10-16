# Distribyutsiya boshqaruv tizimi — umumiy kontekst

## Loyiha maqsadi

Ichimlik va boshqa mahsulotlarni tarqatuvchi kompaniyalar, ularning
do‘konlari, buyurtmalari, yetkazib berish reyslari, to‘lovlari va qaytariladigan
idishlari hisobini yurituvchi tizim yaratish. Ushbu hujjatlar UI yoki
autentifikatsiya oqimini emas, backend poydevori uchun talab va sxema
kelishuvini belgilaydi.

## Rollar

| Rol | Rejalashtirilgan vazifa |
|---|---|
| `super_admin` | Tizim darajasida kompaniyalar va foydalanuvchilarni boshqarish |
| `company_admin` | O‘z kompaniyasi katalogi, do‘konlari, buyurtmalari, jamoasi va hisoblarini boshqarish |
| `driver` | O‘ziga biriktirilgan reys va yetkazib berish nuqtalarini ko‘rish, holatni yangilash |
| `shop_owner` | O‘z do‘koni katalogi, buyurtmalari, qarzi va tara hisobini ko‘rish |

Kirish, tokenlar, sessiyalar va rolga asoslangan route/API poydevori
2-bosqichda amalga oshiriladi; biznes endpointlarida rol va kompaniya
cheklovlari ularning o‘zi 3–4-bosqichda yozilganda qo‘llanadi.

## Asosiy domen qoidalari

- Bir nechta kompaniya bir do‘kon bilan ishlashi mumkin; kompaniyaga xos
  mahsulot narxi va do‘kon chegirmasi alohida saqlanadi.
- Buyurtma aynan bitta kompaniya va bitta do‘konga tegishli. Buyurtma
  pozitsiyasida mahsulot, miqdor va buyurtma vaqtida qo‘llangan narx saqlanadi.
- Kompaniyaga tegishli biznes ma’lumotlari `company` bilan majburiy bog‘lanadi;
  tenant doirasidagi o‘qish va yozish amallari kompaniya bo‘yicha cheklanadi.
- Do‘konning asosiy telefoni unikal; ikkinchi telefon ixtiyoriy va unikal
  bo‘lishi shart emas.
- Bitta do‘kon akkaunti ko‘pi bilan bitta do‘konga ega bo‘ladi.
- Buyurtma holatlari: `new`, `confirmed`, `loaded`, `in_transit`, `delivered`,
  `cancelled`.
- Hisob-kitoblar tarixini yo‘qotmaslik uchun qarz va tara harakatlarini
  o‘tkazmalar jurnali sifatida yuritish taklif qilinadi; joriy balansni
  jurnaldan hisoblash yoki saqlab borish ERD tasdig‘ida kelishiladi.
- Akkauntni o‘chirish so‘rovi sabab va 30 kunlik muddat bilan qayd etiladi;
  so‘rov yuborilishi akkauntni darhol o‘chirmaydi.

## Amalga oshirish chegarasi

Loyiha Django + DRF, PostgreSQL, React + Vite, Docker Compose va
OpenAPI/Swagger uchun sozlangan. 2-bosqichda biznes modellari, migratsiyalar,
seed buyrug‘i, autentifikatsiya, rolga asoslangan kirish himoyasi va tenant
izolyatsiyasi poydevori amalga oshiriladi. `/api/docs/` hamda `/api/schema/`
faqat ishlab chiqish rejimida ochiq.

Katalog, buyurtma, to‘lov va reys biznes endpointlari hamda ularga mos UI
sahifalari 3–4-bosqichlarga qoldiriladi.
