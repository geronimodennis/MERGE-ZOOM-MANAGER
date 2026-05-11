from setuptools import setup


setup(
    name="merge-zoom-manager",
    version="1.7.0",
    py_modules=[
        "CaptureProcessor",
        "WindowCaptureConfiguration",
        "WindowRenderer",
        "WindowRendererGroupPreview",
        "WindowRendererPreview",
        "captureRunnerOnThread",
        "image_utils",
        "main",
        "models",
        "participant_detection",
        "participant_tracking",
        "performance",
        "win32_utils",
        "win32Manager",
        "windowCaptureHandler",
    ],
    install_requires=[
        "numpy",
        "opencv-python",
        "Pillow",
        "pywin32",
    ],
)
