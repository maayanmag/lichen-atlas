// @ts-check
import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import react from '@astrojs/react';

export default defineConfig({
  site: 'https://maayanmag.github.io',
  base: '/lichen-atlas',
  integrations: [
    tailwind({ applyBaseStyles: false }),
    react(),
  ],
  build: {
    assets: '_assets',
  },
  image: {
    service: { entrypoint: 'astro/assets/services/sharp' },
  },
});
