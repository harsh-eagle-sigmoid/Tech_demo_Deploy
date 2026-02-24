from setuptools import setup, find_packages

setup(
    name="agent-observe-sdk",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["requests>=2.20"],
    python_requires=">=3.8",
    description="Lightweight observability SDK for AI agents",
)
