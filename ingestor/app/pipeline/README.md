# app/pipeline/

The RAG ingestion steps, one file each, plus the runner that ties them together.

| File | Step | In → out |
|---|---|---|
| `loader.py` | 1. Extract text | file bytes → list of `Page(number, text)` (PDF via `pypdf`; TXT/MD decoded as UTF-8) |
| `chunker.py` | 2. Split | pages → list of `Chunk(index, page, text)` |
| `embedder.py` | 3. Embed | chunk texts → vectors (Amazon Titan Text Embeddings V2, 1024 numbers each) |
| `pipeline.py` | Runner | `accept()` validates and records "pending"; `run()` does steps 1–3, stores the result, records the outcome |

## Chunking, briefly

- Chunks are about `CHUNK_SIZE` (1000) characters, small enough to be specific when searched and short enough to quote to Claude.
- Neighbouring chunks share `CHUNK_OVERLAP` (150) characters, so a sentence at a boundary is complete in at least one of them.
- Cuts go at the best natural break near the end: paragraph, then line, then sentence, then word.
- Chunks never cross pages, so every chunk knows its page number (useful for "source: page 4").

## Embeddings, briefly

An embedding is a list of numbers that captures what a text *means*. Texts with similar meaning get similar numbers,
so "roaming charges" finds a chunk about "international usage fees" even without shared words.
Titan V2 embeds one text per call, so `embed_many` runs `EMBEDDING_CONCURRENCY` (8) calls in parallel.

## Document ids

`doc_id` = hash of tenant + file name (without the upload timestamp). Uploading the same file again gets the same id,
so its chunks are overwritten instead of duplicated.

## Errors in `run()`

`run()` never raises. It always ends with status `ready` or `failed`:
- **Known problems** (unsupported type, too large, no text) are shown to the user as-is.
- **Unexpected errors** are logged in full; the user sees only a short message pointing to the ingestor logs.
