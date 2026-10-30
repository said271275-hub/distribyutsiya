import { resolveMessage, type Language, type TranslationKey } from './catalog'

const serverErrorKeys: Record<string, TranslationKey> = {
  'Kirish muddati tugagan.': 'server.expiredSession',
  'Akkaunt faol emas.': 'server.inactiveAccount',
  'Akkauntni o‘chirish faqat do‘konchi uchun.': 'server.shopOnlyDeletion',
  'Telefon raqamini +998 XX XXX XX XX formatida kiriting.': 'server.invalidPhoneFormat',
  'Bu telefon raqami allaqachon ro‘yxatdan o‘tgan.': 'server.phoneAlreadyRegistered',
  'SMS kod yuborish limiti tugadi. Birozdan keyin urinib ko‘ring.': 'server.otpRateLimit',
  'SMS kod yuborilmadi. Keyinroq qayta urinib ko‘ring.': 'server.otpSendFailed',
  'Telefon yoki parol noto‘g‘ri.': 'server.invalidCredentials',
  'Telefon raqami yoki parol noto‘g‘ri.': 'server.invalidCredentials',
  'Akkauntni tiklash muddati tugagan.': 'server.restoreExpired',
  'SMS kodi noto‘g‘ri yoki muddati tugagan.': 'server.invalidOtp',
  'Kirish vaqtincha bloklangan. Keyinroq qayta urinib ko‘ring.': 'server.loginBlocked',
  '5 ta noto‘g‘ri urinishdan so‘ng kirish 15 daqiqaga bloklandi.': 'server.loginBlockedAfterAttempts',
  'Parol noto‘g‘ri.': 'server.invalidPassword',
  'Boshqa sababni yozing.': 'server.otherReasonRequired',
  'Ochiq buyurtmalar bor. Avval ularni yakunlang yoki bekor qiling.': 'server.openOrders',
  'To‘lanmagan qarz bor. Avval qarzni to‘liq yoping.': 'server.unpaidDebt',
  'Akkauntni o‘chirish so‘rovi allaqachon yuborilgan.': 'server.deletionAlreadyRequested',
  'Birinchi kirishda parolni o‘zgartiring.': 'server.passwordChangeRequired',
  'Yangi telefon raqami hozirgi raqamdan farq qilishi kerak.': 'server.phoneMustDiffer',
  'Joriy parol noto‘g‘ri.': 'server.currentPasswordInvalid',
  'Parollar bir-biriga mos kelmadi.': 'error.passwordMismatch',
  'Parol kamida 8 ta belgidan iborat bo‘lsin.': 'error.passwordTooShort',
  'Bu parol juda oddiy. Boshqa parol tanlang.': 'error.passwordCommon',
  'Parol faqat raqamlardan iborat bo‘lmasin.': 'error.passwordNumeric',
  'Parol shaxsiy ma’lumotlarga juda o‘xshash.': 'error.passwordSimilar',
  'Parol talablariga mos kelmadi.': 'error.passwordGeneric',
}

export function translateServerError(message: string, language: Language) {
  const key = serverErrorKeys[message]
  return key ? resolveMessage(key, language) : undefined
}
