"""FastAPI HTTP API for Herb-Hermes — the 'research cockpit' backend.

Run:
    pip install fastapi uvicorn
    python -m herb_hermes.index_build          # build the KB once
    uvicorn herb_hermes.api.server:app --reload

The knowledge base is loaded once at startup (or built on demand if absent).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException, Query, Request, Body
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse, RedirectResponse, Response
    from fastapi.middleware.cors import CORSMiddleware
except Exception as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "FastAPI is required for the API layer. Install with: pip install fastapi uvicorn"
    ) from exc

from ..config import DEFAULT_CORPUS_DIR, KB_PATH
from ..discovery.hypothesis import build_hypothesis_card
from ..discovery.sourcing import trace_herb
from ..report import herb_dossier_markdown
from ..store import KnowledgeBase

app = FastAPI(
    title="Herb-Hermes API",
    version="0.2.0",
    description="本草—方剂—机制—发现 证据操作系统：本草溯源 / 方剂谱系 / 药对配伍 / 科研假设",
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

_FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


@lru_cache(maxsize=1)
def get_kb() -> KnowledgeBase:
    if KB_PATH.exists():
        return KnowledgeBase.load(KB_PATH)
    kb = KnowledgeBase.build(DEFAULT_CORPUS_DIR)
    kb.save()
    return kb


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": app.version}


@app.get("/stats")
def stats() -> dict:
    return get_kb().stats


@app.get("/herb/{name}")
def herb(name: str) -> dict:
    kb = get_kb()
    norm = kb.normalizer.normalize(name)
    entries = kb.get_entries(name)
    return {
        "query": name,
        "canonical": norm.canonical,
        "aliases": norm.aliases,
        "ambiguous": norm.ambiguous,
        "ambiguity_note": norm.note,
        "entries": [e.to_dict() for e in entries],
        "graph_neighbors": kb.graph.neighbors(norm.canonical),
    }


@app.get("/trace/{name}")
def trace(name: str, limit: int = Query(40, ge=1, le=200)) -> dict:
    res = trace_herb(get_kb(), name, max_evidence=limit)
    return res.to_dict()


@app.get("/search")
def search(q: str, limit: int = Query(10, ge=1, le=50)) -> dict:
    hits = get_kb().bm25.search(q, top_k=limit)
    return {
        "query": q,
        "results": [
            {"score": round(s, 3), "citation": p.citation, "book": p.book_title,
             "section": p.section, "snippet": p.text.strip()[:200]}
            for p, s in hits
        ],
    }


@app.get("/pairs")
def pairs(herb: Optional[str] = None, limit: int = Query(30, ge=1, le=200)) -> dict:
    kb = get_kb()
    res = kb.pairs_for(herb, top_k=limit) if herb else kb.pairs[:limit]
    return {"herb": herb, "pairs": [p.to_dict() for p in res]}


@app.get("/hypothesis")
def hypothesis(herb: str, partner: Optional[str] = None, disease: str = "骨质疏松") -> dict:
    card = build_hypothesis_card(get_kb(), herb, partner=partner, disease=disease)
    return card.to_dict()


@app.get("/graph/{name}")
def graph(name: str) -> dict:
    kb = get_kb()
    canonical = kb.normalizer.normalize(name).canonical
    return {"herb": canonical, "neighbors": kb.graph.neighbors(canonical)}


@app.get("/formula/{name}")
def formula(name: str) -> dict:
    """方剂谱系 + 君臣佐使 + 剂量古今换算。"""
    kb = get_kb()
    view = kb.genealogy.genealogy(name)
    if view.get("found"):
        view["analysis"] = kb.analyze_formula(name)
    return view


@app.get("/analyze/{name}")
def analyze(name: str) -> dict:
    """单独返回某方的君臣佐使与剂量折算。"""
    res = get_kb().analyze_formula(name)
    if res is None:
        raise HTTPException(404, f"formula not found: {name}")
    return res


@app.get("/formulas")
def formulas(herb: str, limit: int = Query(50, ge=1, le=300)) -> dict:
    kb = get_kb()
    canonical = kb.normalizer.normalize(herb).canonical
    hits = kb.genealogy.formulas_with_herb(canonical, limit=limit)
    return {
        "herb": canonical,
        "count": len(hits),
        "formulas": [
            {"name": f.name, "book": f.book_title, "dynasty": f.dynasty,
             "category": f.category, "herbs": f.composition_herbs,
             "indications": f.indications}
            for f in hits
        ],
    }


@app.get("/report/{name}")
def report(name: str, disease: str = "骨质疏松") -> dict:
    md = herb_dossier_markdown(get_kb(), name, disease=disease)
    return {"name": name, "markdown": md}


# ---- voice (语音交互) --------------------------------------------------
@app.get("/voice/status")
def voice_status_ep() -> dict:
    from ..voice import voice_status
    return voice_status()


@app.post("/voice/asr")
async def voice_asr(request: Request) -> dict:
    """语音转文字 (FireRedASR2-AED)。请求体为原始音频字节（ffmpeg 会转码）。
    未配置模型时返回 503，前端回退浏览器识别。"""
    import tempfile
    from ..voice import get_asr, VoiceUnavailable
    try:
        backend = get_asr()
    except VoiceUnavailable as e:
        raise HTTPException(503, str(e))
    data = await request.body()
    if not data:
        raise HTTPException(400, "empty audio body")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        return backend.transcribe(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.post("/voice/tts")
def voice_tts(payload: dict = Body(...)):
    """文字转语音 (CosyVoice3)。未配置模型时返回 503，前端回退浏览器朗读。"""
    from ..voice import get_tts, VoiceUnavailable
    import os
    text = (payload or {}).get("text", "").strip()
    if not text:
        raise HTTPException(400, "text is required")
    prompt_wav = (payload or {}).get("prompt_wav") or os.environ.get("HERB_HERMES_TTS_PROMPT_WAV")
    if not prompt_wav:
        raise HTTPException(503, "未配置参考音频 HERB_HERMES_TTS_PROMPT_WAV")
    try:
        backend = get_tts()
        wav = backend.synthesize(
            text, prompt_wav,
            prompt_text=(payload or {}).get("prompt_text", ""),
            instruct=(payload or {}).get("instruct", ""))
    except VoiceUnavailable as e:
        raise HTTPException(503, str(e))
    return Response(content=wav, media_type="audio/wav")


# ---- static frontend ("研究驾驶舱") ------------------------------------
# Served under /app/ so the page's relative assets (styles.css, app.js) resolve
# correctly; "/" redirects there.
@app.get("/")
def index():
    if (_FRONTEND_DIR / "index.html").exists():
        return RedirectResponse(url="/app/")
    raise HTTPException(404, "frontend not built")


if _FRONTEND_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")
