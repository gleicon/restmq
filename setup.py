from setuptools import setup, find_packages

setup(
    name="RestMQ",
    version="1.0",

    packages=find_packages('src') + ['twisted.plugins'],
    package_dir={
        '': 'src',
        },
    install_requires=[
        'twisted',
        'simplejson',
        'cyclone',
        ],
    author="Gleicon Moraes",
    author_email="gleicon@gmail.com",
    description="REST/JSON/HTTP based message queue",
    keywords="rest json message queue",
    url="https://github.com/gleicon/restmq",
    )
