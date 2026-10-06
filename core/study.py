from datetime import date, timedelta
from difflib import SequenceMatcher
import random
import re

def recommend_count(value):
    # Only unambiguous question counts; never infer from weights or totals.
    match=re.fullmatch(r"\s*(\d+)\s*(?:questões|questao|questão|questions)?\s*",str(value),re.I)
    return int(match.group(1)) if match else None

def build_plan(subjects, available, exam_date=None, accuracy=None, start=None):
    start=start or date.today();accuracy=accuracy or {}
    end=min(exam_date or (start+timedelta(days=13)),start+timedelta(days=89))
    if end<start:return []
    spent={s:0 for s in subjects};weights={s:1+(1-accuracy.get(s,0.5)) for s in subjects}
    result=[];day=start
    while day<=end:
        left=int(available[day.weekday()])
        if not 0<=left<=720:raise ValueError("Disponibilidade inválida")
        while left and subjects:
            s=min(subjects,key=lambda x:spent[x]/weights[x]);minutes=min(left,50)
            result.append({"date":day.isoformat(),"subject":s,"minutes":minutes})
            spent[s]+=minutes;left-=minutes
        day+=timedelta(days=1)
    return result

def distinct_questions(existing,generated):
    accepted=[]
    normalize=lambda t:re.sub(r"\W+"," ",t.lower()).strip()
    corpus=[normalize(q["statement"]) for q in existing]
    for q in generated:
        statement=normalize(q["statement"])
        if len(set(q["alternatives"]))!=4:continue
        if any(SequenceMatcher(None,statement,t).ratio()>0.90 for t in corpus):continue
        accepted.append(q);corpus.append(statement)
    return accepted

def select_simulation(bank,distribution,level,rng=None):
    rng=rng or random.Random();result=[];reused=False
    if not distribution or sum(distribution.values())<=0:raise ValueError("Escolha ao menos uma questão.")
    for subject,count in distribution.items():
        if not isinstance(count,int) or count<0:raise ValueError("Quantidade inválida")
        if not count:continue
        pool=[q for q in bank if q["subject"]==subject and q["level"]==level]
        if not pool:raise ValueError(f"Não há questões {level.lower()} para {subject}. Gere um lote primeiro.")
        reused|=count>len(pool)
        # Independent copies fix the question version/alternatives for history and PDF.
        import copy
        for offset in range(0,count,len(pool)):
            ordered=rng.sample(pool,len(pool))
            result.extend(copy.deepcopy(ordered[:min(len(pool),count-offset)]))
    rng.shuffle(result)
    return result,reused

def score_simulation(questions,answers):
    if len(questions)!=len(answers):raise ValueError("Respostas incompatíveis")
    correct=sum(a==q["answer"] for q,a in zip(questions,answers) if a is not None)
    blank=sum(a is None for a in answers)
    return {"correct":correct,"wrong":len(questions)-correct-blank,"blank":blank,"total":len(questions),"percentage":round(100*correct/len(questions),2) if questions else 0}

def validate_grade(grade,rubric):
    expected={c["name"]:float(c["maximum"]) for c in rubric}
    if len(expected)!=len(rubric) or len(grade["criteria"])!=len(rubric):raise ValueError("Rubrica divergente")
    seen=set()
    for c in grade["criteria"]:
        if c["name"] in seen or c["name"] not in expected:raise ValueError("Critério divergente")
        if c["maximum"]!=expected[c["name"]] or not 0<=c["score"]<=c["maximum"]:raise ValueError("Nota fora da escala")
        seen.add(c["name"])
    return sum(c["score"] for c in grade["criteria"]),sum(expected.values())
