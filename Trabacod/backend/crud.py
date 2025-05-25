from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from .models import Sucursal

async def get_all_sucursales(db: AsyncSession):
    result = await db.execute(select(Sucursal))
    return result.scalars().all()

async def get_sucursal_by_id(db: AsyncSession, sucursal_id: int):
    result = await db.execute(select(Sucursal).where(Sucursal.id == sucursal_id))
    return result.scalar_one_or_none()

async def disminuir_stock(db: AsyncSession, sucursal_id: int, cantidad: int):
    sucursal = await get_sucursal_by_id(db, sucursal_id)
    if not sucursal or sucursal.cantidad < cantidad:
        return None
    sucursal.cantidad -= cantidad
    await db.commit()
    await db.refresh(sucursal)
    return sucursal
