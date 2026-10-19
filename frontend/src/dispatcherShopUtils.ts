export type DispatcherShopStatus = 'active' | 'inactive' | 'archived' | string

export type DispatcherShop = {
  id: number
  name: string
  phone_primary: string
  phone_secondary: string
  address: string
  district: string
  latitude: string
  longitude: string
  status: DispatcherShopStatus
}

export type ShopFilters = {
  search: string
  district: string
  status: 'all' | 'active' | 'inactive'
}

export type ShopFormValues = Pick<
  DispatcherShop,
  'name' | 'phone_primary' | 'phone_secondary' | 'address' | 'district' | 'latitude' | 'longitude'
>

export function filterShops(shops: DispatcherShop[], filters: ShopFilters) {
  const query = filters.search.trim().toLocaleLowerCase('uz-UZ')
  return shops.filter((shop) => {
    const matchesSearch = !query || [
      shop.name,
      shop.phone_primary,
      shop.phone_secondary,
      shop.address,
      shop.district,
    ].some((value) => value.toLocaleLowerCase('uz-UZ').includes(query))
    const matchesDistrict = filters.district === 'all' || shop.district === filters.district
    const matchesStatus = filters.status === 'all' || shop.status === filters.status
    return matchesSearch && matchesDistrict && matchesStatus
  })
}

export function shopStatusLabel(status: DispatcherShopStatus) {
  if (status === 'active') return 'Faol'
  if (status === 'inactive') return 'Nofaol'
  if (status === 'archived') return 'Arxivlangan'
  return status
}

export function buildShopPayload(values: ShopFormValues) {
  return {
    name: values.name.trim(),
    phone_primary: values.phone_primary.trim(),
    phone_secondary: values.phone_secondary.trim(),
    address: values.address.trim(),
    district: values.district.trim(),
    latitude: values.latitude.trim(),
    longitude: values.longitude.trim(),
  }
}
