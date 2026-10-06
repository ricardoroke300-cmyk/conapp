"""Contrato exato do guia, validado antes de desenhar o PDF."""
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Texto = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=12000)]

class Registro(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

class Evento(Registro):
    evento: Texto
    data: Texto

class Fase(Registro):
    fase: Texto
    nome: Texto
    tipo: Texto
    detalhe: Texto

class Materia(Registro):
    nome: Texto
    peso: Texto
    questoes: Texto
    topicos: Texto

class Guia(Registro):
    titulo: Texto
    orgao: Texto
    banca: Texto
    vagas: Texto
    remuneracao: Texto
    escolaridade: Texto
    carga_horaria: Texto
    cronograma: list[Evento] = Field(max_length=100)
    fases: list[Fase] = Field(max_length=100)
    materias: list[Materia] = Field(max_length=200)
