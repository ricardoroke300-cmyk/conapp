from dataclasses import dataclass
from io import BytesIO
from pypdf import PdfReader

MAX_BYTES = 20 * 1024 * 1024
MAX_PAGES = 600
MAX_CHARS = 900000

class DocumentError(ValueError):
    pass

@dataclass
class Document:
    text: str
    pages: int
    pages_without_text: list[int]

def extract_pdf(data: bytes) -> Document:
    if not data or len(data) > MAX_BYTES:
        raise DocumentError("Envie um PDF de até 20 MB.")
    if not data.startswith(b"%PDF-"):
        raise DocumentError("O arquivo enviado não possui um cabeçalho PDF válido.")
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted and reader.decrypt("") == 0:
            raise DocumentError("O PDF está protegido por senha. Envie uma cópia desbloqueada.")
        if not reader.pages or len(reader.pages) > MAX_PAGES:
            raise DocumentError("O PDF deve ter entre 1 e 600 páginas.")
        parts, missing, size = [], [], 0
        for index, page in enumerate(reader.pages, 1):
            content = (page.extract_text() or "").strip()
            if not content:
                missing.append(index)
            part = f"\n[PÁGINA {index}]\n{content}\n"
            size += len(part)
            if size > MAX_CHARS:
                raise DocumentError("O texto excede a capacidade desta versão (900 mil caracteres). Nenhum trecho foi cortado. Separe o edital e os anexos em arquivos menores.")
            parts.append(part)
        if len(missing) == len(reader.pages):
            raise DocumentError("Este PDF não contém texto extraível. Ele pode ser uma digitalização. Faça OCR no documento antes de enviá-lo; esta versão não lê imagens.")
        return Document("".join(parts), len(reader.pages), missing)
    except DocumentError:
        raise
    except Exception as exc:
        raise DocumentError("Não foi possível ler o PDF. Verifique se está completo e não está corrompido.") from exc
