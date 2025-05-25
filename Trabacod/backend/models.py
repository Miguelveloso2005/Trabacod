from sqlalchemy import Column, Integer, String
from .database import Base

class Sucursal(Base):
    __tablename__ = "sucursales"

    id = Column(Integer, primary_key=True, index=True)
    sucursal = Column(String, nullable=False)
    cantidad = Column(Integer, default=0)
    precio = Column(Integer, default=0)
