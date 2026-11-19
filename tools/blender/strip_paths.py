"""Take machine paths out of a .blend file's bytes, in place (run by tools/pack.py on the packed copy of the scene).

  blender -b --factory-startup --python tools/blender/strip_paths.py -- <file.blend> <path> [<path> ...]

Blender writes the path a file was saved at into the file. Every text in the file that starts with one of the given
paths is rewritten without it (the film's own folder becomes `//`, as Blender writes a path beside the file), padded
to its old length, so nothing in the file moves. A compressed file is read and written with Blender's own zstandard.
Prints `stripped <n>`. The file is not opened as a scene: only its bytes are read.
"""
import io
import sys
from pathlib import Path


def strip(data, swaps):
    """`data` with every NUL-ended text starting with a path of `swaps` ((old, new) byte pairs, longest first)
    rewritten in place, and how many were."""
    out, n = bytearray(data), 0
    for old, new in swaps:
        for variant in (old, old.replace(b'/', b'\\')):
            at = out.find(variant)
            while at >= 0:
                end = out.find(b'\0', at)
                end = len(out) if end < 0 else end
                rest = bytes(out[at + len(variant):end]).lstrip(b'/\\') if new == b'//' else bytes(out[at + len(variant):end])
                text = new + rest
                out[at:end] = text + b'\0' * (end - at - len(text))
                n += 1
                at = out.find(variant, at + len(text))
    return bytes(out), n


def main():
    args = sys.argv[sys.argv.index('--') + 1:]
    path, swaps = Path(args[0]), []
    for spec in args[1:]:
        old, _, new = spec.partition('=')
        swaps.append((old.encode(), new.encode()))
    swaps.sort(key=lambda s: -len(s[0]))
    raw = path.read_bytes()
    packed = raw.startswith(b'\x28\xb5\x2f\xfd')
    if packed:
        import zstandard
        # a .blend is many zstd frames one after another
        data = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(raw), read_across_frames=True).read()
    else:
        data = raw
    data, n = strip(data, swaps)
    if n:
        if packed:
            data = zstandard.ZstdCompressor(level=3).compress(data)
        path.write_bytes(data)
    print(f'stripped {n}')


if __name__ == '__main__':
    main()
