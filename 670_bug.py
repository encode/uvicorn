from multiprocessing import Process
import uvicorn

myproc = Process(target=uvicorn.run, kwargs={'app':'app:app', 'workers':2})
myproc.start()
# # myproc.terminate()
# myproc.join()