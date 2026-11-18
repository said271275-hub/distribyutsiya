import { describe, it, expect } from 'vitest';

export interface CompanySubscriptionItem {
  id: number;
  shop: {
    id: number;
    name: string;
    phone: string;
    address: string;
    district: string;
  };
  status: 'pending' | 'active' | 'rejected' | 'blocked' | 'cancelled';
  created_at: string;
  rejection_reason?: string | null;
}

export function filterSubscriptions(
  items: CompanySubscriptionItem[],
  tab: 'all' | 'pending' | 'active'
): CompanySubscriptionItem[] {
  if (tab === 'all') return items;
  return items.filter((item) => item.status === tab);
}

export function maskPhoneNumber(phone: string): string {
  if (!phone || phone.length < 9) return phone;
  // e.g. +998901234567 -> +998 90 *** ** 67
  const cleaned = phone.replace(/\D/g, '');
  if (cleaned.length === 12 && cleaned.startsWith('998')) {
    return `+998 ${cleaned.slice(3, 5)} *** ** ${cleaned.slice(10)}`;
  }
  return phone;
}

export function validateCompanyRegisterStep1(values: {
  name: string;
  tax_id: string;
  phone: string;
  service_districts: string[];
}): string | null {
  if (!values.name.trim()) return "Kompaniya nomini kiriting";
  if (!/^\d{9}$/.test(values.tax_id.trim())) return "STIR (INN) 9 ta raqamdan iborat bo'lishi kerak";
  if (!values.phone.trim()) return "Telefon raqamini kiriting";
  if (values.service_districts.length === 0) return "Kamida bitta xizmat ko'rsatish tumanini tanlang";
  return null;
}

export function validateCompanyRegisterStep2(values: {
  admin_phone: string;
  otp_code: string;
  password: string;
  password_confirm: string;
}): string | null {
  if (!values.admin_phone.trim()) return "Administrator telefonini kiriting";
  if (values.otp_code.trim().length !== 6) return "Tasdiqlash kodi 6 ta raqam bo'lishi kerak";
  if (values.password.length < 6) return "Parol kamida 6 belgidan iborat bo'lishi kerak";
  if (values.password !== values.password_confirm) return "Parollar mos kelmadi";
  return null;
}

describe('Company Features & Subscriptions Helper Tests', () => {
  const sampleSubscriptions: CompanySubscriptionItem[] = [
    {
      id: 1,
      shop: { id: 101, name: 'Do‘kon A', phone: '+998901234567', address: 'Chilonzor 1', district: 'Chilonzor' },
      status: 'pending',
      created_at: '2026-03-01T10:00:00Z',
    },
    {
      id: 2,
      shop: { id: 102, name: 'Do‘kon B', phone: '+998909876543', address: 'Yunusobod 4', district: 'Yunusobod' },
      status: 'active',
      created_at: '2026-03-02T11:00:00Z',
    },
    {
      id: 3,
      shop: { id: 103, name: 'Do‘kon C', phone: '+998933333333', address: 'Mirzo Ulug‘bek 5', district: 'Mirzo Ulug‘bek' },
      status: 'rejected',
      created_at: '2026-03-03T12:00:00Z',
    },
  ];

  it('filters subscriptions by status correctly', () => {
    expect(filterSubscriptions(sampleSubscriptions, 'all')).toHaveLength(3);
    expect(filterSubscriptions(sampleSubscriptions, 'pending')).toHaveLength(1);
    expect(filterSubscriptions(sampleSubscriptions, 'pending')[0].shop.name).toBe('Do‘kon A');
    expect(filterSubscriptions(sampleSubscriptions, 'active')).toHaveLength(1);
    expect(filterSubscriptions(sampleSubscriptions, 'active')[0].shop.name).toBe('Do‘kon B');
  });

  it('masks phone numbers appropriately for privacy', () => {
    expect(maskPhoneNumber('+998901234567')).toBe('+998 90 *** ** 67');
    expect(maskPhoneNumber('998901234567')).toBe('+998 90 *** ** 67');
    expect(maskPhoneNumber('12345')).toBe('12345');
  });

  it('validates Step 1 company registration data', () => {
    expect(validateCompanyRegisterStep1({
      name: '',
      tax_id: '123456789',
      phone: '+998901112233',
      service_districts: ['Chilonzor'],
    })).toBe('Kompaniya nomini kiriting');

    expect(validateCompanyRegisterStep1({
      name: 'Test OOO',
      tax_id: '12345',
      phone: '+998901112233',
      service_districts: ['Chilonzor'],
    })).toBe("STIR (INN) 9 ta raqamdan iborat bo'lishi kerak");

    expect(validateCompanyRegisterStep1({
      name: 'Test OOO',
      tax_id: '123456789',
      phone: '+998901112233',
      service_districts: [],
    })).toBe("Kamida bitta xizmat ko'rsatish tumanini tanlang");

    expect(validateCompanyRegisterStep1({
      name: 'Test OOO',
      tax_id: '123456789',
      phone: '+998901112233',
      service_districts: ['Chilonzor'],
    })).toBeNull();
  });

  it('validates Step 2 admin registration data', () => {
    expect(validateCompanyRegisterStep2({
      admin_phone: '',
      otp_code: '123456',
      password: 'secretpassword',
      password_confirm: 'secretpassword',
    })).toBe('Administrator telefonini kiriting');

    expect(validateCompanyRegisterStep2({
      admin_phone: '+998901234567',
      otp_code: '123',
      password: 'secretpassword',
      password_confirm: 'secretpassword',
    })).toBe("Tasdiqlash kodi 6 ta raqam bo'lishi kerak");

    expect(validateCompanyRegisterStep2({
      admin_phone: '+998901234567',
      otp_code: '123456',
      password: 'pass',
      password_confirm: 'pass',
    })).toBe("Parol kamida 6 belgidan iborat bo'lishi kerak");

    expect(validateCompanyRegisterStep2({
      admin_phone: '+998901234567',
      otp_code: '123456',
      password: 'secretpassword',
      password_confirm: 'wrongpassword',
    })).toBe('Parollar mos kelmadi');

    expect(validateCompanyRegisterStep2({
      admin_phone: '+998901234567',
      otp_code: '123456',
      password: 'secretpassword',
      password_confirm: 'secretpassword',
    })).toBeNull();
  });
});

