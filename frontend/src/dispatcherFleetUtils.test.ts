import { describe, expect, it } from 'vitest'
import {
  buildDriverPayload,
  buildVehiclePayload,
  driverCreateSchema,
  filterDrivers,
  filterVehicles,
  vehicleFormSchema,
  type FleetDriver,
  type FleetVehicle,
} from './dispatcherFleetUtils'

const vehicles: FleetVehicle[] = [
  {
    id: 1,
    name: 'Katta yuk mashinasi',
    plate_number: '01A123AA',
    capacity: '1500.00',
    volume_capacity: '18.50',
    is_active: true,
    is_archived: false,
  },
  {
    id: 2,
    name: 'Eski yuk mashinasi',
    plate_number: '01B456BB',
    capacity: '900.00',
    volume_capacity: null,
    is_active: false,
    is_archived: false,
  },
  {
    id: 3,
    name: 'Arxivdagi mashina',
    plate_number: '01C789CC',
    capacity: '700.00',
    volume_capacity: '8.00',
    is_active: false,
    is_archived: true,
  },
]

const drivers: FleetDriver[] = [
  {
    id: 1,
    user: 11,
    phone: '+998900000001',
    license_number: 'ABC-123',
    vehicle_id: 1,
    vehicle_name: 'Katta yuk mashinasi',
    is_active: true,
    blocked: false,
  },
  {
    id: 2,
    user: 12,
    phone: '+998900000002',
    license_number: '',
    vehicle_id: null,
    vehicle_name: null,
    is_active: false,
    blocked: true,
  },
]

describe('dispetcher transport va haydovchi yordamchilari', () => {
  it('transport og‘irlik va hajm sig‘imlarini ijobiy, ikki kasr aniqligida tekshiradi', () => {
    const valid = {
      name: 'Yuk mashinasi',
      plate_number: '01A123AA',
      capacity: '1500.00',
      volume_capacity: '18.50',
      is_active: true,
    }
    expect(vehicleFormSchema.safeParse(valid).success).toBe(true)
    expect(vehicleFormSchema.safeParse({ ...valid, volume_capacity: '0' }).success).toBe(false)
    expect(vehicleFormSchema.safeParse({ ...valid, capacity: '1.234' }).success).toBe(false)
  })

  it('transportni saqlashda qiymatlarni tozalab, ikkala sig‘imni yuboradi', () => {
    expect(buildVehiclePayload({
      name: ' Yuk mashinasi ',
      plate_number: ' 01A123AA ',
      capacity: '1500.00',
      volume_capacity: '18.50',
      is_active: true,
    })).toEqual({
      name: 'Yuk mashinasi',
      plate_number: '01A123AA',
      capacity: '1500.00',
      volume_capacity: '18.50',
      is_active: true,
    })
  })

  it('transport ro‘yxatini nom, davlat raqami va holat bo‘yicha filtrlaydi', () => {
    expect(filterVehicles(vehicles, '01A123', 'active')).toEqual([vehicles[0]])
    expect(filterVehicles(vehicles, 'eski', 'inactive')).toEqual([vehicles[1]])
    expect(filterVehicles(vehicles, '', 'archived')).toEqual([vehicles[2]])
  })

  it('haydovchi yaratish telefon/parolni, tahrirlash esa transportni bo‘sh qoldirishni tekshiradi', () => {
    expect(driverCreateSchema.safeParse({
      phone: '+998900000001',
      password: 'vaqtinchalik123',
      license_number: '',
      vehicle_id: '',
    }).success).toBe(true)
    expect(driverCreateSchema.safeParse({
      phone: 'noto‘g‘ri',
      password: 'qisqa',
      license_number: '',
      vehicle_id: '',
    }).success).toBe(false)
    expect(buildDriverPayload({ license_number: ' ABC-123 ', vehicle_id: '' })).toEqual({
      license_number: 'ABC-123',
      vehicle_id: null,
    })
  })

  it('haydovchilarni telefon, guvohnoma, mashina va faollik bo‘yicha qidiradi', () => {
    expect(filterDrivers(drivers, 'ABC', 'active')).toEqual([drivers[0]])
    expect(filterDrivers(drivers, 'yuk mashinasi', 'all')).toEqual([drivers[0]])
    expect(filterDrivers(drivers, '', 'inactive')).toEqual([drivers[1]])
  })
})
