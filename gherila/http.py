from munch import DefaultMunch
from typing import Any
from aiohttp import ClientSession

from .exceptions import Error

class State:

  async def request(self: "State", method: str, url: str, **kwargs) -> Any:
    async with ClientSession() as cs:
      response = await cs.request(
        method=method,
        url=url,
        **kwargs,
      )

      if response.content_type in (
        'text/plain',
        'text/html',
      ):
        return await response.text()
      
      elif response.content_type in (
        'application/json'
      ):
        try:
          data = await response.json(content_type=None)
        except Exception as e:
          raise Error(f"Could not parse JSON -> {e}")
        
        munch = DefaultMunch.fromDict(data)
        return munch
      return response