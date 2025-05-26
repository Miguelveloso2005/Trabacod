from sqlalchemy import Column, Integer, String, Float
from backend.database import Base  # Ajusta la ruta si estás fuera de 'backend'

class Sucursal(Base):
    __tablename__ = "sucursales"

    id = Column(Integer, primary_key=True, index=True)
    sucursal = Column(String, nullable=False, unique=True)
    cantidad = Column(Integer, default=0, nullable=False)
    precio = Column(Float, default=0.0, nullable=False)
