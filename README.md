# People Search — Static Homepage Demo

This is a simple, modern static homepage that lets users search for people (client-side only). It demonstrates a clean UI, suggestions, and responsive layout.

Files:

- `index.html` — main page
- `styles.css` — styling
- `app.js` — small client-side search and UI logic

Run locally (no build step):

Option A — Python (exists on macOS):

```bash
# serve on port 8000
cd people-search-homepage
python3 -m http.server 8000
# open http://localhost:8000 in your browser
```

Option B — Node (npx):

```bash
cd people-search-homepage
npx serve -l 3000
# open http://localhost:3000
```

What next?

- Hook the search to your backend API.
- Add pagination, filtering, or sorting.
- Replace static PEOPLE list in `app.js` with live data fetches.

