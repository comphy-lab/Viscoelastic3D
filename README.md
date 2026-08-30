# ElastoFlow: 2D/3D Viscoelastic Fluid Simulation Framework

[![DOI](https://zenodo.org/badge/874384071.svg)](https://doi.org/10.5281/zenodo.14011692)
[![Website Status](https://img.shields.io/website?url=https%3A%2F%2Fcomphy-lab.github.io%2FViscoelastic3D%2F&style=flat-square&logo=github&label=Website)](https://comphy-lab.github.io/Viscoelastic3D/)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-blue?style=flat-square&logo=github)](https://github.com/comphy-lab/Viscoelastic3D)

---

🚀 **ElastoFlow** is a state-of-the-art, open-source framework for simulating viscoelastic fluid flows in 2D and 3D, built as an extension to the [Basilisk C](http://basilisk.fr/) CFD library. It implements the log-conformation method for robust, high-Weissenberg number simulations, with a focus on clarity, extensibility, and scientific rigor.

## ✨ Key Features

- **Full 3D Log-Conformation Method**: Complete scalar implementation for 3D viscoelastic fluids ([log-conform-viscoelastic-scalar-3D.h](src-local/log-conform-viscoelastic-scalar-3D.h))
- **Robust 2D/Axi Support**: Scalar and tensor-based log-conformation for 2D and axisymmetric cases ([log-conform-viscoelastic-scalar-2D.h](src-local/log-conform-viscoelastic-scalar-2D.h), [log-conform-viscoelastic.h](src-local/log-conform-viscoelastic.h))
- **Optimized Matrix Algebra**: Efficient, stable eigenvalue and tensor operations ([eigen_decomposition.h](src-local/eigen_decomposition.h))
- **Advanced Initialization**: Functions for pseudo vectors/tensors in 2D/3D
- **Error Handling**: Negative eigenvalue checks, eigenvalue clamping, and detailed diagnostics
- **Performance**: Simplified acceleration term calculations and optimized tensor operations
- **Documentation**: Extensive inline documentation, mathematical background, and verification notes
- **Compatibility**: GPLv3 license, fully compatible with Basilisk and previous ElastoFlow versions

## 🐛 Bug Fixes (v2.5/v2.6)
- Corrected matrix algebra in 3D
- Fixed rotation tensor and eigenvalue edge cases
- Improved error reporting and diagnostics
- Enhanced axisymmetric and 2D/3D compatibility

## 🗂️ Repository Structure

```
├── src-local/                  # Custom viscoelastic solvers and tensor utilities
│   ├── log-conform-viscoelastic-scalar-3D.h   # 3D log-conformation (scalar)
│   ├── log-conform-viscoelastic-scalar-2D.h   # 2D/axi log-conformation (scalar)
│   ├── log-conform-viscoelastic.h             # 2D/axi log-conformation (tensor)
│   ├── two-phaseVE.h                          # Two-phase viscoelastic extension
│   └── eigen_decomposition.h                  # 3x3 symmetric eigenvalue solver
├── simulationCases/            # Example/test cases and post-processing scripts
│   ├── dropAtomisation.c                     # 3D drop atomisation simulation
│   ├── pinchOff.c                            # Pinch-off of viscoelastic jet (2D/axi)
│   ├── testEigenDecomposition.c              # Eigenvalue solver test/verification
│   ├── dropImpact.c                          # Drop impact simulation
│   └── verifyWtihPlots.ipynb                 # Jupyter notebook for verification/plots
├── postProcess/                # Project-specific post-processing tools and utilities
    ├── getData-elastic-scalar2D.c            # Data extraction utility
    ├── getFacet2D.c                          # Facet extraction utility
    ├── VideoAxi.py                           # Python visualization script
```

A local Basilisk tree belongs in `basilisk/` after the ref-locked install below. Do not commit it.

## 📚 Documentation
- [docs/](docs/) — Full HTML documentation, mathematical background, and API
- Inline documentation in all major headers (see `src-local/`)
- Example simulation and post-processing scripts in `simulationCases/`

## 🚀 Quick Start

### 1. Prerequisites
- [Basilisk C](https://github.com/comphy-lab/basilisk-C) via the ref-locked installer (gitignored in `basilisk/`)
- C compiler (e.g., gcc)
- Python 3 (for post-processing)
- Optional: Jupyter for notebooks

```sh
git clone https://github.com/comphy-lab/Viscoelastic3D.git
cd Viscoelastic3D
curl -sL https://raw.githubusercontent.com/comphy-lab/basilisk-C/v2026-08-30/reset_install_basilisk-ref-locked.sh | bash -s -- --ref=v2026-08-30 --hard
```

Update `v2026-08-30` with the latest [basilisk-C release](https://github.com/comphy-lab/basilisk-C/releases).

### 2. Compiling & Running Simulations

**A. Vanilla Basilisk method:**
```sh
qcc -O2 -Wall -I./src-local -disable-dimensions simulationCases/{CaseName}.c -o {CaseName} -lm 
./{CaseName}
```

**B. Using the Makefile (with bview browser):**
```sh
CFLAGS=-DDISPLAY=-1 make simulationCases/{CaseName}.tst
```

- For interactive visualization, open the generated `display.html` in your browser (see [Basilisk bview](http://basilisk.fr/three.js/editor/index.html?ws://localhost:7100)).

### 3. Post-Processing & Analysis
- Python scripts and Jupyter notebooks for data extraction and visualization are in `simulationCases/` (e.g., `VideoAxi.py`, `verifyWtihPlots.ipynb`).
- Example utilities: `getData-elastic-scalar2D.c`, `getFacet2D.c`.

## 📝 Example: Running a 3D Drop Atomisation Simulation

```sh
qcc -O2 -Wall -I./src-local -disable-dimensions simulationCases/dropAtomisation.c -o dropAtomisation -lm
./dropAtomisation
```

## 🔍 Technical Details
- **Log-Conformation Method**: See [src-local/log-conform-viscoelastic-scalar-3D.h](src-local/log-conform-viscoelastic-scalar-3D.h) and [src-local/log-conform-viscoelastic-scalar-2D.h](src-local/log-conform-viscoelastic-scalar-2D.h) for mathematical background and implementation notes.
- **Eigenvalue Solver**: [src-local/eigen_decomposition.h](src-local/eigen_decomposition.h) provides robust 3x3 symmetric eigensystem routines.
- **Two-Phase Flows**: [src-local/two-phaseVE.h](src-local/two-phaseVE.h) extends Basilisk's two-phase solver for viscoelasticity.
- **Axisymmetric/2D/3D**: Use the appropriate header for your geometry (see comments in each header for guidance).

## 🧑‍💻 Contributing
- See [AGENTS.md](AGENTS.md) for code style and development guidelines.
- Issue templates and feature requests: [GitHub Issue Templates](.github/ISSUE_TEMPLATE/)
- Pull requests are welcome! Please document your changes and update relevant tests/examples.

## 📋 License
This project is licensed under the [GNU GPLv3](LICENSE), in line with the Basilisk codebase.

## 🙏 Acknowledgments
- Thanks to all contributors and the Basilisk community

## 🔗 References
- Fattal & Kupferman (2004, 2005): Log-conformation method
- Comminal et al. (2015): Constitutive model functions
- Hao & Pan (2007): Split scheme implementation
- [Basilisk C](http://basilisk.fr/)

---
For detailed documentation, see the [docs/](docs/) folder or open `docs/index.html` in your browser.
