# Running in a Production Environment

## Run using Process Managers

### What is a Process Manager?

Computers can run multiple programs in parallel using processes. The OS provides primitives for creating a new process and running a program in it, but it does not know what that program is doing. The OS cannot for example realize that your web app is crashing and needs to be restarted. That's where process managers come in. Within the context of a web server, a process manager is a program that monitors the health of multiple server processes and coordinates killing and spinning up of new processes to keep the application online and healthy.
### Using a process manager
Running Uvicorn using a process manager ensures that you can run multiple processes in a resilient manner, and 
allows you to perform server upgrades without dropping requests.


!!! question "Do you know?"
    Uvicorn provides a lightweight way to run multiple worker processes, for example `--workers 4`, but does not provide any process monitoring.

There are several tools you can use as process manager. In this section we will see how to use the following tools:

- Gunicorn
- Supervisor
- Circus

!!! tldr
    The recommended process manager is Gunicorn.


### Using Gunicorn

[Gunicorn](https://gunicorn.org/) is probably the simplest way to run and manage Uvicorn in a production setting. 
Uvicorn includes a gunicorn worker class that means you can get set up with very little configuration.

!!! note
    Gunicorn is mainly an application server using the WSGI standard and not ASGI standard.But Gunicorn supports working as a process manager and allowing users to tell it which specific worker process class to use. Then Gunicorn would start one or more worker processes using that class.

Now we will see how we can deploy using the Gunicorn.

Let's first install Gunicorn.
```commandline
pip install gunicorn
```

Then, to start the Gunicorn with Uvicorn workers
```commandline
gunicorn -w 4 -k uvicorn.workers.UvicornWorker
```
The above command will start Gunicorn with 4 workers! 

`uvicorn.workers.UvicornWorker` is the worker class we discussed about.
The `UvicornWorker` implementation uses the `uvloop` and `httptools` implementations for improved performance. 

To run under `PyPy` you'll want to use pure-python implementation instead. You can do this by using the `UvicornH11Worker` class.

If you need to pass Uvicorn's config arguments to gunicorn workers then you'll have to subclass `UvicornWorker`.
```python
from uvicorn.workers import UvicornWorker

class MyUvicornWorker(UvicornWorker):
    CONFIG_KWARGS = {"loop": "asyncio", "http": "h11", "lifespan": "off"}
```

### Using Supervisor

[Supervisor](http://supervisord.org/) is a client/server system that allows its users to monitor and control a number of processes on UNIX-like operating systems.

To use `supervisor` as a process manager you should either:

* Hand over the socket to uvicorn using its file descriptor, which supervisor always makes available as `0`, and which must be set in the `fcgi-program` section.
* Or use a UNIX domain socket for each `uvicorn` process.

A simple supervisor configuration might look something like this:

**supervisord.conf**:

```ini
[supervisord]

[fcgi-program:uvicorn]
socket=tcp://localhost:8000
command=venv/bin/uvicorn --fd 0 example:App
numprocs=4
process_name=uvicorn-%(process_num)d
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
```

Then run with `supervisord -n`.

### Using Circus

[Circus](https://circus.readthedocs.io/en/latest/) is a Python program which can be used to monitor and control processes and sockets.

To use `circus` as a process manager, you should either:

* Hand over the socket to uvicorn using its file descriptor, which circus makes available as `$(circus.sockets.web)`.
* Or use a UNIX domain socket for each `uvicorn` process.

A simple circus configuration might look something like this:

**circus.ini**:

```ini
[watcher:web]
cmd = venv/bin/uvicorn --fd $(circus.sockets.web) example:App
use_sockets = True
numprocesses = 4

[socket:web]
host = 0.0.0.0
port = 8000
```

Then run `circusd circus.ini`.

## Run using Docker Containers

A container is a standard unit of software that packages up code and all its dependencies so the application runs quickly and reliably from one computing environment to another. A Docker container image is a lightweight, standalone, executable package of software that includes everything needed to run an application: code, runtime, system tools, system libraries and settings.

In this section we will see how to run your application using a docker container.

### What is docker?

[Docker](https://docs.docker.com/get-started/overview/) is an open platform for developing, shipping, and running applications. Docker enables you to separate your applications from your infrastructure, so you can deliver software quickly. With Docker, you can manage your infrastructure in the same ways you manage your applications. By taking advantage of Docker’s methodologies for shipping, testing, and deploying code quickly, you can significantly reduce the delay between writing code and running it in production.

### Creating Docker Image

Before getting started, make sure you have installed Docker in your environment. If not, follow the guide from [official documentation](https://docs.docker.com/get-started/#download-and-install-docker) to install.    
To get started, the first thing is to build an image. Docker images normally includes in its metadata the default program or command that should be run when the container is started and the parameters to be passed to that program

While building an image, the folder structure is very important. The following tutorial is using a structure like this:
```
.
├── app
│   ├── __init__.py
│   └── main.py
├── Dockerfile
└── requirements.txt
```

Okay, let's get building.

Create a file called `Dockerfile` in root of your project/repo.

```commandline
touch Dockerfile
```

!!! note
    Notice that `Dockerfile` does not have an extension. Text editors, mainly in Windows OS might add `txt`. It is important to remove them before saving. 

Let's edit the file we created and add the following. You can use your favorite text editor.

```commandline
FROM python:3.9

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./app /code/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]

HEALTHCHECK CMD curl http://localhost/
```

The above Dockerfile should be ideal for most of the application. It uses base python image. You can always customize it based on your needs.

!!! tip "Health check probe"
    Notice the last line in the file above? That is an optional healthcheck implementation. 
    
    Using a healthcheck instruction in your Dockerfile is considered a best practice to enable Docker to terminate containers which are not responding correctly, and instantiate new ones.
    It is suggested to extend this basic healthcheck. Make sure to use the right port. For further information you can look at the official [Docker healthcheck documentation](https://docs.docker.com/engine/reference/builder/#healthcheck). 


Now that all the files are in place, let's build the container image.

- Go to the project directory (in where your Dockerfile is, containing your app directory).
- Build your image:

```commandline
docker build -t my_app .
```

!!! tip
    Notice the `.` at the end, it's equivalent to `./`, it tells Docker the directory to use to build the container image. In this case, it's the same current directory `.`.

The build time varies depending upon how big your application is, and number of requirements in your `requirements.txt`. However, it should not be too long. You can leverage Docker cache to speed up your build process!

### Start the Docker Container

To run the image you built, it's simple.

```commandline
docker run -d --name mycontainer -p 80:80 my_app
```

`-p` argument specifies which port to expose. This is important, without this, you will not be able to access your container from your host.

Docker provides various [options](https://docs.docker.com/engine/reference/commandline/run/#options) which you can use while starting your app.

Congratulations! You have successfully built a Docker Image and started a container. Just hop on to the web-browser and you should be able to access your app using the IP of your host or `localhost` (if the browser is in same host).


