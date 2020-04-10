from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def root():
    # print(1)
    return 1