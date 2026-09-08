// TEKIS — Configuration Tailwind partagée
// Les couleurs pointent vers les variables CSS définies dans assets/css/variables.css
// => un seul jeu de classes Tailwind (bg-surface, text-text, ...) qui réagit
//    automatiquement au thème clair/sombre, sans duplication de config par page.
window.tailwind = window.tailwind || {};
tailwind.config = {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: 'var(--color-bg)',
        surface: 'var(--color-surface)',
        'surface-raised': 'var(--color-surface-raised)',
        'surface-panel': 'var(--color-surface-panel)',
        container: 'var(--color-container)',
        'container-high': 'var(--color-container-high)',
        'container-highest': 'var(--color-container-highest)',
        border: 'var(--color-border)',
        'border-strong': 'var(--color-border-strong)',
        text: 'var(--color-text)',
        'text-muted': 'var(--color-text-muted)',
        'text-subtle': 'var(--color-text-subtle)',
        primary: 'var(--color-primary)',
        'on-primary': 'var(--color-on-primary)',
        'primary-container': 'var(--color-primary-container)',
        'on-primary-container': 'var(--color-on-primary-container)',
        secondary: 'var(--color-secondary)',
        'on-secondary': 'var(--color-on-secondary)',
        'secondary-container': 'var(--color-secondary-container)',
        'on-secondary-container': 'var(--color-on-secondary-container)',
        error: 'var(--color-error)',
        'on-error': 'var(--color-on-error)',
        'error-container': 'var(--color-error-container)',
        'on-error-container': 'var(--color-on-error-container)',
        success: 'var(--color-success)'
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace']
      },
      borderRadius: {
        DEFAULT: '0.125rem',
        lg: '0.25rem',
        xl: '0.5rem',
        full: '0.75rem'
      },
      spacing: {
        'margin-mobile': '1rem',
        'margin-page': '2rem',
        gutter: '1.5rem',
        'sidebar-width': '260px',
        'max-width-chat': '800px',
        'stack-xs': '0.25rem',
        'stack-sm': '0.5rem',
        'stack-md': '1rem'
      }
    }
  }
};
