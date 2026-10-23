import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Archive, Check, LoaderCircle, Pencil, Plus, Save, Store, Tags, X } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import api, { apiErrorMessage } from './api'
import {
  buildProductPayload,
  effectiveShopPrice,
  findShopPrice,
  productFormSchema,
  shopPriceFormSchema,
  type ProductFormValues,
  type ProductPayload,
  type ShopPriceRow,
} from './dispatcherCatalogUtils'
import './DispatcherCatalog.css'

type Product = ProductPayload & {
  id: number
  is_archived: boolean
  created_at: string
  updated_at: string
}
type Shop = { id: number; name: string; district: string; status: string }
type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] }
type ProductRequest = { id?: number; values: ProductFormValues }
type ShopPriceFormValues = { shop: string; price: string; discount_percent: string }

const units = [
  { value: 'piece', label: 'dona' },
  { value: 'box', label: 'quti' },
  { value: 'block', label: 'blok' },
] as const

const emptyProduct: ProductFormValues = {
  name: '',
  unit: 'box',
  price: '',
  unit_weight: '',
  unit_volume: '',
  is_active: true,
}

function formatAmount(value: string | null) {
  return value === null ? 'Asosiy narx' : `${new Intl.NumberFormat('uz-UZ', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value))} so‘m`
}

export default function DispatcherCatalogPage() {
  const queryClient = useQueryClient()
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null)
  const [editingProduct, setEditingProduct] = useState<Product | null>(null)
  const [showProductForm, setShowProductForm] = useState(false)
  const [pageError, setPageError] = useState('')
  const productForm = useForm<ProductFormValues>({
    resolver: zodResolver(productFormSchema),
    defaultValues: emptyProduct,
  })
  const products = useQuery({
    queryKey: ['dispatcher-products'],
    queryFn: async () => (
      await api.get<Page<Product>>('/v1/admin/products/', { params: { page_size: 100 } })
    ).data,
  })
  const productRows = products.data?.results ?? []
  const selectedProduct = productRows.find((product) => product.id === selectedProductId) ??
    productRows[0] ?? null

  const productMutation = useMutation({
    mutationFn: async ({ id, values }: ProductRequest) => {
      const payload = buildProductPayload(values)
      const response = id
        ? await api.patch<Product>(`/v1/admin/products/${id}/`, payload)
        : await api.post<Product>('/v1/admin/products/', payload)
      return response.data
    },
    onSuccess: async (product) => {
      setPageError('')
      setSelectedProductId(product.id)
      setShowProductForm(false)
      setEditingProduct(null)
      productForm.reset(emptyProduct)
      await queryClient.invalidateQueries({ queryKey: ['dispatcher-products'] })
    },
    onError: (error) => setPageError(apiErrorMessage(error, 'Mahsulotni saqlab bo‘lmadi. Qayta urinib ko‘ring.')),
  })

  const archiveProduct = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/v1/admin/products/${id}/`)
      return id
    },
    onSuccess: async (id) => {
      setPageError('')
      if (selectedProductId === id) setSelectedProductId(null)
      await queryClient.invalidateQueries({ queryKey: ['dispatcher-products'] })
    },
    onError: (error) => setPageError(apiErrorMessage(error, 'Mahsulotni arxivlab bo‘lmadi. Qayta urinib ko‘ring.')),
  })

  const openCreateForm = () => {
    setEditingProduct(null)
    productForm.reset(emptyProduct)
    setPageError('')
    setShowProductForm(true)
  }
  const openEditForm = (product: Product) => {
    setEditingProduct(product)
    productForm.reset({
      name: product.name,
      unit: product.unit,
      price: product.price,
      unit_weight: product.unit_weight ?? '',
      unit_volume: product.unit_volume ?? '',
      is_active: product.is_active,
    })
    setPageError('')
    setShowProductForm(true)
  }
  const submitProduct = productForm.handleSubmit((values) => {
    setPageError('')
    productMutation.mutate({ id: editingProduct?.id, values })
  })
  const confirmArchive = (product: Product) => {
    if (!window.confirm(`“${product.name}” mahsuloti arxivlansinmi? U butunlay o‘chirilmaydi.`)) return
    setPageError('')
    archiveProduct.mutate(product.id)
  }

  return (
    <section className="dispatcher-catalog-page">
      <div className="dispatcher-page-heading dispatcher-catalog-heading">
        <div>
          <span className="dispatcher-eyebrow">KATALOG BOSHQARUVI</span>
          <h1>Mahsulotlar va narxlar</h1>
          <p>Mahsulot katalogini yangilang va do‘konlarga alohida narx yoki chegirma belgilang.</p>
        </div>
        <button type="button" className="dispatcher-primary-button" onClick={openCreateForm}>
          <Plus size={16} /> Mahsulot qo‘shish
        </button>
      </div>

      {pageError && <div className="dispatcher-catalog-error" role="alert">{pageError}</div>}
      <section className="dispatcher-card dispatcher-catalog-products">
        <div className="dispatcher-section-heading">
          <div><span className="dispatcher-eyebrow">KOMPANIYA KATALOGI</span><h2>Mahsulotlar</h2></div>
          <span className="dispatcher-catalog-count">{products.data?.count ?? 0} ta</span>
        </div>
        {products.isLoading ? (
          <div className="dispatcher-loading" role="status"><span /> Mahsulotlar yuklanmoqda…</div>
        ) : products.isError ? (
          <div className="dispatcher-error-state" role="alert">
            <p>{apiErrorMessage(products.error, 'Mahsulotlarni yuklab bo‘lmadi.')}</p>
            <button type="button" onClick={() => void products.refetch()}>Qayta urinish</button>
          </div>
        ) : productRows.length ? (
          <div className="dispatcher-table-scroll">
            <table className="dispatcher-orders-table dispatcher-catalog-table">
              <thead>
                <tr><th>Mahsulot</th><th>Birlik</th><th>Asosiy narx</th><th>Og‘irlik</th><th>Hajm</th><th>Holat</th><th>Amallar</th></tr>
              </thead>
              <tbody>
                {productRows.map((product) => (
                  <tr
                    key={product.id}
                    className={selectedProduct?.id === product.id ? 'dispatcher-catalog-selected' : ''}
                    onClick={() => setSelectedProductId(product.id)}
                  >
                    <td><strong>{product.name}</strong></td>
                    <td>{units.find((unit) => unit.value === product.unit)?.label ?? product.unit}</td>
                    <td>{formatAmount(product.price)}</td>
                    <td>{product.unit_weight === null ? '—' : `${product.unit_weight} kg`}</td>
                    <td>{product.unit_volume === null ? '—' : `${product.unit_volume} m³`}</td>
                    <td>
                      <span className={`dispatcher-status ${product.is_archived ? 'dispatcher-status-cancelled' : product.is_active ? 'dispatcher-status-confirmed' : 'dispatcher-status-new'}`}>
                        {product.is_archived ? 'Arxivlangan' : product.is_active ? 'Faol' : 'Nofaol'}
                      </span>
                    </td>
                    <td>
                      <div className="dispatcher-catalog-row-actions" onClick={(event) => event.stopPropagation()}>
                        <button type="button" className="dispatcher-order-action" onClick={() => openEditForm(product)}>
                          <Pencil size={13} /> Tahrirlash
                        </button>
                        {!product.is_archived && (
                          <button
                            type="button"
                            className="dispatcher-order-action dispatcher-order-cancel"
                            disabled={archiveProduct.isPending}
                            onClick={() => confirmArchive(product)}
                          >
                            <Archive size={13} /> Arxivlash
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="dispatcher-empty"><Tags size={22} /><strong>Mahsulotlar yo‘q</strong><span>Katalogga birinchi mahsulotni qo‘shing.</span></div>
        )}
      </section>

      {selectedProduct && (
        <ShopPricingEditor
          key={selectedProduct.id}
          product={selectedProduct}
        />
      )}

      {showProductForm && (
        <div className="dispatcher-dialog-backdrop" onMouseDown={(event) => {
          if (event.target === event.currentTarget && !productMutation.isPending) setShowProductForm(false)
        }}>
          <form
            className="dispatcher-confirm-dialog dispatcher-product-form"
            role="dialog"
            aria-modal="true"
            aria-labelledby="dispatcher-product-form-title"
            onSubmit={(event) => void submitProduct(event)}
          >
            <div className="dispatcher-product-form-heading">
              <h2 id="dispatcher-product-form-title">{editingProduct ? 'Mahsulotni tahrirlash' : 'Mahsulot qo‘shish'}</h2>
              <button type="button" aria-label="Oynani yopish" disabled={productMutation.isPending} onClick={() => setShowProductForm(false)}>
                <X size={17} />
              </button>
            </div>
            <label>
              <span>Mahsulot nomi</span>
              <input {...productForm.register('name')} maxLength={200} />
              {productForm.formState.errors.name && <small role="alert">{productForm.formState.errors.name.message}</small>}
            </label>
            <div className="dispatcher-product-form-grid">
              <label>
                <span>O‘lchov birligi</span>
                <select {...productForm.register('unit')}>
                  {units.map((unit) => <option key={unit.value} value={unit.value}>{unit.label}</option>)}
                </select>
              </label>
              <label>
                <span>Asosiy narx (so‘m)</span>
                <input {...productForm.register('price')} type="number" min="0" step="0.01" />
                {productForm.formState.errors.price && <small role="alert">{productForm.formState.errors.price.message}</small>}
              </label>
              <label>
                <span>Birlik og‘irligi (kg)</span>
                <input {...productForm.register('unit_weight')} type="number" min="0" step="0.001" />
                {productForm.formState.errors.unit_weight && <small role="alert">{productForm.formState.errors.unit_weight.message}</small>}
              </label>
              <label>
                <span>Birlik hajmi (m³)</span>
                <input {...productForm.register('unit_volume')} type="number" min="0" step="0.001" />
                {productForm.formState.errors.unit_volume && <small role="alert">{productForm.formState.errors.unit_volume.message}</small>}
              </label>
            </div>
            <label className="dispatcher-product-active">
              <input {...productForm.register('is_active')} type="checkbox" />
              <span>Mahsulot faol</span>
            </label>
            {productMutation.isError && (
              <p className="dispatcher-catalog-form-error" role="alert">
                {apiErrorMessage(productMutation.error, 'Mahsulotni saqlab bo‘lmadi.')}
              </p>
            )}
            <div className="dispatcher-dialog-actions">
              <button type="button" className="dispatcher-order-action" disabled={productMutation.isPending} onClick={() => setShowProductForm(false)}>
                Bekor qilish
              </button>
              <button type="submit" className="dispatcher-primary-button" disabled={productMutation.isPending}>
                {productMutation.isPending ? <LoaderCircle className="dispatcher-spinning" size={15} /> : <Save size={15} />}
                Saqlash
              </button>
            </div>
          </form>
        </div>
      )}
    </section>
  )
}

function ShopPricingEditor({
  product,
}: {
  product: Product
}) {
  const queryClient = useQueryClient()
  const form = useForm<ShopPriceFormValues>({
    resolver: zodResolver(shopPriceFormSchema),
    defaultValues: { shop: '', price: '', discount_percent: '0' },
  })
  const shops = useQuery({
    queryKey: ['dispatcher-catalog-shops'],
    queryFn: async () => (
      await api.get<Page<Shop>>('/v1/admin/shops/', { params: { page_size: 100 } })
    ).data,
  })
  const prices = useQuery({
    queryKey: ['dispatcher-shop-prices', product.id],
    queryFn: async () => (
      await api.get<Page<ShopPriceRow>>('/v1/admin/shop-prices/', {
        params: { page_size: 100 },
      })
    ).data,
  })
  const selectedShopId = Number(form.watch('shop')) || null
  const currentPrice = selectedShopId && prices.data
    ? findShopPrice(prices.data.results, product.id, selectedShopId)
    : undefined

  const savePrice = useMutation({
    mutationFn: async (values: ShopPriceFormValues) => {
      const payload = {
        shop: Number(values.shop),
        product: product.id,
        price: values.price.trim() || null,
        discount_percent: values.discount_percent.trim(),
      }
      const response = currentPrice
        ? await api.patch<ShopPriceRow>(`/v1/admin/shop-prices/${currentPrice.id}/`, payload)
        : await api.post<ShopPriceRow>('/v1/admin/shop-prices/', payload)
      return response.data
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['dispatcher-shop-prices'] })
    },
  })

  const selectShop = (shopId: string) => {
    savePrice.reset()
    form.setValue('shop', shopId, { shouldValidate: true })
    const override = shopId && prices.data
      ? findShopPrice(prices.data.results, product.id, Number(shopId))
      : undefined
    form.setValue('price', override?.price ?? '')
    form.setValue('discount_percent', override?.discount_percent ?? '0')
  }

  return (
    <section className="dispatcher-card dispatcher-shop-pricing">
      <div className="dispatcher-section-heading">
        <div><span className="dispatcher-eyebrow">DO‘KON NARXI VA CHEGIRMASI</span><h2>{product.name}</h2></div>
        <Store size={19} />
      </div>
      {product.is_archived || !product.is_active ? (
        <div className="dispatcher-catalog-notice">Arxivlangan yoki nofaol mahsulotga do‘kon narxi belgilab bo‘lmaydi.</div>
      ) : (
        <form className="dispatcher-shop-price-form" onSubmit={form.handleSubmit((values) => {
          savePrice.reset()
          savePrice.mutate(values)
        })}>
          <label>
            <span>Do‘kon</span>
            <select
              {...form.register('shop')}
              onChange={(event) => selectShop(event.target.value)}
              disabled={shops.isLoading || prices.isLoading || !shops.data?.results.length}
            >
              <option value="">Do‘konni tanlang</option>
              {(shops.data?.results ?? []).map((shop) => (
                <option key={shop.id} value={shop.id}>{shop.name} · {shop.district}</option>
              ))}
            </select>
            {form.formState.errors.shop && <small role="alert">{form.formState.errors.shop.message}</small>}
          </label>
          <label>
            <span>Maxsus narx (so‘m, ixtiyoriy)</span>
            <input {...form.register('price')} type="number" min="0" step="0.01" placeholder={product.price} />
            {form.formState.errors.price && <small role="alert">{form.formState.errors.price.message}</small>}
          </label>
          <label>
            <span>Chegirma (%)</span>
            <input {...form.register('discount_percent')} type="number" min="0" max="100" step="0.01" />
            {form.formState.errors.discount_percent && <small role="alert">{form.formState.errors.discount_percent.message}</small>}
          </label>
          <button type="submit" className="dispatcher-primary-button" disabled={!selectedShopId || savePrice.isPending || shops.isLoading || prices.isLoading || prices.isError}>
            {savePrice.isPending ? <LoaderCircle className="dispatcher-spinning" size={15} /> : currentPrice ? <Save size={15} /> : <Check size={15} />}
            {currentPrice ? 'Narxni yangilash' : 'Narxni belgilash'}
          </button>
        </form>
      )}
      {savePrice.isError && <p className="dispatcher-catalog-form-error" role="alert">{apiErrorMessage(savePrice.error, 'Do‘kon narxini saqlab bo‘lmadi.')}</p>}
      {shops.isError && (
        <div className="dispatcher-catalog-query-error" role="alert">
          <span>{apiErrorMessage(shops.error, 'Do‘konlarni yuklab bo‘lmadi.')}</span>
          <button type="button" onClick={() => void shops.refetch()}>Qayta urinish</button>
        </div>
      )}
      {shops.data && shops.data.results.length === 0 && (
        <p className="dispatcher-catalog-notice">Narx belgilash uchun kompaniyaga ulangan faol do‘konlar topilmadi.</p>
      )}
      {prices.isError && (
        <div className="dispatcher-catalog-query-error" role="alert">
          <span>{apiErrorMessage(prices.error, 'Do‘kon narxlarini yuklab bo‘lmadi.')}</span>
          <button type="button" onClick={() => void prices.refetch()}>Qayta urinish</button>
        </div>
      )}
      {prices.isLoading ? (
        <div className="dispatcher-loading" role="status"><span /> Narxlar yuklanmoqda…</div>
      ) : prices.data ? (
        <div className="dispatcher-shop-price-list">
          <h3>Belgilangan narxlar</h3>
          {prices.data.results.filter((row) => row.product === product.id).length ? (
            <div className="dispatcher-table-scroll">
              <table className="dispatcher-orders-table">
                <thead><tr><th>Do‘kon</th><th>Asosiy narx</th><th>Do‘kon narxi</th><th>Chegirma</th></tr></thead>
                <tbody>
                  {prices.data.results.filter((row) => row.product === product.id).map((row) => {
                    const shop = shops.data?.results.find((item) => item.id === row.shop)
                    return (
                      <tr key={row.id}>
                        <td>{shop?.name ?? `Do‘kon #${row.shop}`}</td>
                        <td>{formatAmount(product.price)}</td>
                        <td>{formatAmount(row.price)}</td>
                        <td>{row.discount_percent}%</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="dispatcher-catalog-notice">Hozircha do‘konlarga alohida narx yoki chegirma belgilanmagan.</p>
          )}
          {selectedShopId && currentPrice && (
            <p className="dispatcher-effective-price">
              Chegirmadan oldingi narx: {formatAmount(effectiveShopPrice(product.price, currentPrice.price))}; chegirma {currentPrice.discount_percent}%.
            </p>
          )}
        </div>
      ) : null}
    </section>
  )
}
