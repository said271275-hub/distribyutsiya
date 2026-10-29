import { describe, expect, it } from 'vitest'
import {
  buildProductPayload,
  buildProductFormData,
  effectiveShopPrice,
  findShopPrice,
  productFormSchema,
  shopPriceFormSchema,
  type ShopPriceRow,
} from './dispatcherCatalogUtils'

describe('dispetcher mahsulot va narx yordamchilari', () => {
  it('bo‘sh og‘irlik va hajmni API uchun null ga aylantiradi', () => {
    expect(buildProductPayload({
      name: '  Ichimlik  ',
      unit: 'box',
      price: '15000.00',
      unit_weight: '',
      unit_volume: '  ',
      is_active: true,
    })).toEqual({
      name: 'Ichimlik',
      unit: 'box',
      price: '15000.00',
      unit_weight: null,
      unit_volume: null,
      is_active: true,
    })
  })

  it('mahsulot rasmi va maydonlarini yuklash uchun shakl ma’lumotini tayyorlaydi', () => {
    const file = new File(['rasm'], 'mahsulot.png', { type: 'image/png' })
    const formData = buildProductFormData({
      name: 'Mahsulot',
      unit: 'box',
      price: '15000.00',
      unit_weight: '',
      unit_volume: '',
      is_active: true,
    }, file)

    expect(formData.get('name')).toBe('Mahsulot')
    expect(formData.get('unit')).toBe('box')
    expect(formData.get('is_active')).toBe('true')
    expect(formData.get('image')).toBe(file)
    expect(formData.has('unit_weight')).toBe(false)
  })

  it('narx yozuvi bo‘lmasa asosiy narxni, bo‘lsa do‘kon narxini tanlaydi', () => {
    expect(effectiveShopPrice('20000.00', null)).toBe('20000.00')
    expect(effectiveShopPrice('20000.00', '18500.00')).toBe('18500.00')
  })

  it('do‘kon narxini aynan mahsulot va do‘kon juftligi bo‘yicha topadi', () => {
    const rows: ShopPriceRow[] = [
      { id: 1, product: 4, shop: 8, price: '9000.00', discount_percent: '5.00' },
      { id: 2, product: 5, shop: 8, price: null, discount_percent: '0.00' },
    ]
    expect(findShopPrice(rows, 4, 8)).toEqual(rows[0])
    expect(findShopPrice(rows, 4, 9)).toBeUndefined()
    expect(findShopPrice(rows, 5, 8)).toEqual(rows[1])
  })

  it('mahsulot formasida o‘zbekcha xatolar va kasr aniqligini tekshiradi', () => {
    const valid = {
      name: 'Mahsulot',
      unit: 'box',
      price: '12500.50',
      unit_weight: '20.125',
      unit_volume: '',
      is_active: true,
    }
    expect(productFormSchema.safeParse(valid).success).toBe(true)
    expect(productFormSchema.safeParse({ ...valid, name: ' ' }).success).toBe(false)
    expect(productFormSchema.safeParse({ ...valid, unit_weight: '20.1234' }).success).toBe(false)
    expect(productFormSchema.safeParse({ ...valid, price: '-1' }).success).toBe(false)
  })

  it('do‘kon narxi ixtiyoriy, chegirma esa 0–100 oralig‘ida bo‘lishini tekshiradi', () => {
    const valid = { shop: '3', price: '', discount_percent: '15.50' }
    expect(shopPriceFormSchema.safeParse(valid).success).toBe(true)
    expect(shopPriceFormSchema.safeParse({ ...valid, shop: '' }).success).toBe(false)
    expect(shopPriceFormSchema.safeParse({ ...valid, discount_percent: '100.01' }).success).toBe(false)
  })
})
