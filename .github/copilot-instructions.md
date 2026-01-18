# Copilot Instructions — People Search Homepage

## Project Overview

Static single-page people search demo with **no build step or backend**. Pure HTML/CSS/JS served directly from files.

## Architecture

```
index.html   → Entry point, semantic HTML structure
styles.css   → Dark theme with CSS custom properties (--bg, --accent, etc.)
app.js       → Client-side search logic, renders cards dynamically
```

**Data Flow:** Static `PEOPLE` array in `app.js` → filtered by `search()` → rendered via `renderCard()` → inserted into `#results`.

## Key Patterns

### CSS Variables (styles.css)
All colors use CSS custom properties defined in `:root`. When adding colors, extend this system:
```css
:root {
  --bg: #0f1724;
  --accent: #60a5fa;
  --muted: #9aa6b2;
}
```

### DOM Helpers (app.js)
Use the existing `q()` selector helper instead of `document.querySelector`:
```javascript
const q = (sel) => document.querySelector(sel);
const input = q('#search');
```

### Card Rendering
New UI cards should follow the `renderCard()` pattern—create element, set `className`, use template literal for `innerHTML`.

## Running Locally

```bash
# Python (macOS built-in)
python3 -m http.server 8000

# Node alternative
npx serve -l 3000
```

No install step required.

## Extension Points

When connecting a real backend:
1. Replace the static `PEOPLE` array with `fetch()` calls
2. Keep `search()` signature intact—accepts query string, returns array of person objects
3. Person object shape: `{ name: string, role: string, location: string }`

## Conventions

- Accessibility: Use `aria-*` attributes and semantic HTML (see `role="search"`, `aria-live="polite"`)
- Mobile-first: Responsive breakpoint at 600px in styles.css
- No frameworks or dependencies—keep it vanilla JS/CSS
