from pathlib import Path
from typing import List, Dict

from src.config import BASE_DIR, MAX_CHARS_PER_CHUNK, DOCUMENT_ID

INPUT_PATH = BASE_DIR / "data" / "input" / "corpus_en.txt"


def carregar_texto(input_path: Path = INPUT_PATH) -> str:
    """Lê o corpus de entrada como texto único."""
    if not input_path.exists():
        raise FileNotFoundError(f"Arquivo de entrada não encontrado: {input_path}")
    with input_path.open("r", encoding="utf-8") as f:
        return f.read()


def dividir_em_paragrafos(texto: str) -> List[str]:
    """Divide o texto em parágrafos, removendo linhas vazias."""
    return [p.strip() for p in texto.split("\n\n") if p.strip()]


def agrupar_em_chunks(
    paragrafos: List[str],
    max_chars: int = MAX_CHARS_PER_CHUNK,
    document_id: str = DOCUMENT_ID,
) -> List[Dict]:
    """Agrupa parágrafos em chunks sem depender de arquivos locais de saída."""
    chunks: List[Dict] = []
    atual: List[str] = []
    atual_len = 0
    chunk_id = 0

    for p in paragrafos:
        if len(p) > max_chars:
            if atual:
                chunks.append({"chunk_id": chunk_id, "text": "\n\n".join(atual)})
                chunk_id += 1
                atual = []
                atual_len = 0

            texto = p
            while len(texto) > max_chars:
                pedaco = texto[:max_chars]
                chunks.append({"chunk_id": chunk_id, "text": pedaco})
                chunk_id += 1
                texto = texto[max_chars:]

            if texto.strip():
                atual = [texto.strip()]
                atual_len = len(texto.strip())
        else:
            if atual_len + len(p) + 2 <= max_chars:
                atual.append(p)
                atual_len += len(p) + 2
            else:
                if atual:
                    chunks.append({"chunk_id": chunk_id, "text": "\n\n".join(atual)})
                    chunk_id += 1
                atual = [p]
                atual_len = len(p)

    if atual:
        chunks.append({"chunk_id": chunk_id, "text": "\n\n".join(atual)})

    total = len(chunks)
    for chunk in chunks:
        chunk["document_id"] = document_id
        chunk["total_chunks"] = total

    return chunks
