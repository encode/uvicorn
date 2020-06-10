import uvicorn

if __name__ == "__main__":
    uvicorn.main(
        auto_envvar_prefix='UVICORN'
    )
