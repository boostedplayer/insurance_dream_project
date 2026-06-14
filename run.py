import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8002,
        reload=True,       # production mein ise False kar dena
        workers=1,         # Production mein CPU count ke hisaab se badhao (persistent checkpointer ke saath)
    )
