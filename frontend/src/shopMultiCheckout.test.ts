import { describe, it, expect } from 'vitest'

export interface MockCatalogProduct {
  id: number
  company_id: number
  company_name: string
  company_cutoff_time: string
  name: string
  unit_price: string
}

export interface MockCartLine {
  product: MockCatalogProduct
  quantity: number
}

export interface CompanyCartGroup {
  company_id: number
  company_name: string
  company_cutoff_time: string
  items: MockCartLine[]
  subtotal: number
}

export function groupCartByCompany(cart: MockCartLine[]): CompanyCartGroup[] {
  const map = new Map<number, CompanyCartGroup>()
  for (const line of cart) {
    const compId = line.product.company_id
    if (!map.has(compId)) {
      map.set(compId, {
        company_id: compId,
        company_name: line.product.company_name,
        company_cutoff_time: line.product.company_cutoff_time,
        items: [],
        subtotal: 0,
      })
    }
    const group = map.get(compId)!
    group.items.push(line)
    group.subtotal += Math.round(Number(line.product.unit_price) * 100) * line.quantity / 100
  }
  return Array.from(map.values())
}

export function calculateGrandTotal(groups: CompanyCartGroup[]): number {
  return groups.reduce((acc, g) => acc + g.subtotal, 0)
}

export function buildCheckoutPayload(
  groups: CompanyCartGroup[],
  deliveries: Record<number, { date: string; from?: string; to?: string; note?: string }>
) {
  return {
    orders: groups.map((g) => {
      const cfg = deliveries[g.company_id] || { date: '2026-11-20' }
      return {
        company_id: g.company_id,
        delivery_date: cfg.date,
        delivery_time_from: cfg.from || null,
        delivery_time_to: cfg.to || null,
        note: cfg.note || '',
        items: g.items.map((item) => ({
          product_id: item.product.id,
          quantity: item.quantity,
        })),
      }
    }),
  }
}

describe('E-BO‘LAK: Multi-Company Cart & Checkout Helper Tests', () => {
  const sampleCart: MockCartLine[] = [
    {
      product: {
        id: 1,
        company_id: 10,
        company_name: 'Coca Cola OOO',
        company_cutoff_time: '18:00:00',
        name: 'Coca Cola 1.5L',
        unit_price: '12000.00',
      },
      quantity: 5,
    },
    {
      product: {
        id: 2,
        company_id: 10,
        company_name: 'Coca Cola OOO',
        company_cutoff_time: '18:00:00',
        name: 'Fanta 1.5L',
        unit_price: '11500.00',
      },
      quantity: 2,
    },
    {
      product: {
        id: 3,
        company_id: 20,
        company_name: 'Nestle Distribution',
        company_cutoff_time: '17:00:00',
        name: 'Nestle Pure Life 5L',
        unit_price: '9000.00',
      },
      quantity: 10,
    },
  ]

  it('groups cart lines by company correctly', () => {
    const groups = groupCartByCompany(sampleCart)
    expect(groups).toHaveLength(2)

    const colaGroup = groups.find((g) => g.company_id === 10)
    expect(colaGroup).toBeDefined()
    expect(colaGroup?.company_name).toBe('Coca Cola OOO')
    expect(colaGroup?.items).toHaveLength(2)
    // 5 * 12000 + 2 * 11500 = 60000 + 23000 = 83000
    expect(colaGroup?.subtotal).toBe(83000)

    const nestleGroup = groups.find((g) => g.company_id === 20)
    expect(nestleGroup).toBeDefined()
    expect(nestleGroup?.company_name).toBe('Nestle Distribution')
    expect(nestleGroup?.items).toHaveLength(1)
    // 10 * 9000 = 90000
    expect(nestleGroup?.subtotal).toBe(90000)
  })

  it('calculates grand total accurately across all companies', () => {
    const groups = groupCartByCompany(sampleCart)
    const grandTotal = calculateGrandTotal(groups)
    // 83000 + 90000 = 173000
    expect(grandTotal).toBe(173000)
  })

  it('generates multi-company checkout payload with individual delivery configs', () => {
    const groups = groupCartByCompany(sampleCart)
    const deliveries = {
      10: { date: '2026-11-20', from: '09:00', to: '12:00', note: 'Eshik oldiga' },
      20: { date: '2026-11-21', note: 'Qo‘ng‘iroq qiling' },
    }
    const payload = buildCheckoutPayload(groups, deliveries)

    expect(payload.orders).toHaveLength(2)
    const order1 = payload.orders.find((o) => o.company_id === 10)
    expect(order1?.delivery_date).toBe('2026-11-20')
    expect(order1?.delivery_time_from).toBe('09:00')
    expect(order1?.delivery_time_to).toBe('12:00')
    expect(order1?.note).toBe('Eshik oldiga')
    expect(order1?.items).toEqual([
      { product_id: 1, quantity: 5 },
      { product_id: 2, quantity: 2 },
    ])

    const order2 = payload.orders.find((o) => o.company_id === 20)
    expect(order2?.delivery_date).toBe('2026-11-21')
    expect(order2?.delivery_time_from).toBeNull()
    expect(order2?.delivery_time_to).toBeNull()
    expect(order2?.note).toBe('Qo‘ng‘iroq qiling')
    expect(order2?.items).toEqual([
      { product_id: 3, quantity: 10 },
    ])
  })
})
