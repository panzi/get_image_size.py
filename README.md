get_image_size.py
=================

Tiny Python library that only reads the size of an image with no external dependencies.

```Python
class UnknownImageFormat(Exception):
    file_path: str
    format: Optional[str]
    sub_format: Optional[str]

    def __init__(self, file_path: str, format: Optional[str]=None, sub_format: Optional[str]=None) -> None:

def get_image_size(file_path: str) -> Tuple[int, int]:
    """
    Return (width, height) for a given image file content.
    File must be seekable. May throw UnknownImageFormat.
    """
```

Supported file formats:

* AVIF
* BMP
* GIF
* ICO
* JPEG
* OpenEXR
* PNG
* PSD
* QOI
* TIFF
* WEBP
* XCF
