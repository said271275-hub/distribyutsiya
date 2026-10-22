import { describe, expect, it } from 'vitest'
import {
  filterFinanceBalances,
  financeEntryLabel,
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

  it('labels order debt, payment and correction ledger entries', () => {
    const entry = (order_id: number | null, payment_id: number | null): FinanceEntry => ({
      id: 1,
      amount: '1000.00',
      direction: 'debit',
      order_id,
      payment_id,
      note: '',
      posted_at: null,
      created_at: '2026-10-01T00:00:00+05:00',
    })
    expect(financeEntryLabel(entry(3, null))).toBe('Buyurtma qarzi')
    expect(financeEntryLabel(entry(null, 4))).toBe('To‘lov')
    expect(financeEntryLabel(entry(null, null))).toBe('Tuzatish')
  })

  it('formats amounts in so‘m', () => {
    expect(formatFinanceMoney('125000')).toContain('so‘m')
  })
})
