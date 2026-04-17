import uvicorn

from server.config import SERVER_HOST, SERVER_PORT

if __name__ == "__main__":
    uvicorn.run(
        "server.main:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=True,
    )
