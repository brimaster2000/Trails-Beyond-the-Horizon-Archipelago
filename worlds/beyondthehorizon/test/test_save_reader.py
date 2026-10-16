import tempfile
import unittest
from pathlib import Path

from .. import save_reader
from ..data import CHESTS

try:
    import zstandard
except ImportError:
    zstandard = None

SAVE_SIZE = 2_722_840


@unittest.skipIf(zstandard is None, "zstandard not installed")
class TestSaveReader(unittest.TestCase):
    def test_reads_chest_flag_from_compressed_save(self) -> None:
        chest = CHESTS[0]  # VAR-halla Sector Chest 1, flag 1500
        raw = bytearray(SAVE_SIZE)
        raw[save_reader.FLAG_ARRAY_OFFSET + chest.flag // 8] |= 1 << (chest.flag % 8)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save226" / "user.dat"
            path.parent.mkdir()
            path.write_bytes(zstandard.ZstdCompressor().compress(bytes(raw)))

            self.assertEqual(save_reader.newest_save(Path(tmp)), path)
            data = save_reader.decompress_save(path)
            flags = {c.id: c.flag for c in CHESTS if c.flag is not None}
            self.assertEqual(save_reader.checked_locations(data, flags), {chest.id})

    def test_fixed_chest_flags(self) -> None:
        flagged = [c for c in CHESTS if c.flag is not None]
        self.assertEqual(len(flagged), 187)
        self.assertEqual([c.flag for c in flagged], list(range(1500, 1687)))


class TestSeedMarker(unittest.TestCase):
    def test_marker_round_trip(self) -> None:
        from ..game_memory import SEED_MARKER_FLAG, read_marker, seed_marker

        marker = seed_marker("12345678901234567890", 1)
        self.assertNotEqual(marker, 0)
        self.assertNotEqual(marker, seed_marker("12345678901234567890", 2))
        flags = bytearray(0x2000)
        flags[SEED_MARKER_FLAG // 8:SEED_MARKER_FLAG // 8 + 4] = marker.to_bytes(4, "little")
        self.assertEqual(read_marker(bytes(flags)), marker)
