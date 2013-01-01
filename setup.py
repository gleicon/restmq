from setuptools import setup, find_packages

setup(
    name="RestMQ",
    version="1.1",

    packages=find_packages('src') + ['twisted.plugins'],
    package_dir={
        '': 'src',
        },

    package_data    = {'': ['*.conf', '*.html', '*.js', '*.sh']},
    include_package_data = True,

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

