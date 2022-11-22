from setuptools import setup, find_packages

setup(
    zip_safe=False,
    packages=find_packages(),
    install_requires=[
        'wheel==0.33.6',
        'requests>=2.20.0',
        'CacheControl==0.12.3',
        'requests-cache==0.4.13',
        'requests-mock==1.8.0',
        'termcolor==1.1.0',
        'docker==2.5.1',
        'gitpython==3.0.8',
        'python-dateutil==2.8.1',
        'PyYAML==5.4',
        'beautifulsoup4==4.8.2',
        'lxml==4.6.5',
        'packaging==20.7',
        'urllib3==1.26.5',
        "pyparsing==3.0.9"
    ],
)
