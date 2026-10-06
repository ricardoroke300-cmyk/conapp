from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from core.guide_schema import Guia

Text = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1,max_length=12000)]
class Model(BaseModel):
    model_config=ConfigDict(extra="forbid",strict=True)

class Criterion(Model):
    name: Text
    maximum: float = Field(gt=0,le=1000)
    description: Text

class Edict(Model):
    guia: Guia
    exam_date: str = Field(description="Data da prova YYYY-MM-DD ou string vazia se indefinida/ambígua")
    essay_criteria: list[Criterion] = Field(description="Somente critérios e máximos numéricos expressos no edital; vazio se ausentes",max_length=20)

    @model_validator(mode='after')
    def validate_consistency(self):
        if self.exam_date:
            from datetime import date
            date.fromisoformat(self.exam_date)
        names=[m.nome for m in self.guia.materias]
        if len(set(names))!=len(names):raise ValueError('Disciplinas duplicadas')
        names=[c.name for c in self.essay_criteria]
        if len(set(names))!=len(names):raise ValueError('Critérios duplicados')
        return self

class Question(Model):
    subject: Text
    topic: Text
    level: Literal["Fácil","Médio","Difícil"]
    statement: Text
    alternatives: list[Text] = Field(min_length=4,max_length=4)
    answer: int = Field(ge=0,le=3)
    explanation: Text

class QuestionBatch(Model):
    questions: list[Question] = Field(min_length=1,max_length=10)

class Check(Model):
    index: int = Field(ge=0)
    answer: int = Field(ge=0,le=3)
    valid: bool
    reason: Text
class Verification(Model):
    items: list[Check] = Field(max_length=10)

class Section(Model):
    title: Text
    theory: Text
    example: Text
    pitfall: Text
    steps: list[Text] = Field(min_length=2,max_length=5,description="Etapas ou conceitos curtos para diagrama vetorial")
class Booklet(Model):
    title: Text
    subject: Text
    sections: list[Section] = Field(min_length=1,max_length=30)
    references: list[Text] = Field(description="Apenas referências existentes no contexto, não inventar URLs",max_length=20)

class BoardReport(Model):
    scope: Text
    evidence: list[Text] = Field(max_length=30)
    style: list[Text] = Field(max_length=30)
    pitfalls: list[Text] = Field(max_length=30)
    priorities: list[Text] = Field(max_length=30)
    limitations: Text

class Theme(Model):
    title: Text
    prompt: Text
    instructions: Text

class Transcription(Model):
    text: Text
    readable: bool
    uncertain: list[Text] = Field(max_length=100)

class CriterionScore(Model):
    name: Text
    score: float = Field(ge=0,le=1000)
    maximum: float = Field(gt=0,le=1000)
    comment: Text
class EssayGrade(Model):
    criteria: list[CriterionScore] = Field(min_length=1,max_length=20)
    feedback: Text
    improvements: list[Text] = Field(max_length=30)
