import { describe, expect, it } from 'vitest'
import {
  buildShopPayload,
  filterShops,
  shopStatusLabel,
  type DispatcherShop,
} from './dispatcherShopUtils'

const shops: DispatcherShop[] = [
  {
    id: 1,
    name: 'Guliston oziq-ovqat',
    phone_primary: '+998900000001',
    phone_secondary: '+998900000011',
    address: 'Mustaqillik ko‘chasi 1',
    district: 'Guliston',
    latitude: '40.840000',
    longitude: '68.660000',
    status: 'active',
  },
  {
    id: 2,
    name: 'Yangiyer savdo',
    phone_primary: '+998900000002',
    phone_secondary: '',
    address: 'Markaziy ko‘cha',
    district: 'Yangiyer',
    latitude: '40.270000',
    longitude: '68.820000',
    status: 'inactive',
  },
  {
    id: 3,
    name: 'Arxivlangan do‘kon',
    phone_primary: '+998900000003',
    phone_secondary: '',
    address: 'Yangi ko‘cha',
    district: 'Guliston',
    latitude: '40.840000',
    longitude: '68.660000',
    status: 'archived',
  },
]

describe('dispetcher do‘kon yordamchi funksiyalari', () => {
  it('nom, telefon yoki manzil bo‘yicha qidiradi', () => {
    expect(filterShops(shops, { search: 'GULISTON', district: 'all', status: 'all' })).toEqual([shops[0], shops[2]])
    expect(filterShops(shops, { search: '900000011', district: 'all', status: 'all' })).toEqual([shops[0]])
    expect(filterShops(shops, { search: 'Markaziy', district: 'all', status: 'all' })).toEqual([shops[1]])
  })

  it('tuman va holat filtrlarini birga qo‘llaydi', () => {
    expect(filterShops(shops, { search: '', district: 'Yangiyer', status: 'inactive' })).toEqual([shops[1]])
    expect(filterShops(shops, { search: '', district: 'Guliston', status: 'inactive' })).toEqual([])
    expect(filterShops(shops, { search: '', district: 'all', status: 'archived' })).toEqual([shops[2]])
  })

  it('do‘kon ma’lumotlarini yangilash uchun API shaklida tayyorlaydi', () => {
    expect(buildShopPayload({
      name: '  Yangi nom ',
      phone_primary: ' +998900000003 ',
      phone_secondary: ' ',
      address: '  Yangi manzil ',
      district: ' Yangiyer ',
      latitude: '40.270000',
      longitude: '68.820000',
    })).toEqual({
      name: 'Yangi nom',
      phone_primary: '+998900000003',
      phone_secondary: '',
      address: 'Yangi manzil',
      district: 'Yangiyer',
      latitude: '40.270000',
      longitude: '68.820000',
    })
  })

  it('do‘kon holatini o‘zbekcha ko‘rsatadi', () => {
    expect(shopStatusLabel('active')).toBe('Faol')
    expect(shopStatusLabel('inactive')).toBe('Nofaol')
    expect(shopStatusLabel('archived')).toBe('Arxivlangan')
  })
})
