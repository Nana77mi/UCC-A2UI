from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from ucc_a2ui.docs import generate_docs
from ucc_a2ui.embed import build_embedder
from ucc_a2ui.embed.chunker import chunk_documents_with_sources
from ucc_a2ui.embed.index_faiss import IndexedChunk, build_faiss_index, save_faiss_index
from ucc_a2ui.embed.search import search_index
from ucc_a2ui.library import build_whitelist, load_component_library, load_params_library


def _write_excel(component_path: Path, params_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(
        [
            "ComponentGroup",
            "ComponentName_CN",
            "ComponentName_EN",
            "KeyParams",
            "MaterialLike_DefaultColors",
        ]
    )
    ws.append(["基础", "列表", "List", "items", "primary=#000000"])
    wb.save(component_path)

    wb = Workbook()
    ws = wb.active
    ws.append(
        [
            "ComponentGroup",
            "ComponentName",
            "ParamCategory",
            "ParamName",
            "ValueType",
            "EnumValues",
            "DefaultValue",
            "Required",
            "Notes",
        ]
    )
    ws.append(["基础", "List", "Data", "items", "array", "", "", "yes", ""])
    wb.save(params_path)


def test_sync_docgen_and_search(tmp_path: Path) -> None:
    component_path = tmp_path / "components.xlsx"
    params_path = tmp_path / "params.xlsx"
    _write_excel(component_path, params_path)

    components = load_component_library(component_path)
    params = load_params_library(params_path)
    whitelist = build_whitelist(components, params)

    docs_dir = tmp_path / "docs"
    docs = generate_docs(docs_dir, whitelist)
    assert docs

    documents = [(Path(doc).read_text(encoding="utf-8"), str(doc)) for doc in docs]
    chunk_pairs = chunk_documents_with_sources(documents, chunk_size=200, chunk_overlap=20)
    chunks = [chunk for chunk, _ in chunk_pairs]
    embedder = build_embedder({"mode": "mock"})
    vectors = embedder.embed(chunks).vectors
    indexed_chunks = [IndexedChunk(text=chunk, source=source) for chunk, source in chunk_pairs]
    index = build_faiss_index(vectors, indexed_chunks)
    index_dir = tmp_path / "index"
    save_faiss_index(index_dir, index)

    results = search_index(str(index_dir), "列表", embedder, top_k=3)
    assert results
