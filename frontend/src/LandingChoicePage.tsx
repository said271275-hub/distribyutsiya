import { ArrowRight, Building2, Package, Store } from 'lucide-react'
import { Link, Navigate } from 'react-router-dom'
import { useAuth } from './useAuth'
import { roleHomes } from './roleAccess'
import { SimpleThemeToggle } from './SimpleThemeToggle'
import './App.css'
import './LandingChoicePage.css'

export default function LandingChoicePage() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <main className="full-loader">
        <span className="button-spinner" /> Yuklanmoqda…
      </main>
    )
  }

  if (user) {
    return <Navigate to={user.must_change_password ? '/password/change' : roleHomes[user.role]} replace />
  }

  return (
    <main className="landing-choice-layout">
      <div className="landing-choice-container">
        <div className="landing-topbar">
          <Link to="/" className="landing-brand" aria-label="Tarqatuv">
            <span className="landing-brand-mark"><Package size={20} /></span>
            <span>
              <strong>tarqatuv</strong>
              <small>BOSHQARUV TIZIMI</small>
            </span>
          </Link>
          <SimpleThemeToggle />
        </div>

        <header className="landing-choice-header">
          <div className="landing-badge">
            <Package size={16} />
            <span>B2B DISTRIBYUTSIYA PLATFORMASI</span>
          </div>
          <h1>Tarqatuv boshqaruv tizimi</h1>
          <p>
            Do‘konlar va distribyutor kompaniyalarni yagona tizimda birlashtiruvchi zamonaviy savdo va logistika platformasi.
          </p>
        </header>

        <div className="landing-cards-grid">
          {/* Shop Card */}
          <div className="landing-role-card">
            <div className="landing-role-icon shop-icon">
              <Store size={32} />
            </div>
            <div className="landing-role-content">
              <h2>Do‘konlar uchun</h2>
              <p>
                Turli distribyutorlardan tovarlarni qidiring, bitta savatdan bir nechta kompaniyaga buyurtma bering va yetkazishni kuzatib boring.
              </p>
              <ul className="landing-role-features">
                <li>Bitta savatdan ko‘p kompaniyali buyurtma</li>
                <li>Haqiqiy vaqt rejimida haydovchi yetib kelish vaqti (ETA)</li>
                <li>Qarzlar va to‘lovlar shaffof hisobi</li>
              </ul>
            </div>
            <div className="landing-role-actions">
              <Link to="/login" className="primary-button landing-action-btn">
                <span>Do‘kon sifatida kirish</span>
                <ArrowRight size={16} />
              </Link>
              <Link to="/register" className="secondary-button landing-action-btn">
                <span>Yangi do‘konni ro‘yxatdan o‘tkazish</span>
              </Link>
            </div>
          </div>

          {/* Company Card */}
          <div className="landing-role-card company-card">
            <div className="landing-role-icon company-icon">
              <Building2 size={32} />
            </div>
            <div className="landing-role-content">
              <h2>Distribyutor kompaniyalar uchun</h2>
              <p>
                O‘z mahsulotlaringizni soting, do‘konlar obunasini boshqaring, avtomatik reys tuzing va ombor harakatlarini to‘liq nazorat qiling.
              </p>
              <ul className="landing-role-features">
                <li>Katalog, narxlar va do‘konlar obunasi boshqaruvi</li>
                <li>Avtomatik reys tuzish va haydovchi ilovasi</li>
                <li>To‘liq ombor hisobi, qarz va to‘lovlar boshqaruvi</li>
              </ul>
            </div>
            <div className="landing-role-actions">
              <Link to="/staff/login" className="primary-button landing-action-btn">
                <span>Kompaniya kabinetiga kirish</span>
                <ArrowRight size={16} />
              </Link>
              <Link to="/company/register" className="secondary-button landing-action-btn">
                <span>Yangi kompaniyani ro‘yxatdan o‘tkazish</span>
              </Link>
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}
