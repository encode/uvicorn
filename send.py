import asyncio

import httpx as httpx


async def main():
    client = httpx.AsyncClient()
    queries = []
    for i in range(10):
         task = asyncio.create_task(client.get("http://localhost:8000"))
         queries.append(task)
    results = await asyncio.wait(queries)
    print(results)
    # results = await asyncio.gather(*queries)
    # print(results)
    # return results
    #         resp = await client.get("http://localhost:8000")
    #         print(resp)
if __name__ == '__main__':
    asyncio.run(main())