import { z } from 'zod'

const decimalPattern = /^\d+(\.\d+)?$/
const optionalDecimal = (label: string, maxDecimalPlaces: number) => z.string()
  .refine((value) => (
    value.trim() === '' ||
    (decimalPattern.test(value.trim()) &&
      (value.trim().split('.')[1]?.length ?? 0) <= maxDecimalPlaces)
  ), `${label} sonini to‘g‘ri kiriting.`)
  .refine((value) => value.trim() === '' || Number(value) >= 0, `${label} manfiy bo‘lishi mumkin emas.`)

export const productFormSchema = z.object({
  name: z.string().trim().min(1, 'Mahsulot nomini kiriting.').max(200, 'Nom 200 belgidan oshmasin.'),
  unit: z.enum(['piece', 'box', 'block']),
  price: z.string()
    .refine((value) => decimalPattern.test(value.trim()), 'Narxni to‘g‘ri kiriting.')
    .refine((value) => (value.trim().split('.')[1]?.length ?? 0) <= 2, 'Narx ko‘pi bilan 2 kasr xonali bo‘lsin.')
    .refine((value) => Number(value) >= 0, 'Narx manfiy bo‘lishi mumkin emas.'),
  unit_weight: optionalDecimal('Og‘irlik', 3),
  unit_volume: optionalDecimal('Hajm', 3),
  is_active: z.boolean(),
})

export const shopPriceFormSchema = z.object({
  shop: z.string().min(1, 'Do‘konni tanlang.'),
  price: optionalDecimal('Do‘kon narxi', 2),
  discount_percent: z.string()
    .refine((value) => decimalPattern.test(value.trim()), 'Chegirma foizini kiriting.')
    .refine((value) => (value.trim().split('.')[1]?.length ?? 0) <= 2, 'Chegirma ko‘pi bilan 2 kasr xonali bo‘lsin.')
    .refine((value) => Number(value) >= 0 && Number(value) <= 100, 'Chegirma 0 dan 100 foizgacha bo‘lishi kerak.'),
})

export type ProductFormValues = {
  name: string
  unit: 'piece' | 'box' | 'block'
  price: string
  unit_weight: string
  unit_volume: string
  is_active: boolean
}

export type ProductPayload = {
  name: string
  unit: ProductFormValues['unit']
  price: string
  unit_weight: string | null
  unit_volume: string | null
  is_active: boolean
}

export type ShopPriceRow = {
  id: number
  shop: number
  product: number
  price: string | null
  discount_percent: string
}

export function buildProductFormData(values: ProductFormValues, image: File) {
  const payload = buildProductPayload(values)
  const formData = new FormData()
  Object.entries(payload).forEach(([key, value]) => {
    if (value !== null) formData.append(key, String(value))
  })
  formData.append('image', image)
  return formData
}

export function buildProductPayload(values: ProductFormValues): ProductPayload {
  return {
    name: values.name.trim(),
    unit: values.unit,
    price: values.price.trim(),
    unit_weight: values.unit_weight.trim() || null,
    unit_volume: values.unit_volume.trim() || null,
    is_active: values.is_active,
  }
}

export function findShopPrice(
  rows: ShopPriceRow[],
  productId: number,
  shopId: number,
) {
  return rows.find((row) => row.product === productId && row.shop === shopId)
}

export function effectiveShopPrice(basePrice: string, price: string | null) {
  return price === null ? basePrice : price
}
