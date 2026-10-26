import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'
import { createHash } from 'node:crypto'

const driverIcons = ['/icons/driver-192.svg', '/icons/driver-512.svg']

function driverServiceWorker(precacheUrls: string[], versionSalt = '', cacheDevelopmentAssets = false) {
  const version = createHash('sha256').update(JSON.stringify([precacheUrls, versionSalt])).digest('hex').slice(0, 12)
  return `const CACHE_PREFIX = 'tarqatuv-driver-shell-';
const CACHE_NAME = CACHE_PREFIX + '${version}';
const PRECACHE_URLS = ${JSON.stringify(precacheUrls)};
const CACHE_DEVELOPMENT_ASSETS = ${cacheDevelopmentAssets};

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await Promise.all(PRECACHE_URLS.map(async (url) => {
      try {
        const response = await fetch(url, { cache: 'reload' });
        if (response.ok) await cache.put(url, response);
      } catch {}
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const cacheNames = await caches.keys();
    await Promise.all(cacheNames
      .filter((name) => name.startsWith(CACHE_PREFIX) && name !== CACHE_NAME)
      .map((name) => caches.delete(name)));
    await self.clients.claim();
  })());
});

self.addEventListener('message', (event) => {
  if (event.data?.type === 'CLEAR_DRIVER_APP_CACHE') {
    event.waitUntil(caches.keys().then((cacheNames) => Promise.all(
      cacheNames.filter((name) => name.startsWith(CACHE_PREFIX)).map((name) => caches.delete(name)),
    )));
  }
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname === '/api' || url.pathname.startsWith('/api/')) {
    event.respondWith(fetch(request, { cache: 'no-store' }));
    return;
  }
  const isDriverPage = url.pathname === '/driver' || url.pathname.startsWith('/driver/');
  if (request.mode === 'navigate' && isDriverPage) {
    event.respondWith(caches.open(CACHE_NAME).then(async (cache) => (
      await cache.match('/index.html') ?? fetch(request)
    )));
    return;
  }
  const isDevelopmentClient = url.pathname === '/@vite/client' || url.pathname === '/@react-refresh';
  const isShellAsset = PRECACHE_URLS.includes(url.pathname);
  if (!isShellAsset && !(CACHE_DEVELOPMENT_ASSETS && (isDevelopmentClient || /\\.(?:m?js|tsx?|css|svg|png|webp|woff2?)$/i.test(url.pathname)))) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);
    const cached = await cache.match(request);
    if (cached) return cached;
    const response = await fetch(request);
    if (response.ok) await cache.put(request, response.clone());
    return response;
  })());
});`
}

function driverPwaPlugin() {
  return {
    name: 'driver-pwa-shell',
    configureServer(server: { middlewares: { use: (path: string, handler: (_request: unknown, response: { setHeader: (name: string, value: string) => void; end: (body: string) => void }) => void) => void } }) {
      const version = String(Date.now())
      server.middlewares.use('/sw.js', (_request, response) => {
        response.setHeader('Content-Type', 'application/javascript; charset=utf-8')
        response.setHeader('Service-Worker-Allowed', '/driver')
        response.end(driverServiceWorker(['/index.html', ...driverIcons], version, true))
      })
    },
    generateBundle(_options: unknown, bundle: Record<string, {
      type: string
      fileName: string
      isEntry?: boolean
      imports?: string[]
      dynamicImports?: string[]
      facadeModuleId?: string
      viteMetadata?: { importedCss?: Set<string>; importedAssets?: Set<string> }
    }>) {
      const outputs = Object.values(bundle)
      const outputByFile = new Map(outputs.map((output) => [output.fileName, output]))
      const assets = new Set<string>()
      const visited = new Set<string>()
      const addChunk = (fileName: string, includeDynamic: boolean) => {
        if (visited.has(fileName)) return
        visited.add(fileName)
        const output = outputByFile.get(fileName)
        if (!output) return
        assets.add(fileName)
        output.viteMetadata?.importedCss?.forEach((asset) => assets.add(asset))
        output.viteMetadata?.importedAssets?.forEach((asset) => assets.add(asset))
        output.imports?.forEach((dependency) => addChunk(dependency, false))
        if (includeDynamic) output.dynamicImports?.forEach((dependency) => addChunk(dependency, true))
      }
      const entry = outputs.find((output) => output.type === 'chunk' && output.isEntry)
      const driver = outputs.find((output) => output.type === 'chunk' && output.facadeModuleId?.endsWith('/DriverPanel.tsx'))
      if (entry) addChunk(entry.fileName, false)
      if (driver) addChunk(driver.fileName, true)
      const precacheUrls = ['/index.html', ...driverIcons, ...Array.from(assets, (fileName) => `/${fileName}`)]
      this.emitFile({ type: 'asset', fileName: 'sw.js', source: driverServiceWorker(precacheUrls) })
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), driverPwaPlugin()],
  server: {
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
