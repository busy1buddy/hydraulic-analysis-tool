from setuptools import setup, find_packages

setup(
    name="hydraulic_analysis_tool",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "wntr",
        "PyQt6",
        "pyqtgraph",
        "numpy",
        "pandas",
        "matplotlib",
        "scipy",
        "networkx",
    ],
    entry_points={
        'console_scripts': [
            'hydraulic-tool=main_app:main',
        ],
    },
    author="HydraulicTool Team",
    description="A comprehensive hydraulic and transient analysis tool for water networks.",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8',
)
