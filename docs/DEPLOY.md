# Ishlab chiqarish muhitiga joylashtirish

Ushbu qo‘llanma Ubuntu 24.04 LTS o‘rnatilgan bitta VPS uchun yozilgan. Django
Gunicorn orqali, Nginx esa veb fayllar va HTTPS uchun ishlaydi. PostgreSQL
faqat shu serverdan ulanadi. SMS ishchisi va kunlik vazifalar `systemd` orqali
boshqariladi. Buyruqlarni serverda operator bajaradi; ushbu qo‘llanma serverga
ulanmaydi va haqiqiy maxfiy qiymatlarni o‘z ichiga olmaydi.

## 1. Tizim paketlari

```sh
sudo apt update
```

Paketlar ro‘yxatini yangilaydi.

```sh
sudo apt install -y ca-certificates git python3 python3-venv python3-dev build-essential libpq-dev postgresql postgresql-contrib nginx certbot age
```

Django, PostgreSQL, Nginx, sertifikat olish va shifrlangan zaxira uchun zarur
paketlarni o‘rnatadi. Veb yig‘ilmasini serverning o‘zida tayyorlasangiz, Vite
talabiga mos Node.js LTS (22 yoki undan yangisi) va npm ham kerak.

## 2. PostgreSQLni mahalliy ulanishga cheklash va baza yaratish

`/etc/postgresql/16/main/postgresql.conf` faylida tinglash manzilini faqat
mahalliy ulanish qilib belgilang:

```ini
listen_addresses = 'localhost'
password_encryption = 'scram-sha-256'
```

`/etc/postgresql/16/main/pg_hba.conf` faylida mahalliy TCP uchun SCRAM
tekshiruvini qoldiring yoki qo‘shing:

```text
host    all    all    127.0.0.1/32    scram-sha-256
host    all    all    ::1/128         scram-sha-256
```

Bu fayllarni tahrirlash uchun administrator huquqli muharrirni oching:

```sh
sudoedit /etc/postgresql/16/main/postgresql.conf
sudoedit /etc/postgresql/16/main/pg_hba.conf
```

PostgreSQL 16 xizmati sozlamalarni qayta o‘qisin:

```sh
sudo systemctl restart postgresql
```

Ilova uchun alohida rol va baza yarating. Quyidagi buyruq interaktiv
PostgreSQL qobig‘ini ochadi:

```sh
sudo -u postgres psql
```

Qobiq ichida quyidagi SQL va `psql` buyrug‘ini navbat bilan bajaring:

```sql
CREATE ROLE distribyutsiya LOGIN;
\password distribyutsiya
CREATE DATABASE distribyutsiya OWNER distribyutsiya;
REVOKE ALL ON DATABASE distribyutsiya FROM PUBLIC;
\q
```

`\password` yangi rol parolini maxfiy kiritish oynasida o‘rnatadi. Rolga
superuser, rol yaratish yoki baza yaratish huquqini bermang. Ilova roli faqat
o‘z bazasining egasi bo‘ladi; bu Django yangilanishlarini bajara olishi uchun
kerak. PostgreSQL 5432-portini tashqi tarmoqqa ochmang; xavfsizlik devorida
ham ushbu portga tashqi ruxsat bermang.

## 3. Tizim foydalanuvchisi va papkalar

Ilovani root bo‘lmagan alohida foydalanuvchi bilan ishga tushiring:

```sh
sudo adduser --system --group --home /srv/distribyutsiya distribyutsiya
```

Kod va foydalanuvchi yuklaydigan fayllar uchun papkalarni yarating:

```sh
sudo install -d -o distribyutsiya -g www-data -m 0750 /srv/distribyutsiya
sudo install -d -o distribyutsiya -g www-data -m 0750 /srv/distribyutsiya/shared/media
sudo install -d -o distribyutsiya -g www-data -m 0750 /var/backups/distribyutsiya
```

Kodni faqat ishonchli, o‘qish huquqi cheklangan manbadan oling. Maxfiy
tokenlarni Git manziliga yoki buyruq qatoriga qo‘shmang:

```sh
sudo -u distribyutsiya git clone --branch main REPOSITORY_URL /srv/distribyutsiya
```

`REPOSITORY_URL` o‘rniga omborning manzilini kiriting. Agar ombor yopiq bo‘lsa,
serverda cheklangan huquqli o‘qish kalitidan foydalaning; shaxsiy kalitni kod
omboriga joylamang.

Kod va zaxira papkalariga huquqlarni belgilang:

```sh
sudo chown -R distribyutsiya:www-data /srv/distribyutsiya
sudo chown distribyutsiya:www-data /var/backups/distribyutsiya
sudo chmod 0750 /var/backups/distribyutsiya
```

## 4. Python muhiti va maxfiy sozlamalar

Virtual muhit yarating va server talablarini o‘rnating:

```sh
sudo -u distribyutsiya python3 -m venv /srv/distribyutsiya/venv
sudo -u distribyutsiya /srv/distribyutsiya/venv/bin/pip install --upgrade pip
sudo -u distribyutsiya /srv/distribyutsiya/venv/bin/pip install -r /srv/distribyutsiya/backend/requirements.txt
```

Gunicorn belgilangan talablar ichida o‘rnatiladi. Maxfiy qiymatlarni faqat
serverdagi muhit fayliga kiriting:

```sh
sudo install -d -o root -g distribyutsiya -m 0750 /etc/distribyutsiya
sudo install -o root -g distribyutsiya -m 0640 /srv/distribyutsiya/.env.production.example /etc/distribyutsiya/production.env
sudoedit /etc/distribyutsiya/production.env
```

Faylda `DJANGO_ENV=production`, `DJANGO_DEBUG=False`, aniq domenlar,
HTTPS manzillari, PostgreSQL qiymatlari, Eskiz sozlamalari, yangi
`DJANGO_SECRET_KEY`, `AUTH_COOKIE_SECURE=True` va bo‘sh bo‘lmagan
`BACKUP_AGE_RECIPIENT` bo‘lishi shart. `DJANGO_SECRET_KEY` uchun serverda
Django’ning tasodifiy kalit yaratuvchisini ishlating; uni chatga yoki kod
omboriga yubormang. Maxfiy qiymatlarni muhit faylida `systemd` ning
`EnvironmentFile` qoidasiga muvofiq yozing; qiymatlarni buyruq qatoriga
qo‘ymang.

```sh
/srv/distribyutsiya/venv/bin/python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

`DEV_OTP_ENABLED=False` bo‘lsin va `DEV_STAFF_PASSWORD` bo‘sh qolishi kerak.
Eski, boshqa muhitda ishlatilgan maxfiy qiymatni qayta ishlatmang.

Marshrutlashni o‘zingiz boshqaradigan OSRM manzili tayyor bo‘lmasa
yoqmang (`ROUTING_EXTERNAL_ENABLED=False`). Ommaviy OSRM xizmatiga
koordinatlar yuborilishi mumkinligini yodda tuting.

## 5. Ishlab chiqarish tekshiruvi, migratsiya va veb fayllar

Yangilanish yoki birinchi migratsiyadan avval, ilova ishga tushganidan keyin
ushbu qo‘llanmadagi zaxira tartibini bajaring. Bo‘sh yangi bazada dastlabki
zaxira migratsiyadan oldin ham olinadi. Muhit faylini xizmatlar kabi yuklaydigan
vaqtinchalik `systemd` vazifasi orqali zaxirani ishga tushiring:

```sh
sudo systemd-run --wait --pipe --collect --property=User=distribyutsiya --property=WorkingDirectory=/srv/distribyutsiya --property=EnvironmentFile=/etc/distribyutsiya/production.env /bin/bash /srv/distribyutsiya/deploy/backup-postgres.sh
```

Zaxira yaratilmaguncha migratsiya buyrug‘iga o‘tmang. Quyidagi buyruqlar
tekshiruv va migratsiyani ilova foydalanuvchisi nomidan bajaradi:

```sh
sudo systemd-run --wait --pipe --collect --property=User=distribyutsiya --property=WorkingDirectory=/srv/distribyutsiya/backend --property=EnvironmentFile=/etc/distribyutsiya/production.env /srv/distribyutsiya/venv/bin/python manage.py check --deploy
```

Ishlab chiqarish muhiti xavfsizlik tekshiruvini bajaradi. Ogohlantirish chiqsa,
ularni ko‘rib chiqing va hal etilgandan keyingina davom eting.

```sh
sudo systemd-run --wait --pipe --collect --property=User=distribyutsiya --property=WorkingDirectory=/srv/distribyutsiya/backend --property=EnvironmentFile=/etc/distribyutsiya/production.env /srv/distribyutsiya/venv/bin/python manage.py migrate --noinput
```

Baza sxemasini yangilaydi. Buyruqni faqat `check --deploy` va zaxira
muvaffaqiyatli bo‘lgandan keyin bajaring.

```sh
sudo systemd-run --wait --pipe --collect --property=User=distribyutsiya --property=WorkingDirectory=/srv/distribyutsiya/backend --property=EnvironmentFile=/etc/distribyutsiya/production.env /srv/distribyutsiya/venv/bin/python manage.py collectstatic --noinput
```

Statik veb fayllarni Nginx xizmat qiladigan papkaga yig‘adi.

Agar veb to‘plamini serverda yaratsangiz, Node.js LTS 22+ va npm bilan:

```sh
sudo -u distribyutsiya -H sh -c 'cd /srv/distribyutsiya/frontend && npm ci && npm run build'
```

`frontend/dist` ichida veb fayllar yaratiladi. API bir xil domen
orqali `/api` manzilida ishlaydi; alohida API domeni talab qilinmaydi.

## 6. Nginx, HTTPS va boshqaruv sahifasi

HTTP vaqtinchalik sozlamasini domen bilan nusxalang, `DOMAIN.TLD` ni o‘z
domeningizga almashtiring va Nginx uchun yoqing:

```sh
sudo install -d -m 0755 /var/lib/letsencrypt
sudo cp /srv/distribyutsiya/deploy/nginx/distribyutsiya-http-bootstrap.conf /etc/nginx/sites-available/distribyutsiya
sudoedit /etc/nginx/sites-available/distribyutsiya
sudo ln -s /etc/nginx/sites-available/distribyutsiya /etc/nginx/sites-enabled/distribyutsiya
sudo nginx -t
sudo systemctl reload nginx
```

DNS yozuvlari serverga qaraganidan keyin, sertifikat oling:

```sh
sudo certbot certonly --webroot --webroot-path /var/lib/letsencrypt --domain DOMAIN.TLD
```

Endi to‘liq `distribyutsiya.conf` namunasi bilan vaqtinchalik HTTP sozlamasini
almashtiring:

```sh
sudo cp /srv/distribyutsiya/deploy/nginx/distribyutsiya.conf /etc/nginx/sites-available/distribyutsiya
sudoedit /etc/nginx/sites-available/distribyutsiya
```

`DOMAIN.TLD` va `alias` satrlaridagi papkalar haqiqiy domen va o‘rnatilgan
papkalar bilan mosligini tekshiring. Ma’mur paneli uchun ruxsat ro‘yxati
namunasini nusxalang:

```sh
sudo cp /srv/distribyutsiya/deploy/nginx/admin-allowlist.conf.example /etc/nginx/snippets/distribyutsiya-admin-allowlist.conf
sudoedit /etc/nginx/snippets/distribyutsiya-admin-allowlist.conf
```

Namuna ichidagi manzillarni faqat boshqaruv sahifasiga kirishi kerak bo‘lgan
statik IP manzillar bilan almashtiring; kerak bo‘lmasa admin ro‘yxatiga
qo‘shmang. Ruxsat ro‘yxati o‘rnatilmasa, `/admin/` orqali ochilmaydi.

Nginx uchun sarlavha, so‘rov tezligi va maxfiy ma’lumotlarni yozmaydigan
jurnal namunalarini tegishli papkalarga o‘rnating:

```sh
sudo cp /srv/distribyutsiya/deploy/nginx/distribyutsiya-proxy-headers.conf /etc/nginx/snippets/distribyutsiya-proxy-headers.conf
sudo cp /srv/distribyutsiya/deploy/nginx/distribyutsiya-rate-limit.conf /etc/nginx/conf.d/
sudo cp /srv/distribyutsiya/deploy/nginx/distribyutsiya-safe-logging.conf /etc/nginx/conf.d/
```

So‘ng sozlamalarni tekshirib Nginx’ni qayta yuklang:

```sh
sudo nginx -t
sudo systemctl reload nginx
```

HTTPS majburiy; namuna HTTP so‘rovlarini HTTPS’ga yo‘naltiradi. PWA va
foydalanuvchi sessiyalari uchun HTTPS’ni o‘chirmang. `/api/docs/` va
`/api/schema/` faqat ishlab chiqish rejimida ochiladi; ishlab chiqarishda
`DEBUG=False` bo‘lgani uchun ular yopiq. Django admin manzili `/admin/`
bo‘lib qoladi, Nginx IP ro‘yxati esa unga tashqi kirishni cheklaydi.

## 7. Gunicorn va fon vazifalari

Namuna `systemd` fayllarini tizim xizmatlari papkasiga o‘rnating:

```sh
sudo cp /srv/distribyutsiya/deploy/systemd/*.service /etc/systemd/system/
sudo cp /srv/distribyutsiya/deploy/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
```

Gunicorn, SMS navbati, takroriy buyurtmalar, saqlash va tozalash vazifalarini
yoqing va ishga tushiring:

```sh
sudo systemctl enable --now distribyutsiya-web.service
sudo systemctl enable --now distribyutsiya-sms.service
sudo systemctl enable --now distribyutsiya-recurring.timer
sudo systemctl enable --now distribyutsiya-maintenance.timer
sudo systemctl enable --now distribyutsiya-backup.timer
```

Gunicorn Django ilovasini faqat mahalliy `127.0.0.1:8000` manzilida tinglaydi.
SMS ishchisi `process_sms_outbox --loop` buyrug‘ini uzluksiz yuritadi.
Takroriy buyurtma qoralamalari har kuni 01:15 da, akkaunt va kirish yozuvlarini
tozalash 02:15 da, zaxira 03:00 da ishlaydi. Vaqt serverning mahalliy vaqt
mintaqasiga bog‘liq; serverni UTC bilan sozlash tavsiya qilinadi.

Xizmatlar va taymerlar holatini tekshiring:

```sh
sudo systemctl --no-pager --full status distribyutsiya-web distribyutsiya-sms
sudo systemctl --no-pager list-timers 'distribyutsiya-*'
sudo journalctl -u distribyutsiya-web -u distribyutsiya-sms --since today --no-pager
```

`systemd` jurnallarini faqat vakolatli boshqaruvchilar ko‘rsin. Nginx namunaviy
jurnali so‘rov tanasini, parametrlarini yoki telefon raqamlarini yozmaydi.
Ilova jurnallarini ham tekshirib, parol, token, OTP yoki to‘liq telefon
raqamlari yozilmasligini tasdiqlang.

## 8. Birinchi boshqaruvchi va demo ma’lumotlar

Faqat ishlab chiqarish sozlamalari, HTTPS va baza tekshirilgandan so‘ng,
birinchi boshqaruvchi hisobini yarating:

```sh
sudo systemd-run --pty --wait --collect --property=User=distribyutsiya --property=WorkingDirectory=/srv/distribyutsiya/backend --property=EnvironmentFile=/etc/distribyutsiya/production.env /srv/distribyutsiya/venv/bin/python manage.py createsuperuser
```

Parolni interaktiv tarzda kiriting. `seed_demo` buyrug‘ini ishlab chiqarish
bazasida hech qachon bajarmang. Ishlab chiqarish foydalanuvchilarida demo
telefonlar, jumladan `+998900009901` va `+998900030001` yoki
`+998900030002`, mavjud emasligini alohida tekshiring.

## 9. Kunlik zaxira va tiklashni sinash

Zaxira buyrug‘i PostgreSQL maxsus formatidagi zaxira va `media` papkasini
`age` orqali shifrlaydi. U 30 kundan eski mahalliy fayllarni o‘chiradi; mahalliy
nusxa yagona zaxira bo‘lmasin. Shifrlangan fayllarni har kuni serverdan
tashqaridagi cheklangan, shifrlangan saqlash joyiga ko‘chiring va ko‘chganini
tekshiring.

Zaxira kalit juftligini serverdan tashqari, himoyalangan qurilmada yarating.
Maxfiy ochish kalitini shu qurilmada saqlang; faqat ochiq qabul qiluvchi
qiymatini serverdagi `BACKUP_AGE_RECIPIENT` ga yozing:

```sh
age-keygen -o /secure/location/age-identity.txt
age-keygen -y /secure/location/age-identity.txt
```

Ikkinchi buyruq chiqargan ochiq qiymatni `BACKUP_AGE_RECIPIENT` ga kiriting.
Maxfiy kalitni serverda saqlamang. Keyin eng yangi zaxira fayllarini
serverdan tashqari himoyalangan tiklash qurilmasiga ko‘chirib, tekshiruvni
o‘sha yerda bajaring:

```sh
sudo systemctl start distribyutsiya-backup.service
sudo systemctl --no-pager --full status distribyutsiya-backup.service
age --decrypt --identity /secure/location/age-identity.txt /path/to/DB_ZAXIRA_FAYLI.dump.age | pg_restore --list
age --decrypt --identity /secure/location/age-identity.txt /path/to/MEDIA_ZAXIRA_FAYLI.tar.gz.age | tar -tzf -
```

`DB_ZAXIRA_FAYLI` va `MEDIA_ZAXIRA_FAYLI` o‘rniga eng so‘nggi nomlarni
qo‘ying. Ushbu buyruqlarni serverdan alohida, ochish kaliti saqlanadigan
himoyalangan tiklash qurilmasida ishga tushiring. Faqat fayl borligi emas,
zaxirani ochish va tarkibini o‘qish ham muvaffaqiyatli bo‘lishi kerak.

Tiklashni ishlab chiqarish serveri yoki bazasida emas, alohida sinov
qurilmasida bajaring.
Quyidagi misolda bo‘sh `distribyutsiya_restore_test` bazasi va unga kirish
huquqi oldindan yaratilgan bo‘lishi kerak. Maxfiy ochish kalitini serverdan
alohida saqlang; tiklash sinovida uni faqat himoyalangan tiklash muhitiga vaqtincha
ulab ishlating:

```sh
sudo -u postgres createdb --owner=distribyutsiya distribyutsiya_restore_test
age --decrypt --identity /secure/location/age-identity.txt /path/to/DB_ZAXIRA_FAYLI.dump.age | sudo -u postgres pg_restore --no-owner --dbname=distribyutsiya_restore_test
mkdir -p /tmp/distribyutsiya-restore-test
age --decrypt --identity /secure/location/age-identity.txt /path/to/MEDIA_ZAXIRA_FAYLI.tar.gz.age | tar -xzf - -C /tmp/distribyutsiya-restore-test
```

Tiklangan bazaga ilova orqali ulanish, jadval va yozuvlarni o‘qish, media
fayllarni ochishni tekshiring. Media fayllarini `/tmp/distribyutsiya-restore-test`
ichidagi alohida sinov papkasiga
tiklang, ishlab chiqarish fayllari bilan almashtirmang. Tiklash sinovi natijasi, sanasi
va muammolarini qayd eting. Sinov ma’lumotlarini tekshirgach, faqat o‘sha
aniq sinov bazasi va papkasini olib tashlang.
