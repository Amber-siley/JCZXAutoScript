from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
import os

from .graph_builder import list_config_files, build_graph, get_entity_detail

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
    return result


@app.get("/api/entity/{name}")
async def api_entity(name: str, file: str = Query(..., description="Config filename")):
    detail = get_entity_detail(file, name)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Entity not found: {name}")
    return detail
