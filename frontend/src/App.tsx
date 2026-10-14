import './App.css'

function App() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl items-center px-5 py-12 sm:px-8">
      <section
        aria-labelledby="welcome-title"
        className="w-full rounded-3xl border border-slate-200 bg-white p-7 shadow-sm sm:p-12"
      >
        <p className="mb-4 text-sm font-semibold uppercase tracking-[0.18em] text-emerald-700">
          Buyurtma va yetkazib berish
        </p>
        <h1
          id="welcome-title"
          className="max-w-2xl text-3xl font-bold tracking-tight text-slate-950 sm:text-5xl"
        >
          Distribyutsiya tizimi uchun asos tayyor
        </h1>
        <p className="mt-5 max-w-2xl text-base leading-7 text-slate-600 sm:text-lg">
          Veb-ilova ishga tushdi. Keyingi bosqichlarda buyurtmalar va
          yetkazib berish jarayonlari backend API orqali ulanadi.
        </p>
        <div className="mt-8 inline-flex items-center gap-2 rounded-full bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-800">
          <span aria-hidden="true" className="size-2 rounded-full bg-emerald-500" />
          Frontend tayyor
        </div>
      </section>
    </main>
  )
}

export default App
