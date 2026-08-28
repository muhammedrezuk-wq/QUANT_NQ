import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// base:'./' → مسارات نسبية، فالمُخرَج built يشتغل مقدَّمًا أوفلاين من خادم الحوكمة المحلي (١٥ §٦/٧)
export default defineConfig({
  plugins: [react()],
  base: './',
  server: {
    port: 5173,
    // أثناء التطوير: نمرّر طلبات الحوكمة للخادم المحلي (يقرأ النواة + يترجم للعربي)
    proxy: { '/gov': 'http://127.0.0.1:8090' },
  },
  build: { outDir: 'built' },
})
