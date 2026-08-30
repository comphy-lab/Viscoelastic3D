# Viscoelastic3D Development Guidelines

## Project Structure
- `basilisk/src/`: local Basilisk CFD library (reference only, do not
  modify). Keep it untracked. Install with the ref-locked script from
  [basilisk-C](https://github.com/comphy-lab/basilisk-C).
- `src-local/`: project-specific Basilisk headers and helpers.
- `simulationCases/`: main simulation entry points and case utilities.
- `postProcess/`: post-processing and visualization tools.
- `.github/`: documentation and CI tooling (generated docs go to
  `docs/`).

## Build & Test Commands
- Compile single file: `qcc -O2 -Wall -disable-dimensions file.c -o executable -lm`
- Compile with custom headers: `qcc -O2 -Wall -disable-dimensions -I$PWD/src-local file.c -o executable -lm`
- Run a case with make: `cd simulationCases && make case_name.tst`
- Generate documentation (no deploy): `bash .github/scripts/build.sh`

Resolve `qcc` from the local `basilisk/src` tree after the ref-locked
install. Do not hardcode a machine-local compiler path.

## Documentation Generation
- Do not edit `docs/` directly (generated output).
- Use `.github/scripts/build.sh` for local builds.
- See `.github/Website-generator-readme.md` for usage.

## Code Style
- **Indentation**: 2 spaces (no tabs).
- **Line Length**: Maximum 80 characters per line.
- **Comments**: Use markdown in comments starting with `/**`.
- **Spacing**: Include spaces after commas and around operators.
- **File Organization**:
  - Place core functionality in `.h` headers.
  - Implement tests in `.c` files.
- **Naming Conventions**:
  - Use `snake_case` for variables and parameters.
  - Use `camelCase` for functions and methods.
- **Error Handling**: Return meaningful values and provide descriptive
  `stderr` messages.
