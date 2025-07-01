import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import asyncio
from concurrent import futures

import grpc
from .grpc_stubs import sucursal_pb2_grpc, sucursal_pb2

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from .main import Sucursal, Base
  # Importamos el modelo SQLAlchemy desde tu main.py

DATABASE_URL = "sqlite+aiosqlite:///./backend/db.sqlite"
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# Servicio implementado
class SucursalService(sucursal_pb2_grpc.ServicioSucursalServicer):
    async def ObtenerSucursales(self, request, context):
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Sucursal))
            sucursales = result.scalars().all()

            respuesta = sucursal_pb2.ListaSucursales()
            for s in sucursales:
                sucursal_msg = sucursal_pb2.Sucursal(
                    id=s.id,
                    nombre=s.sucursal,
                    cantidad=s.cantidad,
                    precio=s.precio
                )
                respuesta.sucursales.append(sucursal_msg)
            return respuesta

    async def AgregarSucursal(self, request, context):
        async with AsyncSessionLocal() as session:
            nueva = Sucursal(
                sucursal=request.nombre,
                cantidad=request.cantidad,
                precio=request.precio
            )
            try:
                session.add(nueva)
                await session.commit()
                return sucursal_pb2.Resultado(ok=True, mensaje="Sucursal agregada correctamente.")
            except Exception as e:
                await session.rollback()
                return sucursal_pb2.Resultado(ok=False, mensaje=str(e))


# Servidor gRPC asincrónico
async def serve():
    server = grpc.aio.server()
    sucursal_pb2_grpc.add_ServicioSucursalServicer_to_server(SucursalService(), server)
    server.add_insecure_port('[::]:50051')
    print("🟢 Servidor gRPC corriendo en el puerto 50051...")
    await server.start()
    await server.wait_for_termination()

if __name__ == '__main__':
    asyncio.run(serve())
