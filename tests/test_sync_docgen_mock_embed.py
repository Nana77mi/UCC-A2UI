from __future__ import annotations

from pathlib import Path

from ucc_a2ui.docs import generate_docs
from ucc_a2ui.embed import build_embedder
from ucc_a2ui.embed.chunker import chunk_documents_with_sources
from ucc_a2ui.embed.index_faiss import IndexedChunk, build_faiss_index, save_faiss_index
from ucc_a2ui.embed.search import search_index
from ucc_a2ui.library import LibrarySourceConfig, build_whitelist, load_library_sources


def _write_json(component_path: Path, params_path: Path) -> None:
    component_path.write_text(
        """
{
  "components": [
    {
      "ComponentGroup": "基础",
      "ComponentName_CN": "列表",
      "ComponentName_EN": "List",
      "KeyParams": ["items"],
      "MaterialLike_DefaultColors": "primary=#000000"
    }
  ]
}
""",
        encoding="utf-8",
    )
    params_path.write_text(
        """
{
  "params": [
    {
      "ComponentName": "List",
      "ParamCategory": "Data",
      "ParamName": "items",
      "ValueType": "array",
      "EnumValues": "",
      "DefaultValue": "",
      "Required": "yes",
      "Notes": ""
    }
  ]
}
""",
        encoding="utf-8",
    )


def test_sync_docgen_and_search(tmp_path: Path) -> None:
    component_path = tmp_path / "components.json"
    params_path = tmp_path / "params.json"
    _write_json(component_path, params_path)

    sources = LibrarySourceConfig(
        component_path=str(component_path),
        params_path=str(params_path),
        source_format="json",
    )
    components, params = load_library_sources(sources)
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
