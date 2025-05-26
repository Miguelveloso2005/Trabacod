from fastapi import FastAPI, Request, Depends, HTTPException, Form, Response, status
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Column, Integer, String, Float, DateTime, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
import asyncio
import pathlib
import httpx
from pydantic import BaseModel

app = FastAPI()
Base = declarative_base()
DATABASE_URL = "sqlite+aiosqlite:///./backend/db.sqlite"

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Dependency para DB
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# Modelos
class Sucursal(Base):
    __tablename__ = "sucursales"
    id = Column(Integer, primary_key=True, index=True)
    sucursal = Column(String, unique=True)
    cantidad = Column(Integer)
    precio = Column(Float)

class Disminucion(Base):
    __tablename__ = "disminuciones"
    id = Column(Integer, primary_key=True, index=True)
    sucursal = Column(String)
    cantidad = Column(Integer)
    fecha = Column(DateTime, default=datetime.utcnow)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# --- Autenticación por sesión con cookie ---
SESSION_COOKIE = "session_token"
VALID_USERNAME = "admin"
VALID_PASSWORD = "admin"

def is_logged_in(request: Request):
    session_token = request.cookies.get(SESSION_COOKIE)
    # En este ejemplo simple, el token será 'admin-session'
    return session_token == "admin-session"

# Middleware para proteger rutas / y /admin
async def require_login(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=302)

# Ruta login GET (muestra formulario)
@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    # Si ya está logueado, redirige a /
    if is_logged_in(request):
        return RedirectResponse("/", status_code=302)
    login_path = pathlib.Path("frontend/login.html")
    return login_path.read_text(encoding="utf-8")

# Ruta login POST (procesa formulario)
@app.post("/login")
async def login_post(response: Response, username: str = Form(...), password: str = Form(...)):
    if username == VALID_USERNAME and password == VALID_PASSWORD:
        response = RedirectResponse(url="/", status_code=302)
        # Simple token de sesión
        response.set_cookie(key=SESSION_COOKIE, value="admin-session", httponly=True)
        return response
    else:
        return HTMLResponse(
            content="<h3>Credenciales incorrectas. <a href='/login'>Intentar de nuevo</a></h3>",
            status_code=401
        )

# Ruta logout para borrar cookie
@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE)
    return response

# Ruta principal / index protegida
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=302)
    index_path = pathlib.Path("frontend/index.html")
    return index_path.read_text(encoding="utf-8")

# Ruta admin protegida
@app.get("/admin", response_class=HTMLResponse)
async def admin_html(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=302)
    admin_path = pathlib.Path("frontend/admin.html")
    return admin_path.read_text(encoding="utf-8")

# --- Resto de rutas ---

@app.get("/stocks")
async def get_stocks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Sucursal))
    sucursales = result.scalars().all()
    return [{"id": s.id, "sucursal": s.sucursal, "cantidad": s.cantidad, "precio": s.precio} for s in sucursales]

@app.post("/stock/disminuir")
async def disminuir_stock(data: dict, db: AsyncSession = Depends(get_db)):
    sucursal_id = data.get("sucursalId")
    cantidad = data.get("cantidad")
    if not isinstance(sucursal_id, int) or not isinstance(cantidad, int):
        return {"success": False, "msg": "Datos inválidos"}
    try:
        result = await db.execute(select(Sucursal).where(Sucursal.id == sucursal_id))
        sucursal = result.scalar_one_or_none()
        if not sucursal:
            return {"success": False, "msg": "Sucursal no encontrada"}
        if sucursal.cantidad < cantidad:
            return {"success": False, "msg": "Stock insuficiente"}
        sucursal.cantidad -= cantidad
        disminucion = Disminucion(sucursal=sucursal.sucursal, cantidad=cantidad)
        db.add(disminucion)
        await db.commit()
        await db.refresh(sucursal)
        if sucursal.cantidad == 0:
            await broadcast_sse(f"Stock Bajo en {sucursal.sucursal}")
        return {"success": True}
    except SQLAlchemyError as e:
        await db.rollback()
        return {"success": False, "msg": str(e)}

@app.post("/sucursal")
async def agregar_sucursal(data: dict, db: AsyncSession = Depends(get_db)):
    try:
        nueva = Sucursal(
            sucursal=data["sucursal"],
            cantidad=int(data["cantidad"]),
            precio=float(data["precio"])
        )
        db.add(nueva)
        await db.commit()
        return {"success": True}
    except Exception as e:
        await db.rollback()
        return {"success": False, "msg": str(e)}

@app.put("/sucursal/{id}")
async def actualizar_precio(id: int, data: dict, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(Sucursal).where(Sucursal.id == id))
        suc = result.scalar_one_or_none()
        if not suc:
            return {"success": False, "msg": "No encontrada"}
        suc.precio = float(data["precio"])
        await db.commit()
        return {"success": True}
    except Exception as e:
        await db.rollback()
        return {"success": False, "msg": str(e)}

@app.delete("/sucursal/{id}")
async def eliminar_sucursal(id: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(Sucursal).where(Sucursal.id == id))
        suc = result.scalar_one_or_none()
        if suc:
            await db.delete(suc)
            await db.commit()
        return {"success": True}
    except Exception as e:
        await db.rollback()
        return {"success": False, "msg": str(e)}

@app.get("/historial")
async def historial(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Disminucion).order_by(Disminucion.fecha.desc()))
    h = result.scalars().all()
    return [{"sucursal": x.sucursal, "cantidad": x.cantidad, "fecha": x.fecha.strftime("%Y-%m-%d %H:%M:%S")} for x in h]

clients = []

async def event_generator():
    queue = asyncio.Queue()
    clients.append(queue)
    try:
        while True:
            data = await queue.get()
            yield f"data: {data}\n\n"
    finally:
        clients.remove(queue)

async def broadcast_sse(message: str):
    for client in clients:
        await client.put(message)

@app.get("/sse")
async def sse_endpoint():
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Modelo para recibir monto en /convert/usd
class ConversionRequest(BaseModel):
    amount: float

@app.post("/convert/usd")
async def convertir_a_usd(data: ConversionRequest):
    monto = data.amount
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://mindicador.cl/api/dolar")
            response.raise_for_status()
            data = response.json()
            valor_usd = data["serie"][0]["valor"]
            convertido = round(monto / valor_usd, 2)
            return {"clp": monto, "usd": convertido, "valor_dolar": valor_usd}
    except Exception as e:
        return {"error": str(e)}
