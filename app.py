from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    print(1)
    return 1
