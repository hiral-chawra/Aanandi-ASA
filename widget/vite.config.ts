import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  build: {
    lib: {
      entry: 'src/index.tsx',
      name: 'AanandiWidget',
      fileName: () => 'widget.min.js',
      formats: ['iife'],
    },
    rollupOptions: {
      // Bundle everything — no external deps so widget is fully self-contained
      external: [],
      output: {
        inlineDynamicImports: true,
        entryFileNames: 'widget.min.js',
        // Inline CSS into JS so Shadow DOM can inject it
        assetFileNames: 'widget.[ext]',
      },
    },
    cssCodeSplit: false,
    minify: 'esbuild',
    sourcemap: false,
  },
  define: {
    // Needed for React 19 in library/iife mode
    'process.env.NODE_ENV': JSON.stringify('production'),
  },
});
