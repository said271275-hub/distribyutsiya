import { z } from 'zod'

const decimalPattern = /^\d+(\.\d{1,2})?$/
const phonePattern = /^\+?[0-9\s()-]{7,20}$/
const requiredCapacity = (label: string) => z.string()
  .trim()
  .refine((value) => decimalPattern.test(value), `${label} qiymatini to‘g‘ri kiriting.`)
  .refine((value) => Number(value) > 0, `${label} noldan katta bo‘lishi kerak.`)

export const vehicleFormSchema = z.object({
  name: z.string().trim().min(1, 'Transport nomini kiriting.').max(120, 'Nom 120 belgidan oshmasin.'),
  plate_number: z.string().trim().min(1, 'Davlat raqamini kiriting.').max(20, 'Raqam 20 belgidan oshmasin.'),
  capacity: requiredCapacity('Og‘irlik sig‘imi'),
  volume_capacity: requiredCapacity('Hajm sig‘imi'),
  is_active: z.boolean(),
})

export const driverCreateSchema = z.object({
  phone: z.string().trim().regex(phonePattern, 'Telefon raqamini to‘g‘ri kiriting.'),
  password: z.string().min(8, 'Vaqtinchalik parol kamida 8 belgidan iborat bo‘lsin.'),
  license_number: z.string().trim().max(80, 'Guvohnoma raqami 80 belgidan oshmasin.'),
  vehicle_id: z.string(),
})

export const driverEditSchema = z.object({
  license_number: z.string().trim().max(80, 'Guvohnoma raqami 80 belgidan oshmasin.'),
  vehicle_id: z.string(),
})

export type FleetVehicle = {
  id: number
  name: string
  plate_number: string
  capacity: string
  volume_capacity: string | null
  is_active: boolean
  is_archived: boolean
}

export type FleetDriver = {
  id: number
  user: number
  phone: string
  license_number: string
  vehicle_id: number | null
  vehicle_name: string | null
  is_active: boolean
  blocked: boolean
}

export type VehicleFormValues = z.infer<typeof vehicleFormSchema>
export type DriverCreateValues = z.infer<typeof driverCreateSchema>
export type DriverEditValues = z.infer<typeof driverEditSchema>

export function buildVehiclePayload(values: VehicleFormValues) {
  return {
    name: values.name.trim(),
    plate_number: values.plate_number.trim(),
    capacity: values.capacity.trim(),
    volume_capacity: values.volume_capacity.trim(),
    is_active: values.is_active,
  }
}

export function buildDriverPayload(values: DriverCreateValues | DriverEditValues) {
  return {
    license_number: values.license_number.trim(),
    vehicle_id: values.vehicle_id ? Number(values.vehicle_id) : null,
  }
}

export function filterVehicles(
  vehicles: FleetVehicle[],
  search: string,
  status: 'all' | 'active' | 'inactive' | 'archived',
) {
  const query = search.trim().toLocaleLowerCase('uz-UZ')
  return vehicles.filter((vehicle) => {
    const matchesStatus = status === 'all' ||
      (status === 'archived' ? vehicle.is_archived :
        status === 'active' ? vehicle.is_active && !vehicle.is_archived :
          !vehicle.is_active && !vehicle.is_archived)
    const matchesSearch = !query ||
      `${vehicle.name} ${vehicle.plate_number}`.toLocaleLowerCase('uz-UZ').includes(query)
    return matchesStatus && matchesSearch
  })
}

export function filterDrivers(
  drivers: FleetDriver[],
  search: string,
  status: 'all' | 'active' | 'inactive',
) {
  const query = search.trim().toLocaleLowerCase('uz-UZ')
  return drivers.filter((driver) => {
    const matchesStatus = status === 'all' ||
      (status === 'active' ? driver.is_active && !driver.blocked : !driver.is_active || driver.blocked)
    const matchesSearch = !query ||
      `${driver.phone} ${driver.license_number} ${driver.vehicle_name ?? ''}`
        .toLocaleLowerCase('uz-UZ').includes(query)
    return matchesStatus && matchesSearch
  })
}
