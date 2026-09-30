"""
Unit tests verifying that the drop engine multiplier can be safely changed
from 100 to any custom number (1, 5, 10, 15, 50, 100) and remains fully functional.
"""

import pytest
from core.engine_patches import EnginePatchManager
from core.mips_engine import MIPSInstruction
import struct


def test_custom_drop_multipliers_mips():
    # Base executable buffer of 2 MB with PS-X EXE header
    base_exe = bytearray(b"PS-X EXE" + bytes(0x1CC800 - 8))

    test_multipliers = [1, 5, 10, 15, 25, 50, 100]

    for mult in test_multipliers:
        exe = bytearray(base_exe)
        patches = EnginePatchManager.apply_drop_engine(
            target_exe=exe,
            express_exe=None,
            drop_multiplier=mult
        )

        assert patches >= 6

        # Check memory integrity
        integrity = EnginePatchManager.validate_memory_integrity(bytes(exe), bytes())
        assert integrity["audio_queue_trigger_ok"] is True
        assert integrity["post_duel_hook_ok"] is True
        assert integrity["victory_hook_ok"] is True
        assert integrity["victory_return_ok"] is True
        assert integrity["dispatcher_present"] is True
        assert integrity["block2_payload_loader_ok"] is True
        assert integrity["drop_multiplier"] == mult
        assert integrity["drop_multiplier_valid"] is True

        # Check that the MIPS immediate at 0x0021C0 is exactly mult
        assert exe[0x0021C0] == mult


def test_drop_multiplier_clamping():
    base_exe = bytearray(b"PS-X EXE" + bytes(0x1CC800 - 8))

    # Test values below 1 clamped to 1
    exe_low = bytearray(base_exe)
    EnginePatchManager.apply_drop_engine(exe_low, None, drop_multiplier=0)
    assert exe_low[0x0021C0] == 1

    # Test values above 100 clamped to 100
    exe_high = bytearray(base_exe)
    EnginePatchManager.apply_drop_engine(exe_high, None, drop_multiplier=999)
    assert exe_high[0x0021C0] == 100
