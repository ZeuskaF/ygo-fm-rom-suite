# Yu-Gi-Oh! Forbidden Memories ROM Suite & Recompilador de ISOs 🎮⚔️

[![Versión de Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Licencia: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Estado de Pruebas](https://img.shields.io/badge/pruebas-53%20aprobadas-brightgreen.svg)](tests/)
[![Plataforma](https://img.shields.io/badge/plataforma-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()
[![Disco PS1](https://img.shields.io/badge/formatos-ISO%20%7C%20BIN%20%7C%20CUE-red.svg)]()

> **Idiomas:** [🇬🇧 English](README.md) | [🇪🇸 Español](README_ES.md)

Herramienta profesional e independiente de ingeniería inversa, edición y recompilación de imágenes de disco para **Yu-Gi-Oh! Forbidden Memories** (PlayStation 1, `SLUS-01411` / `SLES-03951`). Permite inspeccionar, balancear, modificar y recompilar cada aspecto del juego sin necesidad de programas externos de manejo de imágenes de disco.

---

## 🌟 Características Principales

### 1. 🎴 Editor Visual Completo de Cartas (001 a 722)
- **Edición de Parámetros en Tiempo Real:** Modifica ATK, DEF, 24 tipos de carta oficiales (incluyendo Magia, Trampa y Ritual), Estrellas Guardias Primaria y Secundaria, contraseñas BCD de 8 dígitos y coste en Estrellas (Star Chips).
- **Editor de Nombres de Cartas:** Permite modificar nombres de cartas con codificación dinámica y soporte completo de caracteres y signos.
- **Motor Auténtico de Descripciones y Glifos de Tipo:** Decodificación y codificación nativa de secuencias de escape de 3 bytes de PS1 (`0xF8 0x0B <type_id>`). Permite insertar íconos gráficos directamente en el texto mediante etiquetas legibles como `[Bestia]`, `[Guerrero]`, `[Dragón]`, `[Lanzador de Conjuros]`, o sus equivalentes en inglés (`[Beast]`, `[Warrior]`, etc.).

### 2. 🎨 Gráficos de Cartas e Ingestión de Arte Personalizado
- **Extracción de Texturas TIM:** Extrae texturas originales de 16 bits BGR555 directamente de `DATA/CARD_TEX.MRG`.
- **Ingestión de Arte Personalizado:** Importa cualquier imagen en formato PNG, JPEG o WEBP. El motor ajusta la relación de aspecto, escala la imagen y convierte la paleta al formato nativo BGR555 de PS1 de forma transparente.
- **Renderizador Visual de Alta Resolución:** Vista previa en tiempo real con marcos auténticos de carta (Monstruo, Ritual, Magia, Trampa), estrellas de nivel, insignias de tipo y maquetación de texto. Permite exportar cartas renderizadas en imágenes PNG en alta calidad.

### 3. ⚡ Motor de Fusiones Simétrico a Nivel MIPS
- **Fiel a la CPU MIPS de PS1:** Replica la lógica del comparador de la CPU MIPS R3000 (`0x80019a68`), garantizando que la fusión funcione independientemente de qué carta se seleccione en primer lugar.
- **Empaquetado Seguro de 64 KB por Sector:** Graba las tablas de fusión en `DATA/WA_MRG.MRG` en el sector 5903 (`0x0B87800`) a través de las 7 arenas de combate, acotadas estrictamente a 65,536 bytes para no sobrescribir las texturas TIM de la arena adyacente en el sector 34.
- **Importador de Fusiones de Dream Mod en 1 Clic:** Importa más de 31,500 recetas de fusión avanzadas provenientes de mods populares (*Dream Mod 15x*) con un solo botón.

### 4. 🎲 Sistema Auténtico de 7 Pools del Mazo Inicial
- **Overlay Auténtico de la Pantalla de Nombre (Name Entry):** Lee y escribe directamente en el sector 7983 (`0x00F97800`) de `DATA/WA_MRG.MRG`, donde el motor del juego en la PS1 genera los 40 naipes iniciales del jugador.
- **7 Pools de Probabilidad Independientes:** Cada pool cuenta con una suma estricta de 2,048 pesos:
  - **Pool 0:** Monstruos Menores (16 extracciones)
  - **Pool 1:** Monstruos Medios (16 extracciones)
  - **Pool 2:** Monstruos Fuertes (4 extracciones)
  - **Pool 3:** Monstruos Clave / Jefes (1 extracción)
  - **Pool 4:** Magias de Limpieza (Raigeki / Dark Hole - 1 extracción)
  - **Pool 5:** Magias de Campo (Forest, Wasteland, Mountain, Sogen, Umi, Yami - 1 extracción)
  - **Pool 6:** Magias de Equipo (1 extracción)
- **Probabilidades Exactas:** Cálculo en tiempo real de probabilidad combinada de Poisson/Bernoulli en 40 cartas ($P(\ge 1) = 1 - \prod_{p=0}^6 (1 - w_p / 2048)^{\text{draws}_p}$).
- **Presets Rápidos:** Botones de asignación instantánea al 25%, 50% y **100% Garantizada** en el mazo inicial.

### 5. 🌌 Personalizador de Magias de Campo y Tablero 3D
- **Parámetros de Campos:** Personaliza bonificaciones y reducciones de ATK/DEF para los 6 campos (Bosque, Yermo, Montaña, Pradera, Mar, Yami).
- **Ajuste de Color en Arenas 3D:** Modifica la tonalidad RGB y luz ambiental de las arenas de duelo.
- **Visualizador 3D Interactivo:** Representación visual en tiempo real de la cuadrícula de batalla con colocación de monstruos, fondos de campo y efectos de atmósfera.
- **Gestor de Presets:** Exporta e importa configuraciones personalizadas en formato JSON.

### 6. ⚔️ Mazos de Duelistas y Dificultad IA (39 Rivales)
- **Edición de Mazos:** Modifica la baraja completa de 40 cartas de los 39 duelistas del juego (desde Simon Muran y Jono hasta Heishin, Seto 3.º y Nitemare).
- **Selector de Agresividad IA:** Ajusta el porcentaje de fusiones y toma de decisiones tácticas de la IA del 0% al 100%.

### 7. 🏆 Tablas de Drop y Buscador Inverso
- **Inspección de Calificaciones:** Visualiza y edita los drops en los 4 rangos oficiales: **SA-POW**, **BCD-POW**, **SA-TEC** y **BCD-TEC**.
- **Auto-Normalización a 2,048:** Mantiene el balance matemático estricto exigido por la tabla de números pseudoaleatorios (PRNG) de Konami.
- **Buscador Inverso ("¿Quién da esta carta?"):** Busca cualquier carta para conocer de inmediato qué rivales la entregan, en qué rango y con qué porcentaje exacto.
- **Guía de Calificaciones:** Explicación técnica integrada sobre cómo el juego califica turnos, fusiones, cartas restantes y trampas activadas para otorgar las letras de rango.

### 8. 🎁 Motor de Recompensas Universal (Drop x1 a Drop x100)
- **Pantalla de Victoria Libre de Bloqueos:** Reemplaza códigos frágiles de ensamblador por inyección directa al baúl en memoria (`0x801db430`) y retorno seguro al epílogo de cuadro (`0x8002209c`).
- **Disparador de Audio Anti-Softlock:** Limpia automáticamente la bandera de desvanecimiento de sonido post-duelo, eliminando cuelgues y pantallas negras en cualquier juego o mod (Vanilla, Dream Mod, Mod 11, etc.).
- **Multiplicador Ajustable:** Configura la entrega de cartas de 1 a 100 cartas por victoria.

### 9. 💿 Recompilador Quirúrgico y Autónomo de Discos
- **Reconstrucción de Sectores Modo 2 Forma 1:** Inyección atómica a bajo nivel con recálculo exacto de **EDC (CRC32)** y paridades **Reed-Solomon L-EC (P/Q)**.
- **Compilación Autónoma:** Contiene datos canónicos que permiten generar una imagen funcional de disco sin depender de una ISO base.
- **Fusión Quirúrgica:** Extrae y fusiona selectivamente subsistemas (solo cartas, solo fusiones o solo gráficos) entre diferentes imágenes de disco.
- **Listo para Hardware y Emuladores:** Exporta archivos `.iso`, `.bin` y `.cue` compatibles con DuckStation, ePSXe, RetroArch y consolas reales PS1 mediante emuladores de unidad óptica (xStation, PSIO).

---

## 📂 Estructura del Repositorio

```
ygo_fm_rom_suite/
├── Iniciar_Suite.bat          # Lanzador para Windows (Español)
├── Launch_Suite.bat           # Lanzador para Windows (Inglés)
├── launch_suite.sh            # Lanzador para Linux y macOS
├── main.py                    # Enrutador principal (GUI / CLI)
├── requirements.txt           # Dependencias de Python (Pillow, pytest)
├── LICENSE                    # Licencia MIT
├── README.md                  # Documentación en Inglés
├── README_ES.md               # Documentación en Español
├── docs/                      # Guías técnicas detalladas
│   ├── ARCHITECTURE.md        # Arquitectura técnica y offsets del disco PS1 (EN)
│   └── ARQUITECTURA_ES.md     # Arquitectura técnica y offsets del disco PS1 (ES)
├── core/                      # Núcleo de modificación y recompilación
│   ├── cards.py               # Serializador de 722 cartas y decodificador de glifos
│   ├── card_data.py           # Constantes canónicas de tipos, estrellas y atributos
│   ├── canonical_card_names.py# Diccionario oficial de nombres de cartas
│   ├── card_graphics.py       # Extractor e inyector de texturas TIM BGR555
│   ├── card_renderer.py       # Motor gráfico de renderizado de cartas en HD
│   ├── cdrom.py               # Motor de sectores CD-ROM ISO-9660 Modo 2 Forma 1
│   ├── builder.py             # Recompilador de disco y generador de paridades EDC/ECC
│   ├── fusions.py             # Base de datos y sincronizador de 7 arenas de fusión
│   ├── decks.py               # Mazos de duelistas y dificultad de la IA
│   ├── drops.py               # Tablas de recompensas, búsqueda inversa y normalizador
│   ├── starter_deck.py        # Motor de probabilidades de los 7 pools del mazo inicial
│   ├── starter_deck_data.py   # Datos base64 de pools vanilla y respaldo
│   ├── field_spells.py        # Modificadores de magias de campo y paletas de color
│   ├── duel_board_renderer.py # Visualizador interactivo 3D del campo de duelo
│   ├── engine_patches.py      # Parches Drop x100, baúl e inyección anti-bloqueo
│   ├── mips_engine.py         # Desensamblador MIPS R3000A y escáner de patrones AOB
│   └── merger.py              # Motor quirúrgico de fusión entre 2 imágenes ISO
├── ui/                        # Módulos de interfaz de usuario
│   ├── gui.py                 # Interfaz gráfica moderna en Tkinter (tema oscuro)
│   └── cli.py                 # Interfaz de línea de comandos para automatización
└── tests/                     # Suite de pruebas automatizadas (53 tests)
    ├── test_cards.py          # Pruebas de serialización de cartas y glifos
    ├── test_card_graphics.py  # Pruebas de conversión BGR555 e ingesta de arte
    ├── test_card_renderer.py  # Pruebas de renderizado visual de cartas
    ├── test_fusions.py        # Pruebas de simetría MIPS y límites de tabla
    ├── test_starter_deck.py   # Pruebas de pools e inyección en WA_MRG
    ├── test_field_spells.py   # Pruebas de magias de campo y presets JSON
    ├── test_drops.py          # Pruebas de normalización y búsqueda inversa
    ├── test_drop_multipliers.py # Pruebas de rango del multiplicador de drops
    ├── test_drop_recompile.py # Pruebas de integración de recompilación de drops
    ├── test_builder.py        # Pruebas de reconstrucción de sectores e inyección
    ├── test_standalone_builder.py # Pruebas de compilación sin ISO de origen
    ├── test_dream_merge_compile.py # Pruebas de integración de fusión quirúrgica
    ├── test_cdrom.py          # Pruebas de cálculo EDC CRC32 y Reed-Solomon
    ├── test_mips_engine.py    # Pruebas del desensamblador y escáner AOB
    └── test_gui_smoke.py      # Prueba de inicialización de la GUI
```

---

## 🚀 Instalación y Puesta en Marcha

### Requisitos Previos
- **Python 3.10** o superior.
- Sistema Operativo: Windows 10/11, Linux (Ubuntu, Debian, Fedora, Arch) o macOS.

### Pasos de Instalación

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/tu-usuario/ygo-fm-rom-suite.git
   cd ygo-fm-rom-suite
   ```

2. **Instalar dependencias requeridas:**
   ```bash
   pip install -r requirements.txt
   ```

---

## 💻 Guía de Uso

### Interfaz Gráfica (Recomendada)

- **En Windows:** Haz doble clic en `Iniciar_Suite.bat` (o `Launch_Suite.bat`).
- **En Linux / macOS:** Ejecuta:
  ```bash
  chmod +x launch_suite.sh
  ./launch_suite.sh
  ```
- **Desde la Terminal:**
  ```bash
  python main.py
  ```

#### Flujo de Trabajo Básico:
1. Haz clic en **`📂 Cargar ISO / BIN`** y selecciona tu copia del juego (`SLUS_014.11` vanilla o cualquier mod).
2. *(Opcional)* Haz clic en **`📥 Importar Mod`** si deseas transferir fusiones o cartas desde otro disco (por ejemplo, Dream Mod 15x).
3. Modifica cartas, recetas de fusión, drops, pools del mazo inicial o magias de campo.
4. En la pestaña **⚙️ Motor y Recompensas**, elige tu multiplicador de drops deseado (por ejemplo, Drop x5, Drop x15, Drop x100).
5. Pulsa **`⚡ GENERAR NUEVA ROM / ISO COMPILADA ⚡`** para exportar tu disco listo para jugar.

---

### Modo de Línea de Comandos (CLI)

Ideal para servidores, entornos automatizados y scripts de integración continua:

```bash
# Mostrar ayuda de comandos disponibles
python main.py --help

# Recompilar una ISO aplicando un multiplicador de Drop x15
python main.py compile --source "VanillaExpress.iso" --output "Modificado.iso" --drops 15

# Exportar la base de datos de cartas a JSON
python main.py export-cards --source "VanillaExpress.iso" --output "cartas.json"

# Fusionar recetas de un mod dentro de una imagen limpia
python main.py merge-fusions --source "VanillaExpress.iso" --mod "DreamMod.iso" --output "Fusionado.iso"
```

---

## 🧪 Pruebas y Validación

La suite incluye 53 pruebas automatizadas que verifican la exactitud matemática de las paridades EDC/ECC, la simetría de fusiones en MIPS y la reconstrucción de sectores:

```bash
python -m pytest -v
```

```text
============================= 53 passed in 33.03s =============================
```

---

## 📖 Documentación Técnica Avanzada

Para consultar especificaciones completas de los sectores de disco, mapas de memoria RAM de la PS1, rutinas MIPS y fórmulas de probabilidad:
- [Guía de Arquitectura (Español)](docs/ARQUITECTURA_ES.md)
- [Architecture Guide (English)](docs/ARCHITECTURE.md)

---

## 🤝 Cómo Contribuir

¡Agradecemos enormemente las contribuciones de la comunidad! Consulta el archivo [CONTRIBUTING.md](CONTRIBUTING.md) para conocer las pautas de estilo de código, formato de pull requests y estándares de pruebas.

---

## ⚖️ Licencia y Descargo de Responsabilidad

Este proyecto se publica bajo la **[Licencia MIT](LICENSE)**.

**Descargo de Responsabilidad:** *Yu-Gi-Oh!* y *Yu-Gi-Oh! Forbidden Memories* son marcas comerciales registradas de Konami Digital Entertainment y Kazuki Takahashi. Esta suite es una herramienta de investigación e ingeniería inversa desarrollada para preservación de software y creación de contenido bajo los principios de uso legítimo. Este repositorio **no distribuye** ningún archivo de juego con derechos de autor ni copias de ROMs comerciales.
