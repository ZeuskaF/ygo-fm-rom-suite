# Contributing to Yu-Gi-Oh! Forbidden Memories ROM Suite 🤝

[ English ](CONTRIBUTING.md#english) | [ Español ](CONTRIBUTING.md#español)

---

<a name="english"></a>
## 🇬🇧 English

Thank you for your interest in contributing to the **Yu-Gi-Oh! Forbidden Memories ROM Suite**! We welcome bug reports, feature suggestions, documentation enhancements, and pull requests.

### Development Setup
1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/your-username/ygo-fm-rom-suite.git
   cd ygo-fm-rom-suite
   ```
2. **Install requirements:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Run the test suite:**
   ```bash
   python -m pytest -v
   ```
   Ensure all 53 tests pass before introducing changes.

### Coding Standards
- **Python 3.10+ Compatibility:** Code must execute on Python 3.10 through 3.13 without warnings.
- **Pure Python & Minimal Dependencies:** Avoid adding external binary C-extensions or heavy third-party packages. Core algorithms (EDC/ECC, MIPS parsing, ISO extraction) must remain lightweight and portable.
- **Memory & Disc Bounds Safety:** All modifications to PS1 disc structures must strictly enforce sector boundaries (e.g. 64 KB limits for fusion tables, 2048-weight pool balances, EDC CRC32 and Reed-Solomon recalculation).
- **Automated Tests:** Add unit tests under `tests/` for any new parser, feature, or bug fix.

### Submitting a Pull Request
1. Create a dedicated branch: `git checkout -b feature/my-new-feature` or `bugfix/issue-description`.
2. Commit with clear, descriptive commit messages.
3. Verify that `pytest` passes with 100% success.
4. Open a Pull Request detailing your changes and test results.

---

<a name="español"></a>
## 🇪🇸 Español

¡Gracias por tu interés en contribuir a la **Yu-Gi-Oh! Forbidden Memories ROM Suite**! Aceptamos reportes de bugs, sugerencias de nuevas funciones, mejoras en documentación y pull requests.

### Configuración del Entorno
1. **Haz un fork y clona el repositorio:**
   ```bash
   git clone https://github.com/tu-usuario/ygo-fm-rom-suite.git
   cd ygo-fm-rom-suite
   ```
2. **Instala las dependencias:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Ejecuta la suite de pruebas:**
   ```bash
   python -m pytest -v
   ```
   Verifica que todas las 53 pruebas pasen correctamente antes de comenzar a editar.

### Estándares de Código
- **Compatibilidad con Python 3.10+:** El código debe ser compatible con Python 3.10 a 3.13 sin advertencias.
- **Dependencias Ligeras:** Mantén el núcleo en Python estándar y librerías portables (como Pillow). Evita añadir dependencias binarias pesadas.
- **Seguridad en Límites de Memoria y Sectores:** Toda modificación en estructuras de PS1 debe respetar los límites físicos de sector (por ejemplo, 64 KB para tablas de fusión, suma de pesos de 2,048 en pools, y recálculo de EDC/ECC).
- **Pruebas Automatizadas:** Todo nuevo desarrollo o corrección de errores debe incluir su prueba correspondiente en la carpeta `tests/`.

### Envío de Pull Requests
1. Crea una rama para tu aporte: `git checkout -b mi-mejora` o `bugfix/descripcion-del-bug`.
2. Realiza commits con mensajes claros y descriptivos.
3. Asegúrate de que `pytest` termine en verde sin errores.
4. Abre un Pull Request describiendo los cambios realizados y las pruebas efectuadas.
