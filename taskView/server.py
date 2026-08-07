import os
from typing import Optional

from fastapi import Body, FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import editor as ed
from .graph_builder import list_config_files, build_graph, get_entity_detail, build_flow_tree

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = FastAPI(title="taskView", version="1.0.0")

app.mount("/static", StaticFiles(directory=STATIC_DIR, check_dir=False), name="static")


@app.get("/")
async def root():
    from fastapi.responses import FileResponse
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/files")
async def api_files():
    return list_config_files()


@app.get("/api/graph")
async def api_graph(file: str = Query(..., description="Config filename, e.g. MainMenu.txt")):
    result = build_graph(file)
    if not result["nodes"] and not result["edges"]:
        raise HTTPException(status_code=404, detail=f"File not found or empty: {file}")
    target_path = os.path.normpath(os.path.join(ed.CONFIG_DIR, *file.split("/")))
    if os.path.isfile(target_path):
        result["file_hash"] = ed.file_hash(target_path)
    return result


class ApplyRequest(BaseModel):
    ops: list[dict]
    base_hash: Optional[str] = None


@app.get("/api/entities")
async def api_entities():
    """实体池候选列表（key + label + type），供自动补全。"""
    pool, _ = ed.load_entity_pool()
    return [{"key": k, "label": v.name or k, "type": v.type or ""} for k, v in pool.items()]


@app.post("/api/file/{file:path}/validate")
async def api_validate(file: str, req: ApplyRequest = Body(...)):
    pool, efile = ed.load_entity_pool()
    target_path = os.path.normpath(os.path.join(ed.CONFIG_DIR, *file.split("/")))
    if not os.path.isfile(target_path):
        raise HTTPException(status_code=404, detail=f"File not found: {file}")
    try:
        _, errors = ed.simulate_and_validate(pool, efile, file, req.ops)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"errors": errors}


@app.post("/api/file/{file:path}/apply")
async def api_apply(file: str, req: ApplyRequest = Body(...)):
    pool, efile = ed.load_entity_pool()
    target_path = os.path.normpath(os.path.join(ed.CONFIG_DIR, *file.split("/")))
    if not os.path.isfile(target_path):
        raise HTTPException(status_code=404, detail=f"File not found: {file}")

    # 并发冲突保护：base_hash 与磁盘当前哈希不符则拒绝
    if req.base_hash and req.base_hash != ed.file_hash(target_path):
        return JSONResponse(status_code=409, content={"detail": "文件已被外部修改，请重新加载"})

    try:
        writes, errors = ed.simulate_and_validate(pool, efile, file, req.ops)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if errors:
        return JSONResponse(status_code=422, content={"errors": errors})

    written = []
    for path, new_text in writes:
        ed.write_text_atomic(path, new_text)   # writes 元素 = (path, 完整新文本)
        written.append(os.path.relpath(path, ed.CONFIG_DIR).replace(os.sep, "/"))

    graph = build_graph(file)
    return {"graph": graph, "file_hash": ed.file_hash(target_path), "written": written}


@app.get("/api/entity/{name}")
async def api_entity(name: str, file: str = Query(..., description="Config filename")):
    detail = get_entity_detail(file, name)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Entity not found: {name}")
    return detail


@app.get("/api/flow")
async def api_flow(file: str = Query(...), task: str = Query(...)):
    result = build_flow_tree(file, task)
    if not result["nodes"] and not result["edges"]:
        raise HTTPException(status_code=404, detail=f"Task not found or empty: {task}")
    return result
