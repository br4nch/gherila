gherila
=======

A modern, easy-to-use, asynchronous package designed to fetch information from different platforms quick and efficient.

Instalation
-----------

```bash
pip install -U gherila
```

Usage
-----

```python
from gherila import Instagram

async def main():
  ig = Instagram("CSRF_TOKEN", "SESSION_ID")
  user = await ig.get_user("USERNAME")
  print(user)

if __name__ = "__main__":
  import asyncio
  asyncio.run(main())
```