import { describe, expect, it } from 'vitest'
import {
  filterFinanceBalances,
  financeEntryLabel,
  formatFinanceBalance,
  formatFinanceDate,
  formatFinanceMoney,
  type FinanceBalance,
  type FinanceEntry,
} from './dispatcherFinanceUtils'

const balances: FinanceBalance[] = [
  {
    id: 1,
    shop_id: 1,
    shop_name: 'Guliston do‘koni',
    current_balance: '125000.00',
    container_deposit: '50000.00',
    last_payment_at: null,
    entries: [],
  },
  {
    id: 2,
    shop_id: 2,
    shop_name: 'Yangiyer market',
    current_balance: '-10000.00',
    container_deposit: '0.00',
    last_payment_at: null,
    entries: [],
  },
]

describe('dispatcher finance utilities', () => {
  it('filters by shop name and outstanding debt', () => {
    expect(filterFinanceBalances(balances, ' guliston ', false)).toEqual([balances[0]])
    expect(filterFinanceBalances(balances, '', true)).toEqual([balances[0]])
    expect(filterFinanceBalances(balances, 'market', true)).toEqual([])
  })

  it('labels debt increases and decreases by their balance direction', () => {
    const entry = (
      direction: FinanceEntry['direction'],
      order_id: number | null,
      payment_id: number | null,
    ): FinanceEntry => ({
      id: 1,
      amount: '1000.00',
      direction,
      order_id,
      payment_id,
      note: '',
      posted_at: null,
      created_at: '2026-10-01T00:00:00+05:00',
    })
    expect(financeEntryLabel(entry('debit', 3, null))).toBe('Qarz qo‘shildi')
    expect(financeEntryLabel(entry('credit', null, 4))).toBe('Qarz kamaydi')
    expect(financeEntryLabel(entry('credit', 3, null))).toBe('Qarz kamaydi')
    expect(financeEntryLabel(entry('debit', null, null))).toBe('Qarz qo‘shildi')
  })

  it('formats amounts in so‘m', () => {
    expect(formatFinanceMoney('125000')).toBe('125 000,00 so‘m')
  })

  it('describes positive, negative and zero balances with positive amounts', () => {
    expect(formatFinanceBalance('26780692')).toBe('Do‘kon qarzdor: 26 780 692,00 so‘m')
    expect(formatFinanceBalance('-26780692')).toBe('Oldindan to‘langan: 26 780 692,00 so‘m')
    expect(formatFinanceBalance('0')).toBe('Qarz yo‘q')
  })

  it('formats dates as day.month.year', () => {
    expect(formatFinanceDate('2026-10-27')).toBe('27.10.2026')
    expect(formatFinanceDate(null)).toBe('Kiritilmagan')
  })
})
