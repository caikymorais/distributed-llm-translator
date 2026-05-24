import os
import json
from pathlib import Path
from typing import List, Dict

BASE_DIR = Path(__file__).resolve().parents[2]  # raiz do projeto
INPUT_PATH = BASE_DIR / "data" / "input" / "corpus_en.txt"
OUTPUT_PATH = BASE_DIR / "data" / "output" / "chunks_local.json"


def carregar_texto() -> str:
    """Lê o corpus de entrada como texto único."""
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Arquivo de entrada não encontrado: {INPUT_PATH}")
    with INPUT_PATH.open("r", encoding="utf-8") as f:
        return f.read()


def dividir_em_paragrafos(texto: str) -> List[str]:
    """
    Divide o texto em parágrafos, removendo linhas vazias.
    Aqui usamos uma divisão simples por quebras de linha dupla.
    """
    blocos = [p.strip() for p in texto.split("\n\n") if p.strip()]
    return blocos


def agrupar_em_chunks(paragrafos: List[str], max_chars: int = 600) -> List[Dict]:
    """
    Agrupa parágrafos em chunks de até max_chars caracteres,
    tentando não cortar parágrafo no meio.
    """
    chunks: List[Dict] = []
    atual: List[str] = []
    atual_len = 0
    chunk_id = 0

    for p in paragrafos:
        # se o parágrafo sozinho já é maior que max_chars, corta bruto
        if len(p) > max_chars:
            if atual:
                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "text": "\n\n".join(atual),
                    }
                )
                chunk_id += 1
                atual = []
                atual_len = 0

            texto = p
            while len(texto) > max_chars:
                pedaço = texto[:max_chars]
                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "text": pedaço,
                    }
                )
                chunk_id += 1
                texto = texto[max_chars:]
            if texto.strip():
                atual = [texto.strip()]
                atual_len = len(texto.strip())
        else:
            # se cabe no chunk atual, adiciona
            if atual_len + len(p) + 2 <= max_chars:
                atual.append(p)
                atual_len += len(p) + 2
            else:
                # fecha chunk atual e começa outro
                if atual:
                    chunks.append(
                        {
                            "chunk_id": chunk_id,
                            "text": "\n\n".join(atual),
                        }
                    )
                    chunk_id += 1
                atual = [p]
                atual_len = len(p)

    if atual:
        chunks.append(
            {
                "chunk_id": chunk_id,
                "text": "\n\n".join(atual),
            }
        )

    # adiciona metadados de documento
    total = len(chunks)
    for c in chunks:
        c["document_id"] = "doc_local_001"
        c["total_chunks"] = total

    return chunks


def salvar_chunks(chunks: List[Dict]) -> None:
    """Salva os chunks em um JSON local (simulação antes de usar SQS)."""
    os.makedirs(OUTPUT_PATH.parent, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    print(f"Chunks salvos em: {OUTPUT_PATH}")
    print(f"Total de chunks: {len(chunks)}")


def main():
    print(f"Lendo texto de: {INPUT_PATH}")
    texto = carregar_texto()
    paragrafos = dividir_em_paragrafos(texto)
    print(f"Parágrafos encontrados: {len(paragrafos)}")

    chunks = agrupar_em_chunks(paragrafos, max_chars=400)
    salvar_chunks(chunks)


if __name__ == "__main__":
    main()