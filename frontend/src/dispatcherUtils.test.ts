import { describe, expect, it } from 'vitest'
import {
  buildOrderQueryParams,
  canTransitionOrder,
  formatCurrency,
  formatOrderDate,
  getSuggestionLoad,
  orderStatusLabels,
  selectNewOrders,
  toggleOrderSelection,
} from './dispatcherUtils'

describe('dispetcher yordamchi funksiyalari', () => {
  it('buyurtma filtrlari va sahifa raqamini API parametrlariga aylantiradi', () => {
    expect(
      buildOrderQueryParams({
        date: '2026-10-17',
        status: 'confirmed',
        search: '  123  ',
        page: 2,
      }),
    ).toEqual({
      page: 2,
      date: '2026-10-17',
      status: 'confirmed',
      search: '123',
    })
  })

  it('ixtiyoriy filtrlar bo‘sh bo‘lsa ularni so‘rovga qo‘shmaydi', () => {
    expect(
      buildOrderQueryParams({
        date: '',
        status: 'all',
        search: ' ',
        page: 1,
      }),
    ).toEqual({ page: 1 })
  })

  it('buyurtma holatlarini o‘zbekcha ko‘rsatadi', () => {
    expect(orderStatusLabels).toEqual({
      new: 'Yangi',
      confirmed: 'Tasdiqlandi',
      loaded: 'Yuklandi',
      in_transit: 'Yo‘lda',
      delivered: 'Yetkazildi',
      cancelled: 'Bekor qilindi',
    })
  })

  it('buyurtma uchun faqat backend ruxsat bergan holat o‘tishlarini yoqadi', () => {
    expect(canTransitionOrder('new', 'confirmed')).toBe(true)
    expect(canTransitionOrder('new', 'cancelled')).toBe(true)
    expect(canTransitionOrder('confirmed', 'cancelled')).toBe(true)
    expect(canTransitionOrder('confirmed', 'loaded')).toBe(true)
    expect(canTransitionOrder('loaded', 'cancelled')).toBe(false)
    expect(canTransitionOrder('delivered', 'cancelled')).toBe(false)
    expect(canTransitionOrder('cancelled', 'confirmed')).toBe(false)
  })

  it('tanlovga faqat joriy sahifadagi yangi buyurtmalarni qo‘shadi yoki olib tashlaydi', () => {
    const orders = [
      { id: 1, status: 'new' as const },
      { id: 2, status: 'confirmed' as const },
      { id: 3, status: 'new' as const },
    ]
    expect(selectNewOrders([8], orders, true)).toEqual([8, 1, 3])
    expect(selectNewOrders([1, 3, 8], orders, false)).toEqual([8])
    expect(toggleOrderSelection([1, 3], 3)).toEqual([1])
    expect(toggleOrderSelection([1], 3)).toEqual([1, 3])
  })

  it('summa va sanani o‘qishga qulay ko‘rinishda chiqaradi', () => {
    expect(formatCurrency('125000')).toBe('125 000,00 so‘m')
    expect(formatCurrency(125000)).toBe('125 000,00 so‘m')
    expect(formatOrderDate('2026-10-17')).toBe('17-oktabr 2026-yil')
  })

  it('guruhlash taklifidagi tanlangan to‘xtashlarning yukini hisoblaydi', () => {
    expect(
      getSuggestionLoad([
        { capacity_load: '10.000', capacity_metric: 'weight' },
        { capacity_load: '5.000', capacity_metric: 'weight' },
      ]),
    ).toEqual({ metric: 'weight', load: 15 })
  })

  it('aralash yoki o‘lchovi noma’lum yukni taxmin qilmaydi', () => {
    expect(
      getSuggestionLoad([
        { capacity_load: '10.000', capacity_metric: 'weight' },
        { capacity_load: null, capacity_metric: 'unknown' },
      ]),
    ).toEqual({ metric: 'unknown', load: null })
  })
})
