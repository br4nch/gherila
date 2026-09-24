from setuptools import setup

setup(
  name='gherila',
  author='s4nica',
  url='https://github.com/br4nch/gherila',
  version='1.3.1',
  license='MIT',
  description='An async package destioned to fetch information from different platforms',
  python_requires='>=3.10',
  install_requires=['munch', 'aiohttp', 'pydantic>=2', 'orjson', 'aiofiles', 'selectolax'],
  packages=['gherila'],
  classifiers=[
    'Programming Language :: Python :: 3.10',
    'Programming Language :: Python :: 3.11',
    'Programming Language :: Python :: 3.12',
    'Programming Language :: Python :: 3.13',
    'Programming Language :: Python :: 3.14',
    'License :: OSI Approved :: MIT License',
    'Operating System :: OS Independent',
  ],
  include_package_data=True,
)
