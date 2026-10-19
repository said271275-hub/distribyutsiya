import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Archive, LoaderCircle, Pencil, Plus, Search, Save, Truck, UserRound, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import api, { apiErrorMessage } from './api'
import {
  buildDriverPayload,
  buildVehiclePayload,
  driverCreateSchema,
  driverEditSchema,
  filterDrivers,
  filterVehicles,
  vehicleFormSchema,
  type DriverCreateValues,
  type DriverEditValues,
  type FleetDriver,
  type FleetVehicle,
  type VehicleFormValues,
} from './dispatcherFleetUtils'
import './DispatcherFleet.css'

type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] }
type StaffCreated = { id: number }
type VehicleRequest = { id?: number; values: VehicleFormValues }
type DriverRequest = { id?: number; values: DriverCreateValues | DriverEditValues }
type FleetTab = 'vehicles' | 'drivers'

const emptyVehicle: VehicleFormValues = {
  name: '',
  plate_number: '',
  capacity: '',
  volume_capacity: '',
  is_active: true,
}
const emptyDriverCreate: DriverCreateValues = {
  phone: '',
  password: '',
  license_number: '',
  vehicle_id: '',
}
const emptyDriverEdit: DriverEditValues = { license_number: '', vehicle_id: '' }
const emptyVehicles: FleetVehicle[] = []
const emptyDrivers: FleetDriver[] = []
const vehicleStatuses = ['all', 'active', 'inactive', 'archived'] as const
const driverStatuses = ['all', 'active', 'inactive'] as const

function vehicleStatusLabel(vehicle: FleetVehicle) {
  if (vehicle.is_archived) return 'Arxivlangan'
  return vehicle.is_active ? 'Faol' : 'Nofaol'
}

function driverStatusLabel(driver: FleetDriver) {
  return driver.is_active && !driver.blocked ? 'Faol' : 'Nofaol'
}

export default function DispatcherFleetPage() {
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<FleetTab>('vehicles')
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<string>('all')
  const [showVehicleForm, setShowVehicleForm] = useState(false)
  const [editingVehicle, setEditingVehicle] = useState<FleetVehicle | null>(null)
  const [showDriverForm, setShowDriverForm] = useState(false)
  const [editingDriver, setEditingDriver] = useState<FleetDriver | null>(null)
  const [pageError, setPageError] = useState('')
  const vehicleForm = useForm<VehicleFormValues>({
    resolver: zodResolver(vehicleFormSchema),
    defaultValues: emptyVehicle,
  })
  const driverCreateForm = useForm<DriverCreateValues>({
    resolver: zodResolver(driverCreateSchema),
    defaultValues: emptyDriverCreate,
  })
  const driverEditForm = useForm<DriverEditValues>({
    resolver: zodResolver(driverEditSchema),
    defaultValues: emptyDriverEdit,
  })
  const vehiclesQuery = useQuery({
    queryKey: ['dispatcher-fleet-vehicles'],
    queryFn: async () => (
      await api.get<Page<FleetVehicle>>('/v1/admin/vehicles/', { params: { page_size: 100 } })
    ).data,
  })
  const driversQuery = useQuery({
    queryKey: ['dispatcher-fleet-drivers'],
    queryFn: async () => (
      await api.get<Page<FleetDriver>>('/v1/admin/drivers/', { params: { page_size: 100 } })
    ).data,
  })
  const vehicles = vehiclesQuery.data?.results ?? emptyVehicles
  const drivers = driversQuery.data?.results ?? emptyDrivers
  const activeVehicles = vehicles.filter((vehicle) => vehicle.is_active && !vehicle.is_archived)
  const filteredVehicles = useMemo(
    () => filterVehicles(vehicles, search, status as typeof vehicleStatuses[number]),
    [vehicles, search, status],
  )
  const filteredDrivers = useMemo(
    () => filterDrivers(drivers, search, status as typeof driverStatuses[number]),
    [drivers, search, status],
  )

  const invalidateFleet = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['dispatcher-fleet-vehicles'] }),
      queryClient.invalidateQueries({ queryKey: ['dispatcher-fleet-drivers'] }),
      queryClient.invalidateQueries({ queryKey: ['dispatcher-trip-vehicles'] }),
      queryClient.invalidateQueries({ queryKey: ['dispatcher-trip-drivers'] }),
    ])
  }

  const saveVehicle = useMutation({
    mutationFn: async ({ id, values }: VehicleRequest) => {
      const payload = buildVehiclePayload(values)
      const response = id
        ? await api.patch<FleetVehicle>(`/v1/admin/vehicles/${id}/`, payload)
        : await api.post<FleetVehicle>('/v1/admin/vehicles/', payload)
      return response.data
    },
    onSuccess: async () => {
      setPageError('')
      setShowVehicleForm(false)
      setEditingVehicle(null)
      vehicleForm.reset(emptyVehicle)
      await invalidateFleet()
    },
    onError: (failure) => setPageError(apiErrorMessage(failure, 'Transport ma’lumotlarini saqlab bo‘lmadi.')),
  })

  const archiveVehicle = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/v1/admin/vehicles/${id}/`)
    },
    onSuccess: async () => {
      setPageError('')
      await invalidateFleet()
    },
    onError: (failure) => setPageError(apiErrorMessage(failure, 'Transportni arxivlab bo‘lmadi.')),
  })

  const saveDriver = useMutation({
    mutationFn: async ({ id, values }: DriverRequest) => {
      if (id) {
        const response = await api.patch<FleetDriver>(
          `/v1/admin/drivers/${id}/`,
          buildDriverPayload(values),
        )
        return response.data
      }

      if (!('phone' in values)) {
        throw new Error('Haydovchi telefon raqami kiritilmagan.')
      }
      const createValues = values
      const staff = await api.post<StaffCreated>('/v1/admin/staff/', {
        phone: createValues.phone.trim(),
        password: createValues.password,
        role: 'driver',
      })
      let driverPage = await api.get<Page<FleetDriver>>('/v1/admin/drivers/', {
        params: { page_size: 100 },
      })
      let profile = driverPage.data.results.find((driver) => driver.user === staff.data.id)
      while (!profile && driverPage.data.next) {
        driverPage = await api.get<Page<FleetDriver>>(driverPage.data.next)
        profile = driverPage.data.results.find((driver) => driver.user === staff.data.id)
      }
      if (!profile) {
        throw new Error('Haydovchi akkaunti yaratildi, ammo profili ro‘yxatda topilmadi. Ro‘yxatni yangilang.')
      }
      try {
        return (
          await api.patch<FleetDriver>(
          `/v1/admin/drivers/${profile.id}/`,
          buildDriverPayload(createValues),
          )
        ).data
      } catch (failure) {
        throw new Error(
          `Haydovchi akkaunti yaratildi, ammo profilini saqlash bajarilmadi. ${apiErrorMessage(failure, 'Qayta urinib ko‘ring.')}`,
        )
      }
    },
    onSuccess: async () => {
      setPageError('')
      setShowDriverForm(false)
      setEditingDriver(null)
      driverCreateForm.reset(emptyDriverCreate)
      driverEditForm.reset(emptyDriverEdit)
      await invalidateFleet()
    },
    onError: async (failure) => {
      setPageError(failure instanceof Error && !('response' in failure)
        ? failure.message
        : apiErrorMessage(failure, 'Haydovchi ma’lumotlarini saqlab bo‘lmadi.'))
      await invalidateFleet()
    },
  })

  const archiveDriver = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/v1/admin/drivers/${id}/`)
    },
    onSuccess: async () => {
      setPageError('')
      await invalidateFleet()
    },
    onError: (failure) => setPageError(apiErrorMessage(failure, 'Haydovchini arxivlab bo‘lmadi.')),
  })

  const startVehicleCreate = () => {
    setPageError('')
    setEditingVehicle(null)
    vehicleForm.reset(emptyVehicle)
    saveVehicle.reset()
    setShowVehicleForm(true)
  }
  const startVehicleEdit = (vehicle: FleetVehicle) => {
    setPageError('')
    setEditingVehicle(vehicle)
    vehicleForm.reset({
      name: vehicle.name,
      plate_number: vehicle.plate_number,
      capacity: vehicle.capacity,
      volume_capacity: vehicle.volume_capacity ?? '',
      is_active: vehicle.is_active,
    })
    saveVehicle.reset()
    setShowVehicleForm(true)
  }
  const startDriverCreate = () => {
    setPageError('')
    setEditingDriver(null)
    driverCreateForm.reset(emptyDriverCreate)
    saveDriver.reset()
    setShowDriverForm(true)
  }
  const startDriverEdit = (driver: FleetDriver) => {
    setPageError('')
    setEditingDriver(driver)
    driverEditForm.reset({
      license_number: driver.license_number,
      vehicle_id: driver.vehicle_id ? String(driver.vehicle_id) : '',
    })
    saveDriver.reset()
    setShowDriverForm(true)
  }

  const submitVehicle = vehicleForm.handleSubmit((values) => {
    saveVehicle.mutate({ id: editingVehicle?.id, values })
  })
  const submitDriverCreate = driverCreateForm.handleSubmit((values) => {
    saveDriver.mutate({ values })
  })
  const submitDriverEdit = driverEditForm.handleSubmit((values) => {
    if (editingDriver) saveDriver.mutate({ id: editingDriver.id, values })
  })

  const switchTab = (nextTab: FleetTab) => {
    setTab(nextTab)
    setSearch('')
    setStatus('all')
    setPageError('')
  }

  return (
    <section className="dispatcher-fleet-page">
      <div className="dispatcher-page-heading dispatcher-fleet-heading">
        <div>
          <span className="dispatcher-eyebrow">TRANSPORT BOSHQARUVI</span>
          <h1>Mashinalar va haydovchilar</h1>
          <p>Mashinalar sig‘imini belgilang, haydovchilarni yarating va transportga biriktiring.</p>
        </div>
        <button
          type="button"
          className="dispatcher-primary-button"
          onClick={tab === 'vehicles' ? startVehicleCreate : startDriverCreate}
        >
          <Plus size={16} /> {tab === 'vehicles' ? 'Mashina qo‘shish' : 'Haydovchi qo‘shish'}
        </button>
      </div>

      {pageError && <div className="dispatcher-fleet-error" role="alert">{pageError}</div>}

      <div className="dispatcher-fleet-tabs" role="tablist" aria-label="Transport bo‘limlari">
        <button type="button" role="tab" aria-selected={tab === 'vehicles'} onClick={() => switchTab('vehicles')}>
          <Truck size={16} /> Mashinalar <span>{vehiclesQuery.data?.count ?? 0}</span>
        </button>
        <button type="button" role="tab" aria-selected={tab === 'drivers'} onClick={() => switchTab('drivers')}>
          <UserRound size={16} /> Haydovchilar <span>{driversQuery.data?.count ?? 0}</span>
        </button>
      </div>

      <section className="dispatcher-card dispatcher-fleet-card">
        <div className="dispatcher-fleet-toolbar">
          <label className="dispatcher-fleet-search">
            <Search size={16} />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={tab === 'vehicles' ? 'Mashina nomi yoki davlat raqami' : 'Telefon, guvohnoma yoki mashina'}
              aria-label={tab === 'vehicles' ? 'Mashinalarni qidirish' : 'Haydovchilarni qidirish'}
            />
            {search && <button type="button" aria-label="Qidiruvni tozalash" onClick={() => setSearch('')}><X size={14} /></button>}
          </label>
          <label className="dispatcher-fleet-filter">
            <span>Holati</span>
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              {(tab === 'vehicles' ? vehicleStatuses : driverStatuses).map((value) => (
                <option key={value} value={value}>
                  {value === 'all' ? 'Barcha holatlar' : value === 'active' ? 'Faol' : value === 'archived' ? 'Arxivlangan' : 'Nofaol'}
                </option>
              ))}
            </select>
          </label>
        </div>

        {(tab === 'vehicles' ? vehiclesQuery.isLoading : driversQuery.isLoading) ? (
          <div className="dispatcher-loading" role="status"><span /> Ma’lumotlar yuklanmoqda…</div>
        ) : (tab === 'vehicles' ? vehiclesQuery.isError : driversQuery.isError) ? (
          <div className="dispatcher-error-state" role="alert">
            <p>{apiErrorMessage(tab === 'vehicles' ? vehiclesQuery.error : driversQuery.error, 'Ro‘yxatni yuklab bo‘lmadi.')}</p>
            <button type="button" onClick={() => void (tab === 'vehicles' ? vehiclesQuery.refetch() : driversQuery.refetch())}>
              Qayta urinish
            </button>
          </div>
        ) : tab === 'vehicles' ? (
          filteredVehicles.length ? (
            <div className="dispatcher-table-scroll">
              <table className="dispatcher-orders-table dispatcher-fleet-table">
                <thead><tr><th>Mashina</th><th>Davlat raqami</th><th>Og‘irlik sig‘imi</th><th>Hajm sig‘imi</th><th>Holati</th><th>Amallar</th></tr></thead>
                <tbody>
                  {filteredVehicles.map((vehicle) => (
                    <tr key={vehicle.id}>
                      <td><strong>{vehicle.name}</strong></td>
                      <td>{vehicle.plate_number}</td>
                      <td>{vehicle.capacity} kg</td>
                      <td>{vehicle.volume_capacity === null ? 'Kiritilmagan' : `${vehicle.volume_capacity} m³`}</td>
                      <td><span className={`dispatcher-status ${vehicle.is_archived ? 'dispatcher-status-cancelled' : vehicle.is_active ? 'dispatcher-status-confirmed' : 'dispatcher-status-new'}`}>{vehicleStatusLabel(vehicle)}</span></td>
                      <td>
                        <div className="dispatcher-fleet-actions">
                          {!vehicle.is_archived && (
                            <>
                              <button type="button" className="dispatcher-order-action" aria-label={`${vehicle.name} tahrirlash`} onClick={() => startVehicleEdit(vehicle)}><Pencil size={14} /> Tahrirlash</button>
                              <button
                                type="button"
                                className="dispatcher-order-action dispatcher-order-action-danger"
                                aria-label={`${vehicle.name} arxivlash`}
                                disabled={archiveVehicle.isPending}
                                onClick={() => {
                                  if (window.confirm(`“${vehicle.name}” arxivlansinmi? U butunlay o‘chirilmaydi.`)) archiveVehicle.mutate(vehicle.id)
                                }}
                              ><Archive size={14} /> Arxivlash</button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <div className="dispatcher-empty"><Truck size={22} /><strong>Mashinalar topilmadi</strong><span>Qidiruv yoki holat filtrini o‘zgartiring.</span></div>
        ) : filteredDrivers.length ? (
          <div className="dispatcher-table-scroll">
            <table className="dispatcher-orders-table dispatcher-fleet-table">
              <thead><tr><th>Haydovchi</th><th>Guvohnoma</th><th>Biriktirilgan mashina</th><th>Holati</th><th>Amallar</th></tr></thead>
              <tbody>
                {filteredDrivers.map((driver) => (
                  <tr key={driver.id}>
                    <td><strong>{driver.phone}</strong></td>
                    <td>{driver.license_number || 'Kiritilmagan'}</td>
                    <td>{driver.vehicle_name || 'Biriktirilmagan'}</td>
                    <td><span className={`dispatcher-status ${driver.is_active && !driver.blocked ? 'dispatcher-status-confirmed' : 'dispatcher-status-cancelled'}`}>{driverStatusLabel(driver)}</span></td>
                    <td>
                      <div className="dispatcher-fleet-actions">
                        <button type="button" className="dispatcher-order-action" aria-label={`${driver.phone} tahrirlash`} onClick={() => startDriverEdit(driver)}><Pencil size={14} /> Tahrirlash</button>
                        {(driver.is_active || !driver.blocked) && (
                          <button
                            type="button"
                            className="dispatcher-order-action dispatcher-order-action-danger"
                            aria-label={`${driver.phone} arxivlash`}
                            disabled={archiveDriver.isPending}
                            onClick={() => {
                              if (window.confirm(`${driver.phone} haydovchisi faolsizlantirilsinmi? Akkaunt o‘chirilmaydi.`)) archiveDriver.mutate(driver.id)
                            }}
                          ><Archive size={14} /> Arxivlash</button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <div className="dispatcher-empty"><UserRound size={22} /><strong>Haydovchilar topilmadi</strong><span>Qidiruv yoki holat filtrini o‘zgartiring.</span></div>}
      </section>

      {showVehicleForm && (
        <div className="dispatcher-dialog-backdrop" onMouseDown={(event) => {
          if (event.target === event.currentTarget && !saveVehicle.isPending) setShowVehicleForm(false)
        }}>
          <form
            className="dispatcher-confirm-dialog dispatcher-fleet-form"
            role="dialog"
            aria-modal="true"
            aria-labelledby="dispatcher-vehicle-form-title"
            onSubmit={(event) => void submitVehicle(event)}
          >
            <div className="dispatcher-fleet-form-heading">
              <h2 id="dispatcher-vehicle-form-title">{editingVehicle ? 'Mashinani tahrirlash' : 'Mashina qo‘shish'}</h2>
              <button type="button" aria-label="Oynani yopish" onClick={() => setShowVehicleForm(false)}><X size={17} /></button>
            </div>
            <label><span>Mashina nomi</span><input {...vehicleForm.register('name')} maxLength={120} />{vehicleForm.formState.errors.name && <small role="alert">{vehicleForm.formState.errors.name.message}</small>}</label>
            <label><span>Davlat raqami</span><input {...vehicleForm.register('plate_number')} maxLength={20} />{vehicleForm.formState.errors.plate_number && <small role="alert">{vehicleForm.formState.errors.plate_number.message}</small>}</label>
            <div className="dispatcher-fleet-form-grid">
              <label><span>Og‘irlik sig‘imi (kg)</span><input {...vehicleForm.register('capacity')} type="number" min="0.01" step="0.01" />{vehicleForm.formState.errors.capacity && <small role="alert">{vehicleForm.formState.errors.capacity.message}</small>}</label>
              <label><span>Hajm sig‘imi (m³)</span><input {...vehicleForm.register('volume_capacity')} type="number" min="0.01" step="0.01" />{vehicleForm.formState.errors.volume_capacity && <small role="alert">{vehicleForm.formState.errors.volume_capacity.message}</small>}</label>
            </div>
            <label className="dispatcher-fleet-active"><input {...vehicleForm.register('is_active')} type="checkbox" /><span>Transport faol</span></label>
            {saveVehicle.isError && <p className="dispatcher-fleet-form-error" role="alert">{apiErrorMessage(saveVehicle.error, 'Transport ma’lumotlarini saqlab bo‘lmadi.')}</p>}
            <div className="dispatcher-dialog-actions">
              <button type="button" className="dispatcher-order-action" disabled={saveVehicle.isPending} onClick={() => setShowVehicleForm(false)}>Bekor qilish</button>
              <button type="submit" className="dispatcher-primary-button" disabled={saveVehicle.isPending}>
                {saveVehicle.isPending ? <LoaderCircle className="dispatcher-spinning" size={15} /> : <Save size={15} />} Saqlash
              </button>
            </div>
          </form>
        </div>
      )}

      {showDriverForm && (
        <div className="dispatcher-dialog-backdrop" onMouseDown={(event) => {
          if (event.target === event.currentTarget && !saveDriver.isPending) setShowDriverForm(false)
        }}>
          <form
            className="dispatcher-confirm-dialog dispatcher-fleet-form"
            role="dialog"
            aria-modal="true"
            aria-labelledby="dispatcher-driver-form-title"
            onSubmit={(event) => void (editingDriver ? submitDriverEdit(event) : submitDriverCreate(event))}
          >
            <div className="dispatcher-fleet-form-heading">
              <h2 id="dispatcher-driver-form-title">{editingDriver ? 'Haydovchini tahrirlash' : 'Haydovchi qo‘shish'}</h2>
              <button type="button" aria-label="Oynani yopish" disabled={saveDriver.isPending} onClick={() => setShowDriverForm(false)}><X size={17} /></button>
            </div>
            {editingDriver ? (
              <p className="dispatcher-fleet-phone">{editingDriver.phone}</p>
            ) : (
              <>
                <label><span>Telefon raqami</span><input {...driverCreateForm.register('phone')} autoComplete="tel" />{driverCreateForm.formState.errors.phone && <small role="alert">{driverCreateForm.formState.errors.phone.message}</small>}</label>
                <label><span>Vaqtinchalik parol</span><input {...driverCreateForm.register('password')} type="password" autoComplete="new-password" />{driverCreateForm.formState.errors.password && <small role="alert">{driverCreateForm.formState.errors.password.message}</small>}</label>
              </>
            )}
            <DriverFields
              activeVehicles={activeVehicles}
              currentDriver={editingDriver}
              createForm={driverCreateForm}
              editForm={driverEditForm}
              editing={Boolean(editingDriver)}
            />
            {saveDriver.isError && <p className="dispatcher-fleet-form-error" role="alert">{saveDriver.error instanceof Error && !('response' in saveDriver.error) ? saveDriver.error.message : apiErrorMessage(saveDriver.error, 'Haydovchi ma’lumotlarini saqlab bo‘lmadi.')}</p>}
            <div className="dispatcher-dialog-actions">
              <button type="button" className="dispatcher-order-action" disabled={saveDriver.isPending} onClick={() => setShowDriverForm(false)}>Bekor qilish</button>
              <button type="submit" className="dispatcher-primary-button" disabled={saveDriver.isPending}>
                {saveDriver.isPending ? <LoaderCircle className="dispatcher-spinning" size={15} /> : <Save size={15} />} Saqlash
              </button>
            </div>
          </form>
        </div>
      )}
    </section>
  )
}

function DriverFields({
  activeVehicles,
  currentDriver,
  createForm,
  editForm,
  editing,
}: {
  activeVehicles: FleetVehicle[]
  currentDriver: FleetDriver | null
  createForm: UseFormReturn<DriverCreateValues>
  editForm: UseFormReturn<DriverEditValues>
  editing: boolean
}) {
  const register = editing ? editForm.register : createForm.register
  const errors = editing ? editForm.formState.errors : createForm.formState.errors
  const currentVehicleMissing = currentDriver?.vehicle_id &&
    !activeVehicles.some((vehicle) => vehicle.id === currentDriver.vehicle_id)
  return (
    <>
      <label><span>Guvohnoma raqami</span><input {...register('license_number')} maxLength={80} />{errors.license_number && <small role="alert">{errors.license_number.message}</small>}</label>
      <label>
        <span>Mashinaga biriktirish</span>
        <select {...register('vehicle_id')}>
          <option value="">Biriktirilmagan</option>
          {currentVehicleMissing && <option value={String(currentDriver?.vehicle_id)}>{currentDriver?.vehicle_name} (faol emas)</option>}
          {activeVehicles.map((vehicle) => (
            <option key={vehicle.id} value={String(vehicle.id)}>
              {vehicle.name} · {vehicle.plate_number}
            </option>
          ))}
        </select>
        {errors.vehicle_id && <small role="alert">{errors.vehicle_id.message}</small>}
      </label>
    </>
  )
}
