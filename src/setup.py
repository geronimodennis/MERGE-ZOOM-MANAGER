from setuptools import setup
from Cython.Build import cythonize
import numpy
# import cv2
# import threading
# import math

setup(
    ext_modules = cythonize("./*.pyx"),
    include_dirs=[numpy.get_include()]
)
