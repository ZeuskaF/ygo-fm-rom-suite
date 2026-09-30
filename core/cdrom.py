"""
CD-ROM Engine for PlayStation 1 disc images (.bin / .iso / .cue).
Handles Mode 2 Form 1 (2352 bytes/sector) and Mode 1 / 2048-byte ISOs.
Implements full ISO 9660 filesystem parsing, file extraction, injection,
and accurate PSX EDC/ECC (Reed-Solomon) regeneration.
"""

import os
import struct
from typing import Dict, List, Optional, Tuple

# Precomputed Lookup Tables for CD-ROM ECC & EDC
ECC_F_LUT = bytearray(256)
ECC_B_LUT = bytearray(256)
EDC_LUT = [0] * 256

def _init_ecc_edc_tables():
    for i in range(256):
        j = ((i << 1) ^ (0x11D if (i & 0x80) else 0)) & 0xFF
        ECC_F_LUT[i] = j
        ECC_B_LUT[i ^ j] = i
        edc = i
        for _ in range(8):
            edc = (edc >> 1) ^ (0xD8018001 if (edc & 1) else 0)
        EDC_LUT[i] = edc & 0xFFFFFFFF

_init_ecc_edc_tables()

def compute_edc(data: bytes, length: int) -> int:
    """Computes 32-bit EDC checksum over given data buffer."""
    edc = 0
    for i in range(length):
        edc = ((edc >> 8) ^ EDC_LUT[(edc ^ data[i]) & 0xFF]) & 0xFFFFFFFF
    return edc

def _ecc_computeblock(src: bytearray, major_count: int, minor_count: int, 
                      major_mult: int, minor_inc: int, dest: bytearray, dest_offset: int):
    size = major_count * minor_count
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        ecc_a = 0
        ecc_b = 0
        for _ in range(minor_count):
            temp = src[index]
            index += minor_inc
            if index >= size:
                index -= size
            ecc_a ^= temp
            ecc_b ^= temp
            ecc_a = ECC_F_LUT[ecc_a]
        ecc_a = ECC_B_LUT[ECC_F_LUT[ecc_a] ^ ecc_b]
        dest[dest_offset + major] = ecc_a
        dest[dest_offset + major + major_count] = ecc_a ^ ecc_b

def generate_ecc(sector: bytearray, zero_address: bool = True):
    """Generates P-parity and Q-parity for a 2352-byte sector."""
    # Save address bytes (header at 12..15)
    saved_address = bytes(sector[0x0C : 0x10])
    if zero_address:
        sector[0x0C : 0x10] = b"\x00\x00\x00\x00"

    try:
        # P-code (86 columns x 24 words) -> 172 bytes written at 0x81C
        # Input is sector[0x0C : 0x81C] (2064 bytes)
        _ecc_computeblock(sector[0x0C : 0x81C], 86, 24, 2, 86, sector, 0x81C)

        # Q-code (52 diagonals x 43 words) -> 104 bytes written at 0x8C8
        # Input is sector[0x0C : 0x8C8] (2236 bytes, which includes P-parity)
        _ecc_computeblock(sector[0x0C : 0x8C8], 52, 43, 86, 88, sector, 0x8C8)
    finally:
        if zero_address:
            sector[0x0C : 0x10] = saved_address

def encode_mode2_form1_sector(sector: bytearray):
    """Recalculates EDC and ECC for a Mode 2 Form 1 (2352 bytes) PS1 sector."""
    # 1. Compute EDC over subheader (0x10) + user data (0x18..0x817) = 2056 bytes
    edc = compute_edc(sector[0x10 : 0x818], 0x808)
    struct.pack_into("<I", sector, 0x818, edc)
    # 2. Compute ECC P/Q codes
    generate_ecc(sector, zero_address=True)


class ISOFileEntry:
    def __init__(self, name: str, lba: int, size: int, is_dir: bool = False):
        self.name = name
        self.lba = lba
        self.size = size
        self.is_dir = is_dir

    def __repr__(self):
        return f"<ISOFileEntry {self.name} LBA={self.lba} Size={self.size} bytes{' [DIR]' if self.is_dir else ''}>"


class PS1DiscImage:
    """
    Parser and manager for PS1 CD-ROM images (.bin / .iso).
    Supports inspecting, extracting, and injecting files.
    """
    SYNC_PATTERN = bytes([0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00])

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.filesize = os.path.getsize(filepath)
        self.sector_size = self._detect_sector_size()
        self.is_raw_2352 = (self.sector_size == 2352)
        self.user_data_offset = 0x18 if self.is_raw_2352 else 0x00
        self.user_data_size = 2048
        self.file_table: Dict[str, ISOFileEntry] = {}
        self._read_iso9660_directory()

    def _detect_sector_size(self) -> int:
        with open(self.filepath, "rb") as f:
            header = f.read(16)
            if header.startswith(self.SYNC_PATTERN):
                return 2352
            # Check ISO 9660 PVD at 2048*16 = 32768
            f.seek(16 * 2048)
            pvd_check = f.read(6)
            if len(pvd_check) >= 6 and pvd_check[1:6] == b"CD001":
                return 2048
            # Check ISO 9660 PVD in 2352 format at 2352*16 = 37632
            f.seek(16 * 2352 + 0x18)
            pvd_raw = f.read(6)
            if len(pvd_raw) >= 6 and pvd_raw[1:6] == b"CD001":
                return 2352
        # Default to 2352 for PS1 BINs
        return 2352

    def read_sector(self, lba: int) -> bytearray:
        offset = lba * self.sector_size
        with open(self.filepath, "rb") as f:
            f.seek(offset)
            data = f.read(self.sector_size)
            if len(data) < self.sector_size:
                raise ValueError(f"Unexpected EOF reading LBA {lba}")
            return bytearray(data)

    def read_user_data_sector(self, lba: int) -> bytes:
        sector = self.read_sector(lba)
        return bytes(sector[self.user_data_offset : self.user_data_offset + self.user_data_size])

    def _read_iso9660_directory(self):
        """Parses the Primary Volume Descriptor (PVD) at LBA 16 and builds the file table."""
        pvd_sector = self.read_user_data_sector(16)
        if pvd_sector[1:6] != b"CD001":
            raise ValueError(f"Invalid ISO 9660 header on {self.filepath}")

        # Root directory record is at offset 156 (0x9C) in PVD, 34 bytes long
        root_record = pvd_sector[156 : 156 + 34]
        root_lba = struct.unpack_from("<I", root_record, 2)[0]
        root_size = struct.unpack_from("<I", root_record, 10)[0]

        self._parse_dir_recursive("", root_lba, root_size)

    def _parse_dir_recursive(self, current_path: str, lba: int, dir_size: int):
        num_sectors = (dir_size + 2047) // 2048
        dir_bytes = bytearray()
        for i in range(num_sectors):
            dir_bytes.extend(self.read_user_data_sector(lba + i))

        offset = 0
        while offset < len(dir_bytes):
            length = dir_bytes[offset]
            if length == 0:
                # Padding at end of sector, advance to next 2048 boundary
                next_boundary = ((offset // 2048) + 1) * 2048
                if next_boundary <= offset or next_boundary >= len(dir_bytes):
                    break
                offset = next_boundary
                continue

            record = dir_bytes[offset : offset + length]
            if len(record) < 33:
                offset += length
                continue

            file_lba = struct.unpack_from("<I", record, 2)[0]
            data_length = struct.unpack_from("<I", record, 10)[0]
            flags = record[25]
            name_len = record[32]
            name_bytes = record[33 : 33 + name_len]

            is_dir = bool(flags & 0x02)
            # Skip current '.' (0x00) and parent '..' (0x01)
            if name_bytes in (b"\x00", b"\x01"):
                offset += length
                continue

            name = name_bytes.decode("ascii", errors="replace").split(";")[0]
            full_path = f"{current_path}/{name}".lstrip("/")

            self.file_table[full_path.upper()] = ISOFileEntry(full_path, file_lba, data_length, is_dir)

            if is_dir:
                self._parse_dir_recursive(full_path, file_lba, data_length)

            offset += length

    def extract_file(self, internal_path: str) -> bytes:
        """Extracts the exact contents of an internal file (e.g. 'SLUS_014.11' or 'WA_MRG.MRG')."""
        key = internal_path.replace("\\", "/").strip("/").upper()
        if key not in self.file_table:
            # Try searching by basename if full path not found
            matching = [k for k in self.file_table if k.endswith(key) or k == key]
            if not matching:
                raise FileNotFoundError(f"File '{internal_path}' not found in ISO. Available: {list(self.file_table.keys())}")
            key = matching[0]

        entry = self.file_table[key]
        if entry.is_dir:
            raise ValueError(f"'{internal_path}' is a directory, not a file.")

        num_sectors = (entry.size + 2047) // 2048
        result = bytearray()
        for i in range(num_sectors):
            chunk = self.read_user_data_sector(entry.lba + i)
            result.extend(chunk)

        return bytes(result[:entry.size])

    def inject_file_in_place(self, internal_path: str, new_content: bytes, output_filepath: Optional[str] = None) -> str:
        """
        Injects modified file content in-place without shifting LBAs.
        If output_filepath is provided, writes to a new copy and leaves source intact.
        Recalculates EDC and ECC for all modified sectors.
        """
        key = internal_path.replace("\\", "/").strip("/").upper()
        if key not in self.file_table:
            matching = [k for k in self.file_table if k.endswith(key) or k == key]
            if not matching:
                raise FileNotFoundError(f"File '{internal_path}' not found in ISO.")
            key = matching[0]

        entry = self.file_table[key]
        allocated_capacity = ((entry.size + 2047) // 2048) * 2048
        if len(new_content) > allocated_capacity:
            raise ValueError(f"New content size ({len(new_content)} bytes) exceeds allocated space ({allocated_capacity} bytes).")

        target_file = output_filepath if output_filepath else self.filepath
        if output_filepath and output_filepath != self.filepath:
            import shutil
            shutil.copyfile(self.filepath, output_filepath)

        # Pad new_content up to sector boundary with zeroes
        padded_content = bytearray(new_content)
        while len(padded_content) % 2048 != 0:
            padded_content.append(0)

        num_sectors = len(padded_content) // 2048

        with open(target_file, "r+b") as f:
            for i in range(num_sectors):
                lba = entry.lba + i
                sec_offset = lba * self.sector_size
                chunk = padded_content[i * 2048 : (i + 1) * 2048]

                if self.is_raw_2352:
                    f.seek(sec_offset)
                    sector_raw = bytearray(f.read(2352))
                    if sector_raw[0x18 : 0x818] == chunk:
                        continue
                    # Overwrite user data
                    sector_raw[0x18 : 0x818] = chunk
                    # Recalculate EDC/ECC
                    encode_mode2_form1_sector(sector_raw)
                    # Write back
                    f.seek(sec_offset)
                    f.write(sector_raw)
                else:
                    # ISO 2048 mode
                    f.seek(sec_offset)
                    f.write(chunk)

        return target_file

    def inject_files_in_place(self, files_dict: Dict[str, bytes], output_filepath: Optional[str] = None) -> str:
        """
        Injects multiple modified files into the disc image in a single pass.
        Copies the base disc image once, then updates each file's sectors and recalculates EDC/ECC.
        """
        target_file = output_filepath if output_filepath else self.filepath
        if output_filepath and output_filepath != self.filepath:
            import shutil
            shutil.copyfile(self.filepath, output_filepath)

        with open(target_file, "r+b") as f:
            for internal_path, new_content in files_dict.items():
                key = internal_path.replace("\\", "/").strip("/").upper()
                if key not in self.file_table:
                    matching = [k for k in self.file_table if k.endswith(key) or k == key]
                    if not matching:
                        raise FileNotFoundError(f"File '{internal_path}' not found in ISO.")
                    key = matching[0]

                entry = self.file_table[key]
                allocated_capacity = ((entry.size + 2047) // 2048) * 2048
                if len(new_content) > allocated_capacity:
                    raise ValueError(f"New content size for {key} ({len(new_content)} bytes) exceeds allocated space ({allocated_capacity} bytes).")

                padded_content = bytearray(new_content)
                while len(padded_content) % 2048 != 0:
                    padded_content.append(0)

                num_sectors = len(padded_content) // 2048
                for i in range(num_sectors):
                    lba = entry.lba + i
                    sec_offset = lba * self.sector_size
                    chunk = padded_content[i * 2048 : (i + 1) * 2048]

                    if self.is_raw_2352:
                        f.seek(sec_offset)
                        sector_raw = bytearray(f.read(2352))
                        if sector_raw[0x18 : 0x818] == chunk:
                            continue
                        sector_raw[0x18 : 0x818] = chunk
                        encode_mode2_form1_sector(sector_raw)
                        f.seek(sec_offset)
                        f.write(sector_raw)
                    else:
                        f.seek(sec_offset)
                        f.write(chunk)

        return target_file
