from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
import asyncio
import pathlib
import base64

app = FastAPI()
Base = declarative_base()
engine = create_engine("sqlite:///backend/db.sqlite", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

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

Base.metadata.create_all(bind=engine)

# Autenticación básica
def admin_auth(request: Request):
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Basic "):
        return HTMLResponse(status_code=401, content="Unauthorized", headers={"WWW-Authenticate": "Basic"})
    decoded = base64.b64decode(auth.split(" ")[1]).decode("utf-8")
    username, password = decoded.split(":")
    if username != "admin" or password != "admin":
        return HTMLResponse(status_code=401, content="Credenciales incorrectas")
    return True

@app.get("/admin", response_class=HTMLResponse)
def admin_html(user: bool = Depends(admin_auth)):
    index_path = pathlib.Path("frontend/admin.html")
    return index_path.read_text(encoding="utf-8")

@app.get("/stocks")
def get_stocks():
    db = SessionLocal()
    try:
        sucursales = db.query(Sucursal).all()
        return [{"id": s.id, "sucursal": s.sucursal, "cantidad": s.cantidad, "precio": s.precio} for s in sucursales]
    finally:
        db.close()

@app.post("/stock/disminuir")
async def disminuir_stock(data: dict):
    db = SessionLocal()
    sucursal_id = data.get("sucursalId")
    cantidad = data.get("cantidad")
    if not isinstance(sucursal_id, int) or not isinstance(cantidad, int):
        return {"success": False, "msg": "Datos inválidos"}
    try:
        sucursal = db.query(Sucursal).filter(Sucursal.id == sucursal_id).first()
        if not sucursal:
            return {"success": False, "msg": "Sucursal no encontrada"}
        if sucursal.cantidad < cantidad:
            return {"success": False, "msg": "Stock insuficiente"}
        sucursal.cantidad -= cantidad
        db.add(Disminucion(sucursal=sucursal.sucursal, cantidad=cantidad))
        db.commit()
        if sucursal.cantidad == 0:
            await broadcast_sse(f"Stock Bajo en {sucursal.sucursal}")
        return {"success": True}
    except SQLAlchemyError as e:
        db.rollback()
        return {"success": False, "msg": str(e)}
    finally:
        db.close()

@app.post("/sucursal")
def agregar_sucursal(data: dict):
    db = SessionLocal()
    try:
        nueva = Sucursal(
            sucursal=data["sucursal"],
            cantidad=int(data["cantidad"]),
            precio=float(data["precio"])
        )
        db.add(nueva)
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "msg": str(e)}
    finally:
        db.close()

@app.put("/sucursal/{id}")
def actualizar_precio(id: int, data: dict):
    db = SessionLocal()
    try:
        suc = db.query(Sucursal).filter(Sucursal.id == id).first()
        if not suc:
            return {"success": False, "msg": "No encontrada"}
        suc.precio = float(data["precio"])
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "msg": str(e)}
    finally:
        db.close()

@app.delete("/sucursal/{id}")
def eliminar_sucursal(id: int):
    db = SessionLocal()
    try:
        suc = db.query(Sucursal).filter(Sucursal.id == id).first()
        if suc:
            db.delete(suc)
            db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "msg": str(e)}
    finally:
        db.close()

@app.get("/historial")
def historial():
    db = SessionLocal()
    try:
        h = db.query(Disminucion).order_by(Disminucion.fecha.desc()).all()
        return [{"sucursal": x.sucursal, "cantidad": x.cantidad, "fecha": x.fecha.strftime("%Y-%m-%d %H:%M:%S")} for x in h]
    finally:
        db.close()

# SSE
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
