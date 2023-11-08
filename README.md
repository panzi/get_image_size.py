get_image_size.py
=================

Tiny Python library that only reads the width and height of an image with no external dependencies.

```Python
class ImFormat(Enum): ...

class ImError(Exception): ...
class UnsupportedFormat(ImError): ...
class ParserError(ImError):
    format: ImFormat

class ImInfo(NamedTuple):
    width:  int
    height: int
    format: ImFormat

def get_image_size(input: Union[str, PathLike, bytes, bytearray, memoryview, IO[bytes]]) -> ImInfo:
    """
    Return (width, height, format) for a given image file.
    input must be seekable. May raise ImError.
    """

def get_image_size_from_path(file_path: Union[str, PathLike]) -> ImInfo: ...
def get_image_size_from_buffer(buffer: Union[bytes, bytearray, memoryview]) -> ImInfo: ...
def get_image_size_from_reader(input: IO[bytes]) -> ImInfo: ...
```

## Supported File Formats

* AVIF
* BMP
* DDS
* DIB
* GIF
* HEIC/HEIF
* ICO
* JPEG
* JPEG 2000
* OpenEXR
* PCX
* PNG
* PSD
* QOI
* TGA
* TIFF
* VTF
* WEBP
* XCF

No guarantees of correct or complete implementation are made.

## Related Work

* [panzi/imsz](https://github.com/panzi/imsz) – a very similar library in Rust with C bindings
* [scardine/imsz](https://github.com/scardine/imsz) – original Rust library from which the other is a fork
* [StackOverflow answer](https://stackoverflow.com/a/19035508/277767) – the start of it all
