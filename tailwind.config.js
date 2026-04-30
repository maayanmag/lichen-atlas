/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,ts,tsx,md,mdx}'],
  theme: {
    extend: {
      colors: {
        // Lichen palette — derived from observed taxa on Templer stones
        // Each genus has ONE canonical color used everywhere in the UI.
        lichen: {
          caloplaca: '#E07A2E',     // bright orange-red (placodioid rosette)
          aspicilia: '#9DA67E',     // pale grey-green
          verrucaria: '#3A3A3A',    // charcoal (perithecial dots)
          candelariella: '#D9C04A', // egg-yolk yellow
          lecanora: '#C5C2B5',      // off-white grey
          xanthoria: '#E8B547',     // gold-orange
          unknown: '#6E6E6E',       // muted grey
        },
        // App chrome — quiet dark slate with warm bone for light surfaces
        bone: {
          50:  '#FAF8F3',
          100: '#F4F1EB',
          200: '#E9E4D9',
          300: '#D2CABC',
        },
        slate: {
          850: '#0F1115',  // deep page background
          800: '#171A20',  // panel background
          750: '#1F232B',  // elevated surface
          700: '#2A2F38',  // subtle borders
          600: '#444B57',  // muted text
        },
        ember: '#E07A2E',  // semantic = the project's primary accent (Caloplaca)
      },
      fontFamily: {
        // Body / inscription
        serif: ['"Newsreader"', '"EB Garamond"', 'Georgia', 'serif'],
        // UI / chrome
        sans: ['"Inter Tight"', '"Inter"', 'system-ui', 'sans-serif'],
        // Hebrew text
        hebrew: ['"Frank Ruhl Libre"', '"David Libre"', 'serif'],
        // German Fraktur — used very sparingly for original inscriptions
        fraktur: ['"UnifrakturMaguntia"', '"Newsreader"', 'serif'],
      },
      maxWidth: {
        'page': '1440px',
      },
      boxShadow: {
        'panel': '0 1px 0 rgba(255,255,255,0.04), 0 24px 48px -24px rgba(0,0,0,0.7)',
        'soft':  '0 0 0 1px rgba(255,255,255,0.04), 0 8px 24px -16px rgba(0,0,0,0.5)',
      },
      backgroundImage: {
        'grain': "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3CfeColorMatrix values='0 0 0 0 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0.04 0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
      },
    },
  },
  plugins: [],
};
