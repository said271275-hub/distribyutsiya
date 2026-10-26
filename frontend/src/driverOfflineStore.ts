import type { AuthUser } from './api'
import { sortDriverActionsBySequence } from './driverOfflineUtils'

const DATABASE_NAME = 'tarqatuv-driver-offline'
const DATABASE_VERSION = 1

export type DriverActionPayload = {
  reason?: 'shop_closed' | 'refused' | 'partial_delivery' | 'other'
  note?: string
  delivered_orders?: Array<{
    order_id: number
    items: Array<{ item_id: number; quantity: string }>
  }>
}

export type QueuedDriverAction = {
  actionId: string
  actorId: number
  tripId: number
  stopId: number
  date: string
  type: 'delivered' | 'issue'
  payload: DriverActionPayload
  createdAt: string
  sequence?: number
}

type TripSnapshotRow<T> = {
  key: string
  actorId: number
  date: string
  trips: T[]
  savedAt: string
}

type OfflineSessionRow = {
  actorId: number
  companyId: number | null
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION)
    request.onupgradeneeded = () => {
      const database = request.result
      if (!database.objectStoreNames.contains('trips')) {
        database.createObjectStore('trips', { keyPath: 'key' })
      }
      if (!database.objectStoreNames.contains('outbox')) {
        const outbox = database.createObjectStore('outbox', {
          keyPath: 'sequence',
          autoIncrement: true,
        })
        outbox.createIndex('actionId', 'actionId', { unique: true })
        outbox.createIndex('actorId', 'actorId')
      }
      if (!database.objectStoreNames.contains('sessions')) {
        database.createObjectStore('sessions', { keyPath: 'actorId' })
      }
    }
    request.onsuccess = () => {
      request.result.onversionchange = () => request.result.close()
      resolve(request.result)
    }
    request.onerror = () => reject(request.error ?? new Error('IndexedDB ochilmadi.'))
  })
}

function snapshotKey(actorId: number, date: string) {
  return `${actorId}:${date}`
}

export async function getDriverTrips<T>(actorId: number, date: string): Promise<T[] | undefined> {
  const database = await openDatabase()
  return new Promise((resolve, reject) => {
    const transaction = database.transaction('trips', 'readonly')
    const request = transaction.objectStore('trips').get(snapshotKey(actorId, date))
    let trips: T[] | undefined
    request.onsuccess = () => {
      trips = (request.result as TripSnapshotRow<T> | undefined)?.trips
    }
    transaction.oncomplete = () => {
      database.close()
      resolve(trips)
    }
    transaction.onerror = () => {
      database.close()
      reject(transaction.error ?? new Error('Reys nusxasini o‘qib bo‘lmadi.'))
    }
  })
}

export async function saveDriverTrips<T>(actorId: number, date: string, trips: T[]): Promise<void> {
  const database = await openDatabase()
  return new Promise((resolve, reject) => {
    const transaction = database.transaction('trips', 'readwrite')
    transaction.objectStore('trips').put({
      key: snapshotKey(actorId, date),
      actorId,
      date,
      trips,
      savedAt: new Date().toISOString(),
    } satisfies TripSnapshotRow<T>)
    transaction.oncomplete = () => {
      database.close()
      resolve()
    }
    transaction.onerror = () => {
      database.close()
      reject(transaction.error ?? new Error('Reys nusxasini saqlab bo‘lmadi.'))
    }
  })
}

export async function enqueueDriverActionWithTrips<T>(
  action: QueuedDriverAction,
  trips: T[],
): Promise<void> {
  const database = await openDatabase()
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(['outbox', 'trips'], 'readwrite')
    transaction.objectStore('outbox').add(action)
    transaction.objectStore('trips').put({
      key: snapshotKey(action.actorId, action.date),
      actorId: action.actorId,
      date: action.date,
      trips,
      savedAt: new Date().toISOString(),
    } satisfies TripSnapshotRow<T>)
    transaction.oncomplete = () => {
      database.close()
      resolve()
    }
    transaction.onerror = () => {
      database.close()
      reject(transaction.error ?? new Error('Oflayn amalni saqlab bo‘lmadi.'))
    }
  })
}

export async function getPendingDriverActions(actorId: number): Promise<QueuedDriverAction[]> {
  const database = await openDatabase()
  return new Promise((resolve, reject) => {
    const transaction = database.transaction('outbox', 'readonly')
    const request = transaction.objectStore('outbox').getAll()
    let actions: QueuedDriverAction[] = []
    request.onsuccess = () => {
      actions = (request.result as QueuedDriverAction[])
        .filter((action) => action.actorId === actorId)
      actions = sortDriverActionsBySequence(actions)
    }
    transaction.oncomplete = () => {
      database.close()
      resolve(actions)
    }
    transaction.onerror = () => {
      database.close()
      reject(transaction.error ?? new Error('Oflayn amallarni o‘qib bo‘lmadi.'))
    }
  })
}

export async function removePendingDriverAction(sequence: number): Promise<void> {
  const database = await openDatabase()
  return new Promise((resolve, reject) => {
    const transaction = database.transaction('outbox', 'readwrite')
    transaction.objectStore('outbox').delete(sequence)
    transaction.oncomplete = () => {
      database.close()
      resolve()
    }
    transaction.onerror = () => {
      database.close()
      reject(transaction.error ?? new Error('Sinxronlangan amalni navbatdan olib bo‘lmadi.'))
    }
  })
}

export async function getDriverOfflineSession(): Promise<AuthUser | null> {
  const database = await openDatabase()
  return new Promise((resolve, reject) => {
    const transaction = database.transaction('sessions', 'readonly')
    const request = transaction.objectStore('sessions').getAll()
    let session: OfflineSessionRow | undefined
    request.onsuccess = () => {
      session = (request.result as OfflineSessionRow[]).at(-1)
    }
    transaction.oncomplete = () => {
      database.close()
      resolve(session ? {
        id: session.actorId,
        phone: '',
        role: 'driver',
        company_id: session.companyId,
      } : null)
    }
    transaction.onerror = () => {
      database.close()
      reject(transaction.error ?? new Error('Oflayn sessiyani o‘qib bo‘lmadi.'))
    }
  })
}

export async function saveDriverOfflineSession(user: AuthUser): Promise<void> {
  if (user.role !== 'driver') {
    await clearDriverOfflineData()
    return
  }
  const database = await openDatabase()
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(['trips', 'outbox', 'sessions'], 'readwrite')
    const sessions = transaction.objectStore('sessions')
    const session: OfflineSessionRow = { actorId: user.id, companyId: user.company_id }
    const request = sessions.getAll()
    request.onsuccess = () => {
      const storedSessions = request.result as OfflineSessionRow[]
      if (storedSessions.some((stored) => stored.actorId !== user.id)) {
        transaction.objectStore('trips').clear()
        transaction.objectStore('outbox').clear()
      }
      sessions.clear()
      sessions.put(session)
    }
    transaction.oncomplete = () => {
      database.close()
      resolve()
    }
    transaction.onerror = () => {
      database.close()
      reject(transaction.error ?? new Error('Oflayn sessiyani saqlab bo‘lmadi.'))
    }
  })
}

export async function clearDriverOfflineData(): Promise<void> {
  try {
    const database = await openDatabase()
    await new Promise<void>((resolve, reject) => {
      const transaction = database.transaction(['trips', 'outbox', 'sessions'], 'readwrite')
      transaction.objectStore('trips').clear()
      transaction.objectStore('outbox').clear()
      transaction.objectStore('sessions').clear()
      transaction.oncomplete = () => resolve()
      transaction.onerror = () => reject(transaction.error ?? new Error('Mahalliy ma’lumotlarni o‘chirib bo‘lmadi.'))
    })
    database.close()
  } catch {
    return
  }
}