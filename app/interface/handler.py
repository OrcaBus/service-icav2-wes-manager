from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRouter
from mangum import Mangum
from icav2_wes_api.api import analysis

openapi_url = "/schema/openapi.json"
app = FastAPI(
    title="ICAv2 WES Api",
    summary="Access ICAv2 WES Api Information",
    openapi_url=openapi_url,
)
router = APIRouter(prefix="/api/v1")
router.include_router(analysis.router, prefix="/analysis")
app.include_router(router)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="UMCCR ICAv2 WES Manager Swagger Page",
        version="1.0.0",
        description="Authorize with the OrcaBus token to get started",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "OrcaBus Token": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    openapi_schema["security"] = [{"OrcaBus Token": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

@app.get("/")
async def root():
    return {"message": "Welcome to the UMCCR ICAv2 WES api!!"}

@app.get("/schema/swagger-ui")
def read_docs():
    return get_swagger_ui_html(
        title="OrcaBus UMCCR ICAv2 WES API Manager Swagger",
        openapi_url=openapi_url
    )


handler = Mangum(app)
