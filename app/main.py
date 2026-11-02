from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import models  # noqa: F401  (registra as tabelas)
from app.database import Base, engine
from app.migracoes import migrar_esquema
from app.routers import admin, auth, comprovantes, extratos, paginas, ponto, usuarios

migrar_esquema(engine)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Ponto Eletrônico Clínica")
app.mount("/static", StaticFiles(directory=paginas.STATIC_DIR), name="static")

for router in (
    paginas.router, ponto.router, comprovantes.router, auth.router,
    extratos.router, admin.router, usuarios.router,
):
    app.include_router(router)
