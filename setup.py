from setuptools import setup

setup(
    name="obscurahtml",
    version="1.0.0",
    description="HTML obfuscation & protection tool by Forhad Hassan",
    author="Forhad Hassan",
    author_email="fh103010@gmail.com",
    url="https://github.com/Forhadj/ObscuraHTML",
    py_modules=["obscura"],
    install_requires=[
        "rich>=13.7.0",
        "pyfiglet>=1.0.2",
        "pycryptodome>=3.20.0",
    ],
    entry_points={
        "console_scripts": [
            "obscura=obscura:main",
        ],
    },
    python_requires=">=3.10",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Security",
        "Topic :: Internet :: WWW/HTTP",
    ],
)
