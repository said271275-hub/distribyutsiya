import { describe, expect, it } from 'vitest'
import {
  buildOrderQueryParams,
  formatCurrency,
  formatOrderDate,
  getSuggestionLoad,
  orderStatusLabels,
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

  it('summa va sanani o‘qishga qulay ko‘rinishda chiqaradi', () => {
    expect(formatCurrency('125000')).toContain('125')
    expect(formatCurrency(125000)).toContain('so‘m')
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
