from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import models  # noqa: F401  (registra as tabelas)
from app.database import Base, engine
from app.routers import comprovantes, paginas, ponto, relatorios, usuarios

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Ponto Eletrônico Clínica")
app.mount("/static", StaticFiles(directory=paginas.STATIC_DIR), name="static")

for router in (paginas.router, ponto.router, comprovantes.router, usuarios.router, relatorios.router):
    app.include_router(router)
