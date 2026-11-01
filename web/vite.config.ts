import { defineConfig, loadEnv } from 'vite';
import type { ViteUserConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  // GitHub Pages serves from /<repo>/, so the base path comes from the environment.
  const base = env.VITE_BASE_PATH || '/';
  if (!base.startsWith('/')) {
    // Git Bash on Windows rewrites a leading slash into a Windows path, which would otherwise
    // build a site that loads as a blank page.
    throw new Error(
      `VITE_BASE_PATH must start with a slash, got "${base}". In Git Bash, run with MSYS_NO_PATHCONV=1.`,
    );
  }
  const apiBase = env.VITE_API_BASE;
  if (apiBase && !/^(\/|https?:\/\/)/.test(apiBase)) {
    // The same rewrite here builds a site where every API call fails.
    throw new Error(
      `VITE_API_BASE must start with a slash or http, got "${apiBase}". In Git Bash, run with MSYS_NO_PATHCONV=1.`,
    );
  }
  const config: ViteUserConfig = {
    base,
    plugins: [react()],
    server: {
      proxy: { '/api': env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000' },
    },
    build: { target: 'es2022', sourcemap: false, reportCompressedSize: false },
    test: {
      environment: 'node',
      include: ['src/**/*.test.ts'],
      pool: 'forks',
      maxWorkers: 1,
    },
  };
  return config;
});
