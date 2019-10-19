import uvicorn.main

uvicorn.main.main.main(prog_name="uvicorn")
#                  ^--------------------------- main Click command's runner*
#             ^-------------------------------- main Click command
#        ^------------------------------------- main module
#  ^------------------------------------------- package

# *see https://click.palletsprojects.com/en/7.x/api/#click.BaseCommand.main
