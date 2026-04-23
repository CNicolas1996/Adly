import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.api.limiter import limiter
from src.api.routes import config, analyses, chat
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Adly API", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
origins = [origin.strip() for origin in cors_origins_str.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SlowAPI Middleware
app.add_middleware(SlowAPIMiddleware)

# Include routers
app.include_router(config.router)
app.include_router(analyses.router)
app.include_router(chat.router)

@app.get("/")
async def root(request: Request):
    return {"message": "Adly API is running"}

