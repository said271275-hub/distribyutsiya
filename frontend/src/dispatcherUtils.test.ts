import { describe, expect, it } from 'vitest'
import {
  buildOrderQueryParams,
  formatCurrency,
  formatOrderDate,
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
    expect(formatOrderDate('2026-10-17')).toContain('2026')
  })
})
