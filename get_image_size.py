#!/usr/bin/env python3

from typing import Tuple, Optional
from os import fstat, walk
from os.path import isdir, join as join_path
from struct import unpack

__all__ = 'UnknownImageFormat', 'get_image_size'

# Original source: https://stackoverflow.com/questions/15800704/get-image-size-without-loading-image-into-memory
#-------------------------------------------------------------------------------
# Name:        get_image_size
# Purpose:     extract image dimensions given a file path using just
#              core modules
#
# Author:      Paulo Scardine, Mathias Panzenböck (based on code from Emmanuel VAÏSSE)
#
# Created:     26/09/2013
# Copyright:   (c) Paulo Scardine 2013, (c) Mathias Panzenböck 2022
# Licence:     MIT
#-------------------------------------------------------------------------------

TIFF_TYPES = [
    (1, "B"),  #  1 BYTE
    (1, "c"),  #  2 ASCII
    (2, "H"),  #  3 SHORT
    (4, "L"),  #  4 LONG
    (8, "LL"), #  5 RATIONAL
    (1, "b"),  #  6 SBYTE
    (1, "c"),  #  7 UNDEFINED
    (2, "h"),  #  8 SSHORT
    (4, "l"),  #  9 SLONG
    (8, "ll"), # 10 SRATIONAL
    (4, "f"),  # 11 FLOAT
    (8, "d")   # 12 DOUBLE
]

TIFF_TYPES_BE = [(sz, '>' + fmt) for sz, fmt in TIFF_TYPES]
TIFF_TYPES_LE = [(sz, '<' + fmt) for sz, fmt in TIFF_TYPES]

class UnknownImageFormat(Exception):
    __slots__ = 'file_path', 'format', 'sub_format'

    file_path: str
    format: Optional[str]
    sub_format: Optional[str]

    def __init__(self, file_path: str, format: Optional[str]=None, sub_format: Optional[str]=None) -> None:
        msg: str
        if format is None:
            msg = f'Unknown image format: {file_path}'
        elif sub_format is None:
            msg = f'Error parsing {format} image: {file_path}'
        else:
            msg = f'Error parsing {format} ({sub_format}) image: {file_path}'

        super().__init__(msg)

        self.file_path  = file_path
        self.format     = format
        self.sub_format = sub_format

def get_image_size(file_path: str) -> Tuple[int, int]:
    """
    Return (width, height) for a given image file content.
    File must be seekable. May throw UnknownImageFormat.
    """

    with open(file_path, 'rb') as input:
        data = input.read(30)
        meta = fstat(input.fileno())
        size = meta.st_size

        if size >= 10 and (data.startswith(b'GIF87a') or data.startswith(b'GIF89a')):
            # GIFs
            return unpack("<HH", data[6:10])
        elif data.startswith(b'\211PNG\r\n\032\n'):
            # PNG
            if size >= 24 and data[12:16] == b'IHDR':
                return unpack(">LL", data[16:24])
            elif size >= 16:
                # older PNGs?
                return unpack(">LL", data[8:16])
            else:
                raise UnknownImageFormat(file_path, 'PNG')
        elif size >= 7 and data.startswith(b'\377\330'):
            # JPEG
            input.seek(3)
            b = data[2:3]
            try:
                while b and b != b'\xDA':
                    while b != b'\xFF':
                        b = input.read(1)
                        if not b:
                            raise UnknownImageFormat(file_path, 'JPEG')
                    while b == b'\xFF':
                        b = input.read(1)
                        if not b:
                            raise UnknownImageFormat(file_path, 'JPEG')
                    b0 = b[0]
                    if b0 >= 0xC0 and b0 <= 0xC3:
                        input.seek(3, 1)
                        height, width = unpack(">HH", input.read(4))
                        return width, height
                    else:
                        input.seek(unpack(">H", input.read(2))[0] - 2, 1)
                    b = input.read(1)

                raise UnknownImageFormat(file_path, 'JPEG')
            except Exception as error:
                raise UnknownImageFormat(file_path, 'JPEG') from error
        elif data.startswith(b'RIFF') and size >= 30 and data[8:12] == b'WEBP':
            # WEBP
            # learned format from: https://wiki.tcl-lang.org/page/Reading+WEBP+image+dimensions
            hdr = data[12:16]
            if hdr == b'VP8L':
                b0 = data[21]
                b1 = data[22]
                b2 = data[23]
                b3 = data[24]
                width  = 1 + (((b1 & 0x3F) << 8) | b0)
                height = 1 + (((b3 & 0xF) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6))
            elif hdr == b'VP8 ':
                b0 = data[23]
                b1 = data[24]
                b2 = data[25]
                if b0 != 0x9d or b1 != 0x01 or b2 != 0x2a:
                    raise UnknownImageFormat(file_path, 'WEBP', 'VP8 ')
                w, h = unpack("<HH", data[26:30])
                width  = w & 0x3ffff
                height = h & 0x3ffff
            elif hdr == b'VP8X':
                w1 = data[24]
                w2 = data[25]
                w3 = data[26]
                h1 = data[27]
                h2 = data[28]
                h3 = data[29]

                width  = (w1 | w2 << 8 | w3 << 16) + 1
                height = (h1 | h2 << 8 | h3 << 16) + 1

                return width, height
            else:
                raise UnknownImageFormat(file_path, 'WEBP')
            return width, height
        elif data[4:12] == b'ftypavif':
            # AVIF
            ftype_size, = unpack(">I", data[0:4])
            input.seek(ftype_size)

            # chunk nesting: meta > iprp > ipco > ispe
            # search meta chunk
            chunk_size = 0
            while True:
                data = input.read(8)
                if len(data) < 8:
                    raise UnknownImageFormat(file_path, 'AVIF')
                chunk_size, = unpack(">I", data[0:4])
                if data.endswith(b'meta'):
                    break
                input.seek(chunk_size - 8, 1)

            input.seek(4, 1)
            chunk_offset = 12
            sub_chunk_size = 0
            # search iprp
            while True:
                if chunk_offset >= chunk_size:
                    raise UnknownImageFormat(file_path, 'AVIF')
                data = input.read(8)
                if len(data) < 8:
                    raise UnknownImageFormat(file_path, 'AVIF')
                sub_chunk_size, = unpack(">I", data[0:4])
                if data.endswith(b'iprp'):
                    break
                chunk_offset += sub_chunk_size
                input.seek(sub_chunk_size - 8, 1)

            chunk_offset = 8
            chunk_size = sub_chunk_size
            sub_chunk_size = 0
            # search ipco
            while True:
                if chunk_offset >= chunk_size:
                    raise UnknownImageFormat(file_path, 'AVIF')
                data = input.read(8)
                if len(data) < 8:
                    raise UnknownImageFormat(file_path, 'AVIF')
                sub_chunk_size, = unpack(">I", data[0:4])
                if data.endswith(b'ipco'):
                    break
                chunk_offset += sub_chunk_size
                input.seek(sub_chunk_size - 8, 1)

            chunk_offset = 8
            chunk_size = sub_chunk_size
            sub_chunk_size = 0
            # search ispe
            while True:
                if chunk_offset >= chunk_size:
                    raise UnknownImageFormat(file_path, 'AVIF')
                data = input.read(8)
                if len(data) < 8:
                    raise UnknownImageFormat(file_path, 'AVIF')
                sub_chunk_size, = unpack(">I", data[0:4])
                if data.endswith(b'ispe'):
                    break
                chunk_offset += sub_chunk_size
                input.seek(sub_chunk_size - 8, 1)

            chunk_offset = 8
            chunk_size = sub_chunk_size
            if chunk_size < 12:
                raise UnknownImageFormat(file_path, 'AVIF')
            data = input.read(12)
            if len(data) < 12:
                raise UnknownImageFormat(file_path, 'AVIF')
            return unpack(">II", data[4:])
        elif data.startswith(b'BM') and data[6:10] == b'\0\0\0\0' and size >= 26:
            # BMP
            width, height = unpack("<ii", data[18:26])
            # height is negative when stored upside down
            return width, abs(height)
        elif size >= 8 and (data.startswith(b"II\052\000") or data.startswith(b"MM\000\052")):
            # from here: https://github.com/scardine/image_size
            # Standard TIFF, big- or little-endian
            # BigTIFF and other different but TIFF-like formats are not
            # supported currently
            byteOrder = data[:2]
            # maps TIFF type id to size (in bytes)
            # and python format char for struct
            if byteOrder == b"MM":
                tiffTypes = TIFF_TYPES_BE
                ulong  = ">L"
                ushort = ">H"
            else:
                tiffTypes = TIFF_TYPES_LE
                ulong  = "<L"
                ushort = "<H"
            ifdOffset = unpack(ulong, data[4:8])[0]
            try:
                countSize = 2
                input.seek(ifdOffset)
                ec = input.read(countSize)
                ifdEntryCount = unpack(ushort, ec)[0]
                # 2 bytes: TagId + 2 bytes: type + 4 bytes: count of values + 4
                # bytes: value offset
                ifdEntrySize = 12
                width  = -1
                height = -1
                for i in range(ifdEntryCount):
                    entryOffset = ifdOffset + countSize + i * ifdEntrySize
                    input.seek(entryOffset)
                    btag = input.read(2)
                    tag = unpack(ushort, btag)[0]
                    if tag == 256 or tag == 257:
                        # if type indicates that value fits into 4 bytes, value
                        # offset is not an offset but value itself
                        btype = input.read(2)
                        ftype = unpack(ushort, btype)[0]
                        if ftype < 1 or ftype > len(tiffTypes):
                            raise UnknownImageFormat(file_path, 'TIFF', f'unknown field type: {ftype}')
                        typeSize, typeChar = tiffTypes[ftype - 1]
                        input.seek(entryOffset + 8)
                        bvalue = input.read(typeSize)
                        if ftype == 5 or ftype == 10:
                            # rational
                            a, b = unpack(typeChar, bvalue)[0]
                            value = int(a) // int(b)
                        else:
                            value = int(unpack(typeChar, bvalue)[0])

                        if value < 0:
                            value = 0

                        if tag == 256:
                            width  = value
                        else:
                            height = value
                        if width > -1 and height > -1:
                            return width, height

                raise UnknownImageFormat(file_path, 'TIFF')
            except Exception as error:
                raise UnknownImageFormat(file_path, 'TIFF') from error
        elif data.startswith(b'qoif') and size >= 14:
            # QOI
            return unpack(">II", data[4:12])
        elif data.startswith(b'8BPS\0\x01\0\0\0\0\0\0') and size >= 22:
            # PSD
            height, width = unpack(">II", data[14:22])
            return width, height
        elif data.startswith(b'gimp xcf ') and size >= 22 and data[13] == 0:
            # XCF
            return unpack(">II", data[14:22])
        elif data.startswith(b'\0\0\x01\0') and size >= 6:
            # ICO
            count, = unpack("<H", data[4:6])
            input.seek(6)
            width  = 0
            height = 0
            for _ in range(count):
                data = input.read(16)
                if len(data) < 16:
                    raise UnknownImageFormat(file_path, 'ICO')
                w = data[0]
                h = data[1]
                if w >= width and h >= height:
                    width  = w
                    height = h
            return width, height
        elif data.startswith(b"\x76\x2f\x31\x01") and size > 8 and (data[4] == 0x01 or data[4] == 0x02):
            # OpenEXR
            input.seek(8)
            while True:
                name_buf = bytearray()
                while True:
                    chunk = input.read(1)
                    if not chunk:
                        raise UnknownImageFormat(file_path, 'OpenEXR')
                    byte = chunk[0]
                    if byte == 0:
                        break
                    name_buf.append(byte)

                if len(name_buf) == 0:
                    break

                type_buf = bytearray()
                while True:
                    chunk = input.read(1)
                    if not chunk:
                        raise UnknownImageFormat(file_path, 'OpenEXR')
                    byte = chunk[0]
                    if byte == 0:
                        break
                    type_buf.append(byte)

                size_buf = input.read(4)
                if len(size_buf) < 4:
                    raise UnknownImageFormat(file_path, 'OpenEXR')
                size, = unpack("<I", size_buf)

                if name_buf == b"displayWindow":
                    if type_buf != b"box2i" or size != 16:
                        raise UnknownImageFormat(file_path, 'OpenEXR')

                    box_buf = input.read(16)
                    x1, y1, x2, y2 = unpack("<iiii", box_buf)
                    width  = x2 - x1 + 1
                    height = y2 - y1 + 1
                    if width <= 0 or height <= 0:
                        raise UnknownImageFormat(file_path, 'OpenEXR')
                    return width, height
                else:
                    input.seek(size, 1)
            raise UnknownImageFormat(file_path, 'OpenEXR')
    # TODO: PCX, TGA

    raise UnknownImageFormat(file_path)

def main() -> None:
    import sys
    for path in sys.argv[1:]:
        if isdir(path):
            for parent, dirnames, filenames in walk(path):
                for filename in filenames:
                    file_path = join_path(parent, filename)
                    try:
                        width, height = get_image_size(file_path)
                    except Exception as error:
                        print('*** error:', file_path, error, file=sys.stderr)
                    else:
                        print(file_path, width, height)
        else:
            file_path = path
            try:
                width, height = get_image_size(file_path)
            except Exception as error:
                print('*** error:', file_path, error, file=sys.stderr)
            else:
                print(file_path, width, height)

if __name__ == '__main__':
    main()
