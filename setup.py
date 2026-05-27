from setuptools import find_packages, setup

setup(
    name="sentinel",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "sentinel=sentinel.deploy.runner:main",
        ],
    },
    python_requires=">=3.9",
    author="ADLC Demo",
    description="Autonomous code review bot with sub-agents following the Agent Development Lifecycle",
)
