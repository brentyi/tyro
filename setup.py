from setuptools import find_packages, setup

setup(
    name="dcargs",
    version="0.0",
    description="Automagic CLIs with dataclasses",
    url="http://github.com/brentyi/dcargs",
    author="brentyi",
    author_email="brentyi@berkeley.edu",
    license="MIT",
    packages=find_packages(),
    package_data={"dcargs": ["py.typed"]},
    python_requires=">=3.7",
    install_requires=[],
    extras_require={
        "testing": [
            "pytest",
            "pytest-cov",
        ],
        "type-checking": [
            "mypy",
        ],
    },
)
