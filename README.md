# SumoImperium

Frontend:

```bash
npm install
npm run dev
```

The Vite app uses `http://localhost:8000` for the API by default. Override it with:

```bash
VITE_API_BASE=http://localhost:8000 npm run dev
```

Backend:

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Profile verification uploads use Cloudinary. Set this in `backend/.env`:

```bash
CLOUDINARY_URL=cloudinary://your-api-key:your-api-secret@your-cloud-name
```
