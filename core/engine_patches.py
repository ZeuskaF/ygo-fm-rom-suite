"""
Engine Patches and Gameplay Modifiers for Yu-Gi-Oh! Forbidden Memories.

ARQUITECTURA DE HOMOLOGACIÓN DESDE VANILLA EXPRESS + IA DREAM MOD:
  - Base: Dream Mod (preserva intactas las 84 áreas de IA, saltos MIPS, combos, 3D y modo historia).
  - Integración nativa del Drop Engine de Vanilla Express (1 a 100 cartas):
    1. Base del motor de drops y variables (0x0021B0..0x002278).
    2. Despachador de memoria de Vanilla Express (0x1CBC30..0x1CBC98 -> 0x801db430).
    3. Payload de código intercalado (0x1CBF60..0x1CC020 -> 0x801db760).
    4. Función 2 de depósito en baúl (0x1CC730..0x1CC7A4 -> 0x801dbf30).
    5. Disparador 1 (Post-duel roll, 0x012460..0x01248C):
       Llama al despachador y preserva el disparador de audio 0x0602 en 0x5708($v1)
       para que el driver de sonido del Dream Mod limpie el flag de fadeout y no se congele.
    6. Disparador 2 (Victory chest & reward display, 0x012710..0x012724):
       Llama al despachador para acreditar las cartas en el baúl y retorna limpiamente a 0x8002209c.
    7. Multiplicador de drops configurable (0x0021C0: 1 a 100 cartas).
    8. Preservación del bono de 50 starchips del Dream Mod (0x0126DC).
    9. Preservación íntegra de los sistemas de diálogo (0x0155C8), GPU (0x002B30)
       y tablas de probabilidad de drop (0x19B440..0x19B700).
"""

import struct
from typing import Optional


class EnginePatchManager:
    """
    Gestiona la aplicación y homologación de parches entre Vanilla Express y Dream Mod.
    """

    # Regiones del motor de drops de Vanilla Express que se integran en el ejecutable
    _DROP_ENGINE_REGIONS = [
        # (offset_inicio, offset_fin, descripcion)
        (0x0021B0, 0x002278, "Drop engine base, slots y despachador de función 1"),
        (0x1CBC30, 0x1CBC98, "Dispatcher 0x801db430"),
        (0x1CBF60, 0x1CC020, "Payload de código intercalado 0x801db760"),
        (0x1CC730, 0x1CC7A4, "Función 2 despachador baúl 0x801dbf30"),
    ]

    # Bytecode estático embebido del motor de Vanilla Express (Drop x100 y Dispatcher).
    # Permite inyectar el motor en CUALQUIER mod sin necesidad de poseer el ISO de Vanilla Express.
    STANDALONE_DROP_ENGINE_PAYLOADS = {
        0x0021B0: bytes.fromhex(
            "696d656f75740a002449643a20696e74640000007620312e373520313939372f"
            "00322f30372030393a30303a3336206d001a01806f20457870202400756e6578"
            "30bf1d80656420696e746572727570741e80013c60b72124000021240180023c"
            "601b422400000324c00004240000259000000000000045a00000000002006324"
            "0200212401004224f8ff6414000000000180023cb01942240800448c00000000"
            "0180013cd019212401000224000022a0000000000180023c601b42241e6d0708"
            "0000000000000000"
        ),
        0x1CBC30: bytes.fromhex(
            "0180023cb0194224000041ac040043ac080044ac0c0045ac0180013cd0192124"
            "000021900180033c03002010e01963240180033cf01963240000638c00000000"
            "080060000000000008004000000000000180023cb01942240000418c0400438c"
            "0800448c0800a000"
        ),
        0x1CBF60: bytes.fromhex(
            "0101808001053c3c00000000100024000001000000010024c01e19802305903c"
            "b84e19bb24a58c240021002800a100000b21002870a110000000000000a40084"
            "0400860000000c00002500860000000c1e00800001003c005001bb802105243c"
            "21c0081930a2009021ff08003042003000f400ff2241a4140101800001213c24"
            "f201ff800005103c01b0001910a1268c000200801005243c021c801f05a53c24"
            "68201c6da507240820006d00070008001000800001003c000000000000000000"
        ),
        0x1CC730: bytes.fromhex(
            "1e80013c60b72124010021240180023c601b422400000324c000042400002590"
            "00000000000045a000000000020063240200212401004224f8ff641400000000"
            "0180023cb01942240800448c000000000180013cd019212400000224000022a0"
            "000000000180023c601b42241e6d070800000000"
        ),
    }

    @staticmethod
    def apply_drop_engine(
        target_exe: bytearray,
        express_exe: Optional[bytes] = None,
        drop_multiplier: int = 100
    ) -> int:
        """
        Aplica el motor de drops de Vanilla Express sobre el ejecutable base (Dream Mod u otro),
        preservando los disparadores de audio, pantalla de victoria y diálogo del mod.

        Si express_exe es None, utiliza el bytecode embebido autónomo sin requerir
        el archivo ISO de Vanilla Express.
        """
        patches_applied = 0

        # 1. Copiar las regiones nucleares del motor de drops
        for start, end, desc in EnginePatchManager._DROP_ENGINE_REGIONS:
            if len(target_exe) >= end:
                if express_exe is not None and len(express_exe) >= end:
                    target_exe[start:end] = express_exe[start:end]
                elif start in EnginePatchManager.STANDALONE_DROP_ENGINE_PAYLOADS:
                    payload = EnginePatchManager.STANDALONE_DROP_ENGINE_PAYLOADS[start]
                    target_exe[start:start + len(payload)] = payload
                patches_applied += 1


        # 2. Configurar Disparador 1: Post-duel roll hook (0x012460..0x01248C)
        # Salta al despachador de Vanilla Express para rodar las N cartas.
        # CRÍTICO PARA EVITAR SOFTLOCK: Preserva 'li $a1, 0x0602' y 'sw $a1, 0x5708($v1)'
        # del Dream Mod para que el driver de sonido inicie la música de victoria y
        # limpie el flag de fadeout (bit 7 de 0x800F9ECE). Sin esto el juego queda
        # congelado esperando indefinidamente.
        if len(target_exe) >= 0x01248C:
            hook1 = struct.pack(
                '<12I',
                0x08076D0C,  # 0x012460: j 0x801DB430 (Dispatcher Vanilla Express)
                0x00000000,  # 0x012464: nop
                0x8F8402E0,  # 0x012468: lw $a0, 0x02E0($gp)
                0x3C03801D,  # 0x01246C: lui $v1, 0x801D
                0x3C01800A,  # 0x012470: lui $at, 0x800A
                0xA422B338,  # 0x012474: sh $v0, -0x4CC8($at)
                0xA482003C,  # 0x012478: sh $v0, 0x003C($a0)
                0x24050602,  # 0x01247C: li $a1, 0x0602 (Audio Victory Theme Dream Mod)
                0xAC655708,  # 0x012480: sw $a1, 0x5708($v1) (Disparador de audio para limpiar fadeout)
                0xAC6256A8,  # 0x012484: sw $v0, 0x56A8($v1)
                0x9082003A,  # 0x012488: lbu $v0, 0x003A($a0)
                0x00000000,  # 0x01248C: nop
            )
            target_exe[0x012460:0x012460 + len(hook1)] = hook1
            patches_applied += 1

        # 3. Configurar Disparador 2: Victory chest deposit & screen return (0x012710..0x012724)
        # Salta al despachador para acreditar las cartas al baúl y sale limpiamente a 0x8002209c
        if len(target_exe) >= 0x012724:
            hook2 = struct.pack(
                '<5I',
                0x8444003C,  # 0x012710: lh $a0, 0x003C($v0)
                0x08076D0C,  # 0x012714: j 0x801DB430 (Dispatcher)
                0x00000000,  # 0x012718: nop
                0x08008827,  # 0x01271C: j 0x8002209C (return limpio a epílogo de frame)
                0x00000000,  # 0x012720: nop
            )
            target_exe[0x012710:0x012710 + len(hook2)] = hook2
            patches_applied += 1

        # 4. Preservar bono de 50 starchips del Dream Mod en la pantalla de victoria
        if len(target_exe) >= 0x0126E0:
            target_exe[0x0126DC:0x0126E0] = (0x24630032).to_bytes(4, "little")
            patches_applied += 1

        # 5. Configurar multiplicador de drops (1 a 100 cartas)
        drop_count = max(1, min(100, drop_multiplier))
        if len(target_exe) > 0x21C0:
            target_exe[0x21C0] = drop_count & 0xFF
            patches_applied += 1

        # 6. Reiniciar variable de estado del despachador
        if len(target_exe) > 0x21D0:
            target_exe[0x21D0] = 0x00
            patches_applied += 1

        # 7. Asegurar que el desentrelazador de Función 2 no esté truncado
        # 0x1CC748 debe ser 0x240400C0 (li $a0, 0xC0 = 192 bytes payload completos)
        if len(target_exe) >= 0x1CC74C:
            target_exe[0x1CC748:0x1CC74C] = (0x240400C0).to_bytes(4, "little")
            patches_applied += 1

        return patches_applied

    @staticmethod
    def import_cpu_difficulty_and_ai(target_exe: bytearray, mod_exe: bytes) -> int:
        """Sincroniza la tabla de dificultad de 39 duelistas si es necesario."""
        patches = 0
        diff_start = 0x082090
        diff_end = 0x082120
        if len(target_exe) >= diff_end and len(mod_exe) >= diff_end:
            target_exe[diff_start:diff_end] = mod_exe[diff_start:diff_end]
            patches += 1
        return patches

    @staticmethod
    def clear_ai_scratch_state(target_exe: bytearray) -> int:
        """Limpia el área scratchpad previa para un inicio seguro entre duelos."""
        if len(target_exe) >= 0x19B440:
            target_exe[0x19B400:0x19B440] = bytes(64)
            return 1
        return 0

    @staticmethod
    def validate_memory_integrity(target_exe: bytes, express_exe: bytes) -> dict:
        """
        Valida que todos los segmentos de victoria, renderizado y drops cumplan
        con la arquitectura segura sin congelamientos.
        """
        results = {}

        # 1. Disparador de audio post-duelo para evitar softlock
        a_inst = struct.unpack_from('<I', target_exe, 0x012480)[0]
        results["audio_queue_trigger_ok"] = (a_inst == 0xAC655708)

        # 2. Hook 1 post-duelo apunta a dispatcher (0x801db430)
        p_hook = struct.unpack_from('<I', target_exe, 0x012460)[0]
        results["post_duel_hook_ok"] = (p_hook == 0x08076D0C)

        # 3. Hook 2 de victoria apunta a dispatcher (0x801db430)
        v_hook = struct.unpack_from('<I', target_exe, 0x012714)[0]
        results["victory_hook_ok"] = (v_hook == 0x08076D0C)

        # 4. Salida de victoria correcta a epílogo (j 0x8002209c)
        v_ret = struct.unpack_from('<I', target_exe, 0x01271C)[0]
        results["victory_return_ok"] = (v_ret == 0x08008827)

        # 5. Despachador de Vanilla Express presente
        d_inst = struct.unpack_from('<I', target_exe, 0x1CBC30)[0]
        results["dispatcher_present"] = (d_inst == 0x3C028001)

        # 6. Desentrelazador de Función 2 completo (0xC0 bytes)
        b2_inst = struct.unpack_from('<I', target_exe, 0x1CC748)[0]
        results["block2_payload_loader_ok"] = (b2_inst == 0x240400C0)

        # 7. Motor de diálogo preservado (no roto por Vanilla)
        d_box = struct.unpack_from('<I', target_exe, 0x0155C8)[0]
        results["dialog_engine_preserved"] = (d_box == 0x3C02801E)

        # 8. Renderizado GPU preservado (no roto por Vanilla)
        gpu_inst = struct.unpack_from('<I', target_exe, 0x002B40)[0]
        results["gpu_buffers_preserved"] = (gpu_inst == 0x3C0200F1)

        # 9. Bono de 50 starchips de Dream Mod preservado
        sc_inst = struct.unpack_from('<I', target_exe, 0x0126DC)[0]
        results["starchip_bonus_preserved"] = (sc_inst == 0x24630032)

        # 10. Multiplicador de drops válido
        if len(target_exe) > 0x21C0:
            results["drop_multiplier"] = target_exe[0x21C0]
            results["drop_multiplier_valid"] = (1 <= target_exe[0x21C0] <= 100)

        # 11. Rutinas nativas de Dream Mod preservadas en 0x19B440 (no borradas a ceros)
        dm_routine = struct.unpack_from('<I', target_exe, 0x19B440)[0]
        results["dream_routines_preserved"] = (dm_routine != 0)

        return results

    @staticmethod
    def validate_full_build(exe_bytes: bytes, wa_bytes: bytes) -> dict:
        """
        Validación exhaustiva pre-compilación:
          1. Cabecera PS-X EXE
          2. Integridad de hooks de victoria y despachador
          3. Sincronización y consistencia de tablas de drop (39 duelistas)
        """
        results = EnginePatchManager.validate_memory_integrity(exe_bytes, bytes())
        results["ps1_exe_header_valid"] = (exe_bytes[:8] == b"PS-X EXE")
        results["exe_size_sufficient"] = (len(exe_bytes) >= 0x1CC800)

        # Validar tablas de drop en WA_MRG
        DROP_BASE = 0x00E9B000
        STRIDE = 0x1800
        if len(wa_bytes) >= DROP_BASE + 39 * STRIDE:
            is_16bit = False
            if len(exe_bytes) >= 0x01205C:
                is_16bit = (struct.unpack_from('<I', exe_bytes, 0x012058)[0] == 0x96020000)

            results["drop_format_16bit"] = is_16bit
            valid_duelists = 0
            for d in range(39):
                base = DROP_BASE + d * STRIDE
                if is_16bit:
                    p_sums = [
                        sum(struct.unpack_from('<722H', wa_bytes, base + off))
                        for off in [0x0000, 0x05B4, 0x0B68, 0x111C]
                    ]
                else:
                    p_sums = [
                        sum(wa_bytes[base + off : base + off + 722])
                        for off in [0x0000, 0x02D2, 0x05B4, 0x0886]
                    ]
                if p_sums == [2048, 2048, 2048, 2048]:
                    valid_duelists += 1

            results["duelist_drop_pools_valid"] = (valid_duelists == 39)
            results["valid_drop_duelists_count"] = valid_duelists
        else:
            results["duelist_drop_pools_valid"] = False

        return results

