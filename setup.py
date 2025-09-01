from setuptools import setup

setup(
  name='gherila',
  author='s4nica',
  url='https://github.com/br4nch/gherila',
  version='1.0.4',
  license='MIT',
  description='An async package destioned to fetch information from different platforms',
  python_requires='>=3.8.0',
  install_requires=['munch', 'aiohttp', 'pydantic', 'orjson'],
  packages=['gherila'],
  classifiers=[
    'Programming Language :: Python :: 3.8',
    'Programming Language :: Python :: 3.9',
    'Programming Language :: Python :: 3.10',
    'Programming Language :: Python :: 3.11',
    'Programming Language :: Python :: 3.12',
    'Programming Language :: Python :: 3.13',
    'License :: OSI Approved :: MIT License',
    'Operating System :: OS Independent',
  ],
  include_package_data=True,
)